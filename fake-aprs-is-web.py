import json
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
import time
import netifaces
from datetime import datetime, timedelta
import re
import aprslib

# Configuration
HOST = '0.0.0.0'
HTTP_PORT = 14501
log_file_path = "/home/lighthouse/fake-aprs-is/fake-aprs-is-logs/fake-aprs-is.log"
all_packets = []  # Store all packets to apply filters
center_lat = 33.4484  # Phoenix, AZ latitude
center_lon = -112.0740  # Phoenix, AZ longitude

def get_all_ips():
    """Get all IP addresses of the server."""
    ip_addresses = []
    for iface in netifaces.interfaces():
        addrs = netifaces.ifaddresses(iface)
        if netifaces.AF_INET in addrs:
            for addr in addrs[netifaces.AF_INET]:
                ip_addresses.append(addr['addr'])
    return ip_addresses

def normalize_packet(packet):
    """Normalize the packet by removing substrings that shouldn't affect duplicate detection."""
    ignore_patterns = [r",qAR,[^:]*:", r",qAO,[^:]*:"]  # Add more patterns as needed
    for pattern in ignore_patterns:
        packet = re.sub(pattern, "", packet)
    return packet

def decode_packet(raw_packet):
    """Decode the packet to extract latitude, longitude, and other details."""
    try:
        packet = aprslib.parse(raw_packet)
        if "latitude" in packet and "longitude" in packet:
            return {
                "lat": packet["latitude"],
                "lon": packet["longitude"],
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "fields": packet,
                "callsign": packet.get("from", "Unknown")
            }
    except aprslib.exceptions.UnknownFormat:
        print(f"Skipping unknown format: {raw_packet}")
    except Exception as e:
        print(f"Parse error for packet: {raw_packet}, Error: {e}")
    return None

def process_new_aprs_data():
    """Continuously read the log file and add only new APRS packets to the list."""
    global all_packets
    try:
        with open(log_file_path, "r") as log_file:
            log_file.seek(0, 2)  # Move to the end of the file
            while True:
                line = log_file.readline()
                if not line:
                    time.sleep(0.1)
                    continue
                if "Received packet:" in line:
                    try:
                        raw_packet = line.split("Received packet: ", 1)[1].strip()

                        # Ignore `#` packets
                        if raw_packet == "#":
                            print("Ignored packet: #")
                            continue

                        normalized_packet = normalize_packet(raw_packet)

                        # Decode the packet
                        position = decode_packet(raw_packet)

                        if position:
                            # Check for duplicates
                            if any(
                                normalize_packet(p["fields"].get("raw", "")) == normalized_packet
                                for p in all_packets
                            ):
                                print(f"Duplicate packet ignored: {raw_packet}")
                                continue

                            all_packets.append(position)
                            if len(all_packets) > 1000:  # Limit history to 1000 packets
                                all_packets = all_packets[-1000:]
                            print(f"New packet added: {raw_packet}")
                    except Exception as e:
                        print(f"Error processing packet: {line.strip()}, Error: {e}")
    except FileNotFoundError:
        print("Log file not found. Please ensure the path is correct.")

class MapHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Serve the map with filtered position data."""
        if self.path.startswith("/new_positions.json"):
            # Extract query parameters
            params = self.path.split("?")
            filters = {}
            if len(params) > 1:
                filters = dict(p.split("=") for p in params[1].split("&"))

            # Apply time filter
            now = datetime.now()
            time_filter = filters.get("time", "all")
            min_time = now - timedelta(minutes=int(time_filter)) if time_filter != "all" else None

            # Apply call sign filter
            call_sign_filter = filters.get("callsigns", "all")
            call_signs = call_sign_filter.split(",") if call_sign_filter != "all" else None

            # "Last Updated Only" filter
            last_updated_only = filters.get("lastUpdatedOnly", "false") == "true"
            latest_positions = {}

            # Filter packets
            filtered_packets = []
            for p in all_packets:
                if min_time and datetime.strptime(p["timestamp"], "%Y-%m-%d %H:%M:%S") < min_time:
                    continue
                if call_signs and p["callsign"] not in call_signs:
                    continue
                if last_updated_only:
                    latest_positions[p["callsign"]] = p
                else:
                    filtered_packets.append(p)

            if last_updated_only:
                filtered_packets = list(latest_positions.values())

            # Serve filtered packets
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(filtered_packets).encode("utf-8"))
        elif self.path.startswith("/callsigns.json"):
            # Return unique list of call signs
            unique_callsigns = list(set(p["callsign"] for p in all_packets if p["callsign"] != "Unknown"))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(unique_callsigns).encode("utf-8"))
        else:
            # Serve the HTML map page
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Real-Time APRS Packet Map</title>
                <link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css" />
                <script src="https://unpkg.com/leaflet/dist/leaflet.js"></script>
            </head>
            <body>
                <h1>Real-Time APRS Packet Map</h1>
                <div id="map" style="width: 100%; height: 600px;"></div>
                <div>
                    <label>Filter by Time:</label>
                    <input type="range" id="timeFilter" min="1" max="121" value="121" oninput="updateTimeLabel(this.value)" onchange="updateFilters()" />
                    <span id="timeLabel">All</span>
                    <br/>
                    <label>Filter by Call Signs:</label>
                    <select id="callsignFilter" multiple onchange="updateFilters()">
                        <option value="all" selected>All</option>
                    </select>
                    <br/>
                    <input type="checkbox" id="lastUpdatedOnly" onchange="updateFilters()" />
                    <label for="lastUpdatedOnly">Last Updated Only</label>
                    <br/>
                    <button onclick="location.reload()">Refresh Map</button>
                </div>
                <script>
                    const map = L.map('map');
                    let savedCenter = localStorage.getItem("mapCenter");
                    let savedZoom = localStorage.getItem("mapZoom");

                    if (savedCenter && savedZoom) {{
                        map.setView(JSON.parse(savedCenter), parseInt(savedZoom));
                    }} else {{
                        map.setView([{center_lat}, {center_lon}], 13);
                    }}

                    const baseLayers = {{
                        "Street Map": L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                            maxZoom: 19,
                            attribution: 'Â© OpenStreetMap contributors'
                        }}),
                        "Satellite": L.tileLayer('https://mt1.google.com/vt/lyrs=s&x={{x}}&y={{y}}&z={{z}}', {{
                            maxZoom: 20,
                            attribution: 'Â© Google'
                        }}),
                        "Topographic": L.tileLayer('https://{{s}}.tile.opentopomap.org/{{z}}/{{x}}/{{y}}.png', {{
                            maxZoom: 17,
                            attribution: 'Â© OpenTopoMap contributors'
                        }})
                    }};
                    baseLayers["Street Map"].addTo(map);
                    L.control.layers(baseLayers).addTo(map);

                    async function updateFilters() {{
                        const timeFilter = document.getElementById("timeFilter").value;
                        const callsignFilter = Array.from(document.getElementById("callsignFilter").selectedOptions).map(opt => opt.value).join(",");
                        const lastUpdatedOnly = document.getElementById("lastUpdatedOnly").checked;
                        const response = await fetch(`/new_positions.json?time=${{timeFilter === "121" ? "all" : timeFilter}}&callsigns=${{callsignFilter}}&lastUpdatedOnly=${{lastUpdatedOnly}}`);
                        const newPositions = await response.json();
                        map.eachLayer(layer => layer instanceof L.Marker && map.removeLayer(layer));
                        newPositions.forEach(position => {{
                            const fieldsData = JSON.stringify(position.fields, null, 2)
                                .replace(/\\n/g, "<br/>")
                                .replace(/ /g, "&nbsp;");
                            L.marker([position.lat, position.lon]).addTo(map)
                                .bindPopup(`Callsign: ${'{'}position.callsign{'}'}<br/>Data:<br/>${'{'}fieldsData{'}'}`);
                        }});
                    }}

                    async function loadCallSigns() {{
                        const response = await fetch("/callsigns.json");
                        const callsigns = await response.json();
                        const callsignFilter = document.getElementById("callsignFilter");
                        callsignFilter.innerHTML = "<option value='all' selected>All</option>";
                        callsigns.forEach(call => {{
                            const option = document.createElement("option");
                            option.value = call;
                            option.text = call;
                            callsignFilter.appendChild(option);
                        }});
                    }}

                    function updateTimeLabel(value) {{
                        const label = value === "121" ? "All" : `${{value}} minutes`;
                        document.getElementById("timeLabel").textContent = label;
                    }}

                    map.on("moveend", () => {{
                        localStorage.setItem("mapCenter", JSON.stringify(map.getCenter()));
                        localStorage.setItem("mapZoom", map.getZoom());
                    }});

                    loadCallSigns();
                    updateFilters();
                </script>
            </body>
            </html>
            """
            self.wfile.write(html_content.encode("utf-8"))

def run_http_server():
    """Run the HTTP server."""
    http_server = HTTPServer((HOST, HTTP_PORT), MapHTTPRequestHandler)
    print(f"Server running at http://{HOST}:{HTTP_PORT}/")
    for ip in get_all_ips():
        print(f"- {ip}:{HTTP_PORT}")
    http_server.serve_forever()

if __name__ == "__main__":
    log_thread = threading.Thread(target=process_new_aprs_data, daemon=True)
    log_thread.start()
    run_http_server()


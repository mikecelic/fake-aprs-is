#!/home/lighthouse/fake-aprs-is-env/bin/python
import socket
import datetime
import time
import threading

# Configuration
HOST = '0.0.0.0'  # Listen on all available interfaces
PORT = 14580      # Typical APRS-IS port
log_file_path = '/home/lighthouse/fake-aprs-is/fake-aprs-is-logs/fake-aprs-is.log'
keepalive_interval = 60  # Send keepalive every 60 seconds
recent_packets = []  # Store recent packets for log
max_recent_packets = 100  # Limit the number of packets stored

def log_packet(ip_address, packet_data, log_to_console=True):
    """Log packet data with a timestamp, including IP address, and optionally print to console."""
    timestamp = datetime.datetime.now().isoformat()
    log_entry = f"{timestamp} - {ip_address} - {packet_data}"

    # Append the log entry to recent packets list
    recent_packets.append(log_entry)
    if len(recent_packets) > max_recent_packets:
        recent_packets.pop(0)  # Keep only the most recent packets

    # Write to log file
    with open(log_file_path, 'a') as log_file:
        log_file.write(log_entry + "\n")

    # Print to console if needed
    if log_to_console:
        print(log_entry)

def send_keepalive(client_socket, ip_address):
    """Send keepalive messages to the client at regular intervals."""
    while True:
        time.sleep(keepalive_interval)
        try:
            keepalive_message = "# keepalive\r\n"
            client_socket.send(keepalive_message.encode('utf-8'))
            log_packet(ip_address, "Sent keepalive")
        except (BrokenPipeError, ConnectionResetError):
            log_packet(ip_address, "Connection closed during keepalive")
            break

def handle_client(client_socket, ip_address):
    """Handle communication with a single client."""
    # Start keepalive thread for this client
    keepalive_thread = threading.Thread(target=send_keepalive, args=(client_socket, ip_address))
    keepalive_thread.start()

    # Send a welcome message immediately upon connection
    welcome_message = "# Welcome to APRS-IS (fake server)\r\n"
    client_socket.send(welcome_message.encode('utf-8'))
    log_packet(ip_address, "Sent welcome message")

    # Wait to receive authentication data
    auth_data = client_socket.recv(1024).decode('utf-8', errors='replace').strip()
    log_packet(ip_address, f"Received authentication data: {auth_data}")

    # Add a slight delay
    time.sleep(0.5)

    # Send back logresp acknowledgment to mimic APRS-IS authentication response
    callsign = auth_data.split()[1]  # Extract the callsign
    auth_ack = f"# logresp {callsign} verified, server 1.0\r\n"
    client_socket.send(auth_ack.encode('utf-8'))
    log_packet(ip_address, f"Sent logresp for callsign {callsign}")

    # Begin packet receiving loop
    while True:
        try:
            # Receive packet data from the client
            data = client_socket.recv(1024)
            if not data:
                break

            # Log each received packet
            packet_data = data.decode('utf-8', errors='replace').strip()
            log_packet(ip_address, f"Received packet: {packet_data}")

        except UnicodeDecodeError as e:
            log_packet(ip_address, f"Decoding error: {e}")

    client_socket.close()
    log_packet(ip_address, "Connection closed")

# Setting up the server socket with SO_REUSEADDR
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Allow reuse of the port
server_socket.bind((HOST, PORT))
server_socket.listen()

log_packet("Server", f"APRS-IS fake server listening on port {PORT}", log_to_console=True)

# Main server loop
while True:
    client_socket, addr = server_socket.accept()
    ip_address = addr[0]  # Extract only the IP address
    log_packet(ip_address, "Connection established")

    # Start a new thread to handle the client
    client_thread = threading.Thread(target=handle_client, args=(client_socket, ip_address))
    client_thread.start()

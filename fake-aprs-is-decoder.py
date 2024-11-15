#!/usr/bin/env python3

import aprslib
import json
import argparse
from datetime import datetime, timedelta

# Path to the APRS log file
log_file_path = "/home/lighthouse/fake-aprs-is/fake-aprs-is-logs/fake-aprs-is.log"

# Supported packet types
PACKET_TYPES = ["position", "weather", "telemetry", "status", "message", "object", "item", "query", "nmea"]

def parse_duration(duration_str):
    """Parse duration strings like '1h', '30min', etc., and return a timedelta."""
    units = {'min': 'minutes', 'h': 'hours', 'd': 'days', 'w': 'weeks'}
    num = int(''.join(filter(str.isdigit, duration_str)))
    unit = ''.join(filter(str.isalpha, duration_str))
    return timedelta(**{units[unit]: num})

def process_log_line(line, debug):
    """Process only lines that start with 'Received packet:'."""
    if "Received packet:" in line:
        try:
            timestamp_str, client_ip, packet_line = line.split(" - ", 2)
            timestamp = datetime.fromisoformat(timestamp_str)
            packet_data = packet_line.split("Received packet: ", 1)[1].strip()
            if debug:
                print(f"DEBUG: Extracted packet: {packet_data}")
            return line, packet_data, client_ip, timestamp
        except ValueError:
            if debug:
                print(f"DEBUG: Skipped line due to formatting issue: {line.strip()}")
    else:
        if debug:
            print(f"DEBUG: Skipped line - does not contain 'Received packet:': {line.strip()}")
    return None, None, None, None

def infer_packet_type(packet):
    """Infer the packet type based on its fields, prioritizing specific types."""
    if "weather" in packet:
        return "weather"
    if "message_text" in packet:
        return "message"
    if "object_name" in packet:
        return "object"
    if "telemetry" in packet or packet.get("format") == "telemetry-message":
        return "telemetry"
    if "latitude" in packet and "longitude" in packet:
        return "position"
    if "status" in packet:
        return "status"
    if "query" in packet:
        return "query"
    if "nmea" in packet:
        return "nmea"
    return None

def decode_aprs_packet(logline, packet_data, client_ip, log_timestamp, duration=None, filter_type=None, search_term=None, suppress_errors=False, debug=False):
    """Decodes an APRS packet and applies filters."""
    try:
        if duration and datetime.now() - log_timestamp > duration:
            if debug:
                print(f"DEBUG: Skipped packet due to duration filter - {log_timestamp}")
            return

        # Attempt to parse the packet
        packet = aprslib.parse(packet_data)
        if debug:
            print(f"DEBUG: Parsed packet - {packet}")

        # Infer and add type
        packet_type = infer_packet_type(packet)
        if packet_type:
            packet["type"] = packet_type

        if filter_type and packet_type != filter_type:
            if debug:
                print(f"DEBUG: Packet type '{packet_type}' does not match filter '{filter_type}', skipping.")
            return

        if search_term and search_term.lower() not in json.dumps(packet).lower():
            if debug:
                print(f"DEBUG: Search term '{search_term}' not found in packet, skipping.")
            return

        # Output the original logline with the parsed packet
        print(f"Logline: {logline.strip()}")
        print(json.dumps(packet, indent=4, ensure_ascii=False))

    except aprslib.exceptions.ParseError as e:
        if debug:
            print(f"{log_timestamp} - Parse Error: {e}")
    except Exception as e:
        if debug:
            print(f"{log_timestamp} - Error: {e}")

def main():
    parser = argparse.ArgumentParser(description="Decode APRS packets from log file")
    parser.add_argument(
        "-t", "--type", 
        help=f"Filter output by packet type (options: {', '.join(PACKET_TYPES)})"
    )
    parser.add_argument("-s", "--search", help="Case-insensitive search term")
    parser.add_argument("-d", "--duration", type=str, default="1h", help="Specify duration (e.g., 1min, 30min, 1h, 5h, 1d, 1w)")
    parser.add_argument("--debug", action="store_true", help="Enable debugging output")

    args = parser.parse_args()
    filter_type = args.type
    search_term = args.search
    duration = parse_duration(args.duration)
    debug = args.debug
    suppress_errors = not debug

    if debug:
        print(f"DEBUG: Filter type: {filter_type}, Search term: {search_term}, Duration: {duration}")

    with open(log_file_path, "r") as log_file:
        for line in log_file:
            logline, packet_data, client_ip, log_timestamp = process_log_line(line.strip(), debug)
            if packet_data and client_ip and log_timestamp:
                decode_aprs_packet(logline, packet_data, client_ip, log_timestamp, duration, filter_type, search_term, suppress_errors, debug)

if __name__ == "__main__":
    main()


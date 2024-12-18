#!/usr/bin/env python3
import re
import argparse
from collections import defaultdict
from datetime import datetime, timedelta

# Initialize dictionaries to hold hourly counts for each client
client_hourly_counts = defaultdict(lambda: defaultdict(int))
client_last_hour_packets = defaultdict(list)  # Stores packets with timestamps for each client in the specified time range

# Parse command-line arguments
parser = argparse.ArgumentParser(description="APRS Log Analyzer")
parser.add_argument("-d", "--duration", type=str, default="1h", help="Specify duration (e.g., 1min, 30min, 1h, 5h, 1d, 1w)")
parser.add_argument("-u", "--unique", action="store_true", help="Show unique packets for each client")
parser.add_argument("-i", "--identical", action="store_true", help="Show packets seen by all clients")
args = parser.parse_args()

# Determine the time delta based on the -d argument
time_delta_mapping = {
    "min": "minutes",
    "h": "hours",
    "d": "days",
    "w": "weeks"
}
unit = args.duration[-3:] if args.duration.endswith("min") else args.duration[-1]
value = int(args.duration[:-3]) if unit == "min" else int(args.duration[:-1])  # Default to 1 if parsing fails
time_delta = timedelta(**{time_delta_mapping.get(unit, "hours"): value})

# Get the current time and calculate the start time for the log range
latest_timestamp = datetime.now()
time_range_start = latest_timestamp - time_delta

# Function to normalize packets by removing `qAO`, `qAR`, and similar parts
def normalize_packet(packet):
    # Remove `qAO`, `qAR`, or similar patterns
    normalized = re.sub(r",qA[OR],[^:]+:", ":", packet).strip()
    return normalized

# List to store all unique packets with timestamps for sorting later
all_unique_packets_with_timestamps = []

# Define a list of patterns to ignore, including keepalive packets
ignore_patterns = [
    "Packet: Sent keepalive",
    "Connection established",
    "#",  # Any packet with only `#`
]

# Open and read the log file
with open('/home/lighthouse/fake-aprs-is/fake-aprs-is-logs/fake-aprs-is.log', 'r') as file:
    for line in file:
        # Skip lines containing any ignore patterns, including keepalives
        if any(pattern in line for pattern in ignore_patterns):
            continue

        # Extract the timestamp, client IP, and message
        match = re.match(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+)\s-\s([\d.]+)\s-\s(.+)', line)
        if match:
            timestamp, client_ip, packet_data = match.groups()
            date_time = datetime.fromisoformat(timestamp)

            # Skip packets older than the specified time range
            if date_time < time_range_start:
                continue

            # Increment counts for the client on an hourly basis
            hour_str = date_time.strftime('%Y-%m-%d %H:00')
            client_hourly_counts[client_ip][hour_str] += 1

            # Normalize the packet for comparison, but keep the original for display
            normalized_packet = normalize_packet(packet_data)
            if normalized_packet in ["#", ""]:
                continue  # Skip empty packets or those with only `#`

            # Track original and normalized packets with timestamps for comparison
            client_last_hour_packets[client_ip].append((date_time, packet_data, normalized_packet))

# Perform detailed comparison of packets within the specified time range
identical_counts = defaultdict(int)
unique_counts = defaultdict(int)
client_packet_diff = defaultdict(list)  # Store packet differences

# Check identical and unique counts per client in the specified time range
for client, packets in client_last_hour_packets.items():
    for timestamp, original_packet, normalized_packet in packets:
        # Check if this normalized packet appears in other clients' data within a 1-second window
        is_identical = any(
            abs((timestamp - other_timestamp).total_seconds()) <= 1 and normalized_packet == other_packet
            for other_client, other_packets in client_last_hour_packets.items()
            if other_client != client
            for other_timestamp, _, other_packet in other_packets
        )

        if is_identical:
            identical_counts[client] += 1
            if args.identical:
                # Add to global list if showing identical packets across clients
                all_unique_packets_with_timestamps.append((timestamp, client, original_packet))
        else:
            # Skip adding "Sent keepalive" packets to unique counts or output
            if "Sent keepalive" in original_packet:
                continue
            unique_counts[client] += 1
            # Log this packet as unique to this client for debugging
            client_packet_diff[client].append((timestamp, original_packet))
            # Also add to the global list for sorting later if showing unique packets
            if args.unique:
                all_unique_packets_with_timestamps.append((timestamp, client, original_packet))

# Sort the global list of all unique packets by timestamp
all_unique_packets_with_timestamps.sort(key=lambda x: x[0])

# Output results
print("\nHourly Counts:")
for client, hours in client_hourly_counts.items():
    print(f"\nClient: {client}")
    for hour, count in hours.items():
        print(f"  {hour}: {count} messages")

print("\nDetailed Comparison (Total Counts per Client):")
for client in client_last_hour_packets.keys():
    total_packets = identical_counts[client] + unique_counts[client]
    identical_percentage = (identical_counts[client] / total_packets) * 100 if total_packets > 0 else 0
    print(f"\nClient: {client}")
    print(f"  Identical packets: {identical_counts[client]} ({identical_percentage:.2f}%)")
    print(f"  Unique packets: {unique_counts[client]}")

if args.unique:
    print("\nPacket Differences (Unique Packets per Client):")
    for client, unique_packets in client_packet_diff.items():
        print(f"\nClient: {client}")
        print("  Unique packets in this client (not seen by others):")
        for timestamp, packet in sorted(unique_packets, key=lambda x: x[0]):
            print(f"    {timestamp}: {packet}")

if args.identical:
    print("\nAll Identical Packets Across Clients (Sorted by Timestamp):")
    for timestamp, client, packet in all_unique_packets_with_timestamps:
        print(f"{timestamp} - Client: {client} - Packet: {packet}")

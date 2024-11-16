#!/home/lighthouse/fake-aprs-is-env/bin/python
import serial
import time
import re
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Configuration
log_file_path = '/home/lighthouse/fake-aprs-is/fake-aprs-is-logs/fake-aprs-is.log'
serial_port = '/dev/ttyS1'  # Update to your console port
baud_rate = 9600           # Adjust to match your radio's configuration
last_sent_packets = {}     # Cache for normalized packets with their timestamps

# Patterns to ignore
ignore_patterns = [
    r'^#',  # Lines that start with #
    r'TCPIP\*'  # Lines containing TCPIP* in the source/destination
]

def extract_packet(log_line):
    """Extract APRS packet from a log line using regex."""
    match = re.search(r'Received packet: (.+)', log_line)
    if match:
        return match.group(1)
    return None

def normalize_packet(packet):
    """Normalize a packet string by removing dynamic parts."""
    # Remove any dynamic identifiers using regex
    normalized = re.sub(r",q[A-Z]+,[^:]+:", "", packet)
    return normalized.strip()

def should_ignore_packet(packet):
    """Check if the packet matches any ignore patterns."""
    for pattern in ignore_patterns:
        if re.search(pattern, packet):
            return True
    return False

def is_unique_packet(packet):
    """Check if a normalized packet is unique within the last second."""
    current_time = time.time()
    normalized_packet = normalize_packet(packet)
    if normalized_packet in last_sent_packets:
        if current_time - last_sent_packets[normalized_packet] < 1:
            return False  # Duplicate within the same second
    last_sent_packets[normalized_packet] = current_time
    return True

class LogFileHandler(FileSystemEventHandler):
    """Handle changes to the log file."""
    def __init__(self, serial_connection):
        self.serial_connection = serial_connection
        self.file = open(log_file_path, 'r')
        self.file.seek(0, 2)  # Start at the end of the file

    def on_modified(self, event):
        """React to the log file being modified."""
        if event.src_path == log_file_path:
            for line in self.file:
                packet = extract_packet(line.strip())
                if packet:
                    if should_ignore_packet(packet):
                        print(f"Packet ignored: {packet}")
                    elif not is_unique_packet(packet):
                        print(f"Duplicate packet ignored: {packet}")
                    else:
                        # Send the unique and non-ignored packet to the console port
                        self.serial_connection.write(packet.encode('utf-8') + b'\r\n')
                        print(f"Packet sent to {serial_port}: {packet}")

def main():
    try:
        # Open the serial port
        with serial.Serial(serial_port, baud_rate, timeout=1) as ser:
            print(f"Listening to log file and forwarding packets to {serial_port}...")

            # Set up the log file watcher
            event_handler = LogFileHandler(serial_connection=ser)
            observer = Observer()
            observer.schedule(event_handler, path=log_file_path, recursive=False)
            observer.start()

            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("Exiting on user interrupt.")
                observer.stop()

            observer.join()
    except serial.SerialException as e:
        print(f"Serial port error: {e}")

if __name__ == "__main__":
    main()


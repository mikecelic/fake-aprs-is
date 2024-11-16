#!/home/lighthouse/fake-aprs-is-env/bin/python
import serial
import datetime

# Configuration
serial_port = '/dev/ttyS0'  # Update to your console port (e.g., /dev/ttyUSB0 or COMx on Windows)
baud_rate = 9600             # Adjust to match your radio's configuration
log_file_path = '/home/lighthouse/fake-aprs-is/fake-aprs-is-logs/fake-aprs-is.log'

def log_console_packet(packet_data):
    """Log console packet data with a timestamp."""
    timestamp = datetime.datetime.now().isoformat()
    log_entry = f"{timestamp} - Console - {packet_data}"

    # Write to log file
    with open(log_file_path, 'a') as log_file:
        log_file.write(log_entry + "\n")

    # Print to console for debugging
    print(log_entry)

def main():
    try:
        # Open the serial port
        with serial.Serial(serial_port, baud_rate, timeout=1) as ser:
            print(f"Listening on {serial_port} at {baud_rate} baud...")
            while True:
                # Read a line of data from the serial port
                line = ser.readline().decode('utf-8', errors='replace').strip()
                if line:
                    log_console_packet(line)
    except serial.SerialException as e:
        print(f"Serial port error: {e}")
    except KeyboardInterrupt:
        print("Exiting on user interrupt.")

if __name__ == "__main__":
    main()

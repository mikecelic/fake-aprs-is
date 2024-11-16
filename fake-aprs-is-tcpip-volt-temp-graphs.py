import re
import matplotlib.pyplot as plt
from datetime import datetime
from collections import defaultdict

# Define the log file path
log_file_path = "/home/lighthouse/fake-aprs-is/fake-aprs-is-logs/fake-aprs-is.log"

# Define the regex pattern to match the desired lines and extract values
pattern = re.compile(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+) - .+ - Received packet: (\w+)>LHOUSE,TCPIP\*:@\d+z\d{4}\.\d{2}[NS]/\d{5}\.\d{2}[EW]-.*U=(\d+\.\d+)V,T=.*?(\d+\.\d+)F')

# Initialize a dictionary to hold data for each client
clients_data = defaultdict(lambda: {'timestamps': [], 'voltages': [], 'temperatures': []})

# Open the log file and process each line
with open(log_file_path, 'r') as file:
    for line in file:
        match = pattern.search(line)
        if match:
            timestamp_str, client, voltage_str, temperature_str = match.groups()

            # Parse the timestamp and extract numeric values
            timestamp = datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S.%f")
            voltage = float(voltage_str)
            temperature = float(temperature_str)

            # Append values to the respective client's data
            clients_data[client]['timestamps'].append(timestamp)
            clients_data[client]['voltages'].append(voltage)
            clients_data[client]['temperatures'].append(temperature)

# Check if data was found for any client
if not clients_data:
    print("No matching data found in log.")
else:
    for client, data in clients_data.items():
        timestamps = data['timestamps']
        voltages = data['voltages']
        temperatures = data['temperatures']

        print(f"\nData for client: {client}")
        for i in range(len(timestamps)):
            print(f"Timestamp: {timestamps[i]}, Voltage: {voltages[i]}V, Temperature: {temperatures[i]}F")

        # Plot and save Voltage for this client
        plt.figure(figsize=(12, 6))
        plt.plot(timestamps, voltages, marker='o', linestyle='-', label="Voltage (V)")
        plt.xlabel("Timestamp")
        plt.ylabel("Voltage (V)")
        plt.title(f"Voltage Over Time - {client}")
        plt.legend()
        plt.gcf().autofmt_xdate()
        plt.savefig(f"{client}_voltage_over_time.png")
        print(f"Voltage plot saved as {client}_voltage_over_time.png")

        # Plot and save Temperature for this client
        plt.figure(figsize=(12, 6))
        plt.plot(timestamps, temperatures, marker='o', color='r', linestyle='-', label="Temperature (F)")
        plt.xlabel("Timestamp")
        plt.ylabel("Temperature (F)")
        plt.title(f"Temperature Over Time - {client}")
        plt.legend()
        plt.gcf().autofmt_xdate()
        plt.savefig(f"{client}_temperature_over_time.png")
        print(f"Temperature plot saved as {client}_temperature_over_time.png")

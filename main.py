import time
from sensor_simulator.sensor import generate_sensor_data
from fog_node.fog_processor import process_data

while True:

    sensor_data = generate_sensor_data()

    processed_data = process_data(sensor_data)

    print("Processed Data:", processed_data)

    time.sleep(5)
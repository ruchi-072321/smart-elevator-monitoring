import time
from sensor_simulator.sensor import generate_sensor_data
from fog_node.fog_processor import process_data
from backend.api_sender import send_to_cloud

# configurable sensor interval
SENSOR_INTERVAL = 5

while True:

    sensor_data = generate_sensor_data()

    processed_data = process_data(sensor_data)

    print("Processed Data:", processed_data)

    # only send important events to cloud
    if processed_data["status"] != "NORMAL":
        send_to_cloud(processed_data)

    time.sleep(SENSOR_INTERVAL)
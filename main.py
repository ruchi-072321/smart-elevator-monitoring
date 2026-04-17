import threading
import time
from sensor_simulator.sensor import generate_sensor_data
from fog_node.fog_processor import process_data
from backend.api_sender import send_to_cloud
from backend.api_server import run_server
from backend.data_store import set_latest_sensor_data

# configurable sensor interval
SENSOR_INTERVAL = 5


def start_api_server():
    run_server(port=5000)


if __name__ == "__main__":
    api_thread = threading.Thread(target=start_api_server, daemon=True)
    api_thread.start()

    while True:
        sensor_data_list = generate_sensor_data()

        processed_list = []
        for sensor_data in sensor_data_list:
            processed_data = process_data(sensor_data)
            print("Processed Data:", processed_data)
            processed_list.append(processed_data)
            send_to_cloud(processed_data)

        set_latest_sensor_data(processed_list)
        time.sleep(SENSOR_INTERVAL)

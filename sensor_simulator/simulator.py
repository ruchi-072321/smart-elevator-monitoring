import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sensor import generate_sensor_data
from fog_node.fog_processor import process_data
from backend.api_sender import send_to_cloud

SENSOR_INTERVAL = 5


def run_simulator():
    while True:
        sensor_data_list = generate_sensor_data()

        for sensor_data in sensor_data_list:
            processed_data = process_data(sensor_data)
            print("Simulated Data:", processed_data)
            send_to_cloud(processed_data)

        time.sleep(SENSOR_INTERVAL)


if __name__ == "__main__":
    run_simulator()

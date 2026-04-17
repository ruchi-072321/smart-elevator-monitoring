import random
import time

ELEVATOR_ID = "ELEVATOR_1"
SENSOR_TYPES = ["temperature", "vibration", "weight", "people_count"]


def create_sensor_payload(sensor_type, base):
    return {
        "elevator_id": ELEVATOR_ID,
        "timestamp": str(int(time.time() * 1000)),
        "sensor_type": sensor_type,
        "sensor_value": base[sensor_type],
        "people_count": base["people_count"],
        "temperature": base["temperature"],
        "vibration": base["vibration"],
        "door_status": base["door_status"],
        "weight": base["weight"]
    }


def generate_sensor_data():
    temperature = round(20 + random.uniform(-10, 20), 1)
    vibration = round(random.uniform(0.1, 5.5), 2)
    weight = random.randint(0, 2500)
    people_count = random.randint(0, 25)
    door_status = random.choice(["open", "closed", "opening", "closing"])
    
    base = {
        "people_count": people_count,
        "temperature": temperature,
        "vibration": vibration,
        "weight": weight,
        "door_status": door_status
    }

    sensors = [create_sensor_payload(sensor_type, base) for sensor_type in SENSOR_TYPES]
    assert len(sensors) == 4, f"Expected 4 sensors, got {len(sensors)}"
    return sensors

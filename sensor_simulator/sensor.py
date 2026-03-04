import random
import time

def generate_sensor_data():

    data = {
        "elevator_id": "ELEVATOR_1",
        "people_count": random.randint(0,8),
        "weight": random.randint(100,600),
        "vibration": round(random.uniform(0,5),2),
        "temperature": random.randint(20,70),
        "door_status": random.choice(["open","closed"]),
        "timestamp": time.time()
    }

    return data
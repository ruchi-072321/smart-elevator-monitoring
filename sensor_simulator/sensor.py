import random
import time
import requests

API_URL = "https://n7omj6kh6k.execute-api.us-east-1.amazonaws.com/process-elevator-data"

while True:
    base_temp = 35
    base_vibration = 2

    data = {
        "elevator_id": "ELEVATOR_1",
        "timestamp": str(int(time.time() * 1000)),
        "people_count": random.randint(0, 10),
        "temperature": base_temp + random.randint(-5, 10),
        "vibration": round(base_vibration + random.uniform(-1.5, 2.5), 2),
        "door_status": random.choice(["open", "closed"]),
        "weight": random.randint(100, 800)
    }

    # 🔥 ALERT LOGIC
    alerts = []
    status = "NORMAL"

    if data["temperature"] > 60:
        alerts.append("High temperature")
        status = "WARNING"

    if data["vibration"] > 2.5:
        alerts.append("High vibration")
        status = "WARNING"

    if data["weight"] > 700:
        alerts.append("Overweight")
        status = "CRITICAL"

    data["alerts"] = alerts
    data["status"] = status

    try:
        response = requests.post(API_URL, json=data)
        print("Sent:", data, "Status:", response.status_code)
    except Exception as e:
        print("Error:", e)

    time.sleep(3)
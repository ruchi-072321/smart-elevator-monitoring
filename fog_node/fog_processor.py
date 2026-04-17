def process_data(data):
    sensor_type = data["sensor_type"]
    sensor_value = data["sensor_value"]

    alerts = []

    if sensor_type == "weight" and sensor_value > 500:
        alerts.append("OVERLOAD")

    if sensor_type == "temperature" and sensor_value > 60:
        alerts.append("OVERHEATING")

    if sensor_type == "vibration" and sensor_value > 3:
        alerts.append("HIGH VIBRATION")

    if sensor_type == "door_status" == "open" and sensor_type == "people_count" and sensor_value == 0:
        alerts.append("DOOR MALFUNCTION")

    data["alerts"] = alerts

    # system health status
    if len(alerts) == 0:
        data["status"] = "NORMAL"
    elif len(alerts) == 1:
        data["status"] = "WARNING"
    else:
        data["status"] = "CRITICAL"

    return data
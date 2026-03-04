def process_data(data):

    alerts = []

    if data["weight"] > 500:
        alerts.append("OVERLOAD")

    if data["temperature"] > 60:
        alerts.append("OVERHEATING")

    if data["vibration"] > 3:
        alerts.append("HIGH VIBRATION")

    if data["door_status"] == "open" and data["people_count"] == 0:
        alerts.append("DOOR MALFUNCTION")

    data["alerts"] = alerts

    return data
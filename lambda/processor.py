import json
import os
from decimal import Decimal
from datetime import datetime, timezone

from runtime_bootstrap import ensure_local_site_packages

ensure_local_site_packages()

import boto3
from botocore.exceptions import ClientError

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
TABLE_NAME = os.getenv("DYNAMODB_TABLE", "ElevatorSensorData")
SNS_TOPIC_ARN = os.getenv("SNS_TOPIC_ARN", "").strip()

print(f"DEBUG: AWS_REGION={AWS_REGION}, TABLE_NAME={TABLE_NAME}")

dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
sns = boto3.client("sns", region_name=AWS_REGION)
table = dynamodb.Table(TABLE_NAME)

print(f"DEBUG: Table loaded: {table.table_name}, endpoint: {table.meta.client._endpoint.host}")


def to_decimal(value):
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {key: to_decimal(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_decimal(item) for item in value]
    return value


def normalize_event(event):
    if isinstance(event, dict) and "Records" in event:
        event = event["Records"][0]

    if isinstance(event, dict) and "body" in event and isinstance(event["body"], str):
        try:
            return json.loads(event["body"])
        except json.JSONDecodeError:
            pass

    return event if isinstance(event, dict) else {}


def analyze_sensor(data):
    sensor_type = data.get("sensor_type")
    sensor_value = float(data.get("sensor_value", 0) or 0)
    alerts = []

    if sensor_type == "temperature" and sensor_value > 40:
        alerts.append("HIGH TEMPERATURE")
    elif sensor_type == "temperature" and sensor_value < 15:
        alerts.append("LOW TEMPERATURE")

    if sensor_type == "vibration" and sensor_value > 4.0:
        alerts.append("HIGH VIBRATION")

    if sensor_type == "weight" and sensor_value > 2400:
        alerts.append("OVERLOAD")
    elif sensor_type == "weight" and sensor_value < 50:
        alerts.append("SENSOR ERROR - WEIGHT")

    if sensor_type == "people_count" and sensor_value > 20:
        alerts.append("CAPACITY WARNING")

    if not alerts:
        status = "NORMAL"
    elif len(alerts) == 1:
        status = "WARNING"
    else:
        status = "CRITICAL"

    return alerts, status


def build_item(data):
    elevator_id = data.get("elevator_id", "ELEVATOR_1")
    raw_timestamp = str(data.get("timestamp") or int(datetime.now(timezone.utc).timestamp() * 1000))
    sensor_type = data.get("sensor_type", "unknown")
    event_id = f"{elevator_id}#{raw_timestamp}#{sensor_type}"  # Create unique event_id

    alerts, status = analyze_sensor(data)
    processed_at = datetime.now(timezone.utc).isoformat()

    item = {
        "event_id": event_id,
        "elevator_id": elevator_id,
        "timestamp": raw_timestamp,
        "raw_timestamp": raw_timestamp,
        "sensor_type": sensor_type,
        "sensor_value": data.get("sensor_value"),
        "temperature": data.get("temperature"),
        "vibration": data.get("vibration"),
        "weight": data.get("weight"),
        "people_count": data.get("people_count"),
        "door_status": data.get("door_status"),
        "alerts": alerts,
        "status": status,
        "processed_at": processed_at,
    }
    return to_decimal(item)


def store_to_dynamodb(item):
    try:
        # Check if table exists
        table.load()
        print(f"Table loaded: {table.table_name}, status: {table.table_status}")
        table.put_item(Item=item)
        print(f"Successfully stored item in DynamoDB: {item['elevator_id']} {item['sensor_type']}")
    except Exception as e:
        print(f"Failed to store in DynamoDB: {e}")
        raise


def send_alert(item):
    if not SNS_TOPIC_ARN or not item.get("alerts"):
        return

    message = (
        "ELEVATOR ALERT\n\n"
        f"Elevator: {item['elevator_id']}\n"
        f"Sensor: {item['sensor_type']}\n"
        f"Value: {item['sensor_value']}\n"
        f"Alerts: {', '.join(item['alerts'])}\n"
        f"Status: {item['status']}\n"
        f"Time: {item['processed_at']}"
    )
    sns.publish(
        TopicArn=SNS_TOPIC_ARN,
        Subject=f"Elevator Alert: {item['status']}",
        Message=message,
    )


def lambda_handler(event, context):
    try:
        print(f"DEBUG: Received event: {json.dumps(event)}")
        data = normalize_event(event)
        print(f"DEBUG: Normalized data: {json.dumps(data)}")
        item = build_item(data)
        print(f"DEBUG: Built item: {json.dumps(item, default=str)}")
        store_to_dynamodb(item)
        send_alert(item)

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "Data processed successfully",
                    "sensor_type": item["sensor_type"],
                    "status": item["status"],
                    "alerts": item["alerts"],
                    "debug": {
                        "table_name": TABLE_NAME,
                        "region": AWS_REGION,
                        "endpoint": table.meta.client._endpoint.host,
                        "item_keys": list(item.keys())
                    }
                }
            ),
        }
    except ClientError as exc:
        print(f"DynamoDB/SNS error: {exc}")
        return {"statusCode": 500, "body": json.dumps({"error": str(exc)})}
    except Exception as exc:
        print(f"Error processing sensor data: {exc}")
        return {"statusCode": 500, "body": json.dumps({"error": str(exc)})} 

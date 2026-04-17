import json
import os
from collections import defaultdict
from decimal import Decimal

from runtime_bootstrap import ensure_local_site_packages

ensure_local_site_packages()

import boto3
from boto3.dynamodb.conditions import Key

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
TABLE_NAME = os.getenv("DYNAMODB_TABLE", "ElevatorSensorData")
ELEVATOR_ID = os.getenv("ELEVATOR_ID", "ELEVATOR_1")

dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
table = dynamodb.Table(TABLE_NAME)


def clean(obj):
    if isinstance(obj, list):
        return [clean(item) for item in obj]
    if isinstance(obj, dict):
        return {key: clean(item) for key, item in obj.items()}
    if isinstance(obj, Decimal):
        number = float(obj)
        return int(number) if number.is_integer() else number
    return obj


def build_response(status, body):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "GET,OPTIONS",
        },
        "body": json.dumps(body),
    }


def latest_by_sensor(items):
    latest = {}
    for item in items:
        sensor_type = item.get("sensor_type")
        if sensor_type and sensor_type not in latest:
            latest[sensor_type] = item
    return list(latest.values())


def grouped_history(items):
    grouped = defaultdict(list)
    for item in items:
        snapshot_key = str(item.get("raw_timestamp") or item.get("timestamp", "")).split("#")[0]
        grouped[snapshot_key].append(item)
    return [grouped[key] for key in sorted(grouped.keys())]


def lambda_handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return build_response(200, {"message": "ok"})

    try:
        response = table.query(
            KeyConditionExpression=Key("elevator_id").eq(ELEVATOR_ID),
            ScanIndexForward=False,
            Limit=120,
        )
        items = clean(response.get("Items", []))

        return build_response(
            200,
            {
                "latest": latest_by_sensor(items),
                "history": grouped_history(items),
            },
        )
    except Exception as exc:
        print(f"Error retrieving data: {exc}")
        return build_response(500, {"error": str(exc)})

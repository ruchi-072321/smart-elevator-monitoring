import json
import os
import time

from runtime_bootstrap import ensure_local_site_packages

ensure_local_site_packages()

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_IOT_ENDPOINT = os.getenv("AWS_IOT_ENDPOINT")
AWS_IOT_TOPIC = os.getenv("AWS_IOT_TOPIC", "elevator/sensors")
DYNAMODB_TABLE = os.getenv("DYNAMODB_TABLE", "ElevatorSensorData")
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_SESSION_TOKEN = os.getenv("AWS_SESSION_TOKEN")
AWS_IOT_CLIENT_ID = os.getenv("AWS_IOT_CLIENT_ID", "ElevatorMonitorClient")
AWS_USE_MQTT = os.getenv("AWS_USE_MQTT", "true").lower() in ("1", "true", "yes")

MQTT_CLIENT = None


def make_boto_session():
    session_args = {"region_name": AWS_REGION}
    if AWS_ACCESS_KEY and AWS_SECRET_KEY:
        session_args.update({
            "aws_access_key_id": AWS_ACCESS_KEY,
            "aws_secret_access_key": AWS_SECRET_KEY,
        })
    if AWS_SESSION_TOKEN:
        session_args["aws_session_token"] = AWS_SESSION_TOKEN
    return boto3.Session(**session_args)


def resolve_iot_endpoint():
    global AWS_IOT_ENDPOINT
    if AWS_IOT_ENDPOINT:
        return AWS_IOT_ENDPOINT

    session = make_boto_session()
    iot = session.client("iot")
    response = iot.describe_endpoint(endpointType="iot:Data-ATS")
    AWS_IOT_ENDPOINT = response["endpointAddress"]
    print(f"Resolved AWS IoT endpoint: {AWS_IOT_ENDPOINT}")
    return AWS_IOT_ENDPOINT


def get_iot_client():
    endpoint = resolve_iot_endpoint()
    session = make_boto_session()
    return session.client("iot-data", endpoint_url=f"https://{endpoint}")


def get_dynamo_resource():
    session = make_boto_session()
    return session.resource("dynamodb")


def get_mqtt_client():
    global MQTT_CLIENT
    if MQTT_CLIENT is not None:
        return MQTT_CLIENT

    endpoint = resolve_iot_endpoint()
    try:
        from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
    except ImportError as exc:
        raise RuntimeError(
            "AWSIoTPythonSDK package is required for MQTT support. Install it with `pip install AWSIoTPythonSDK`."
        ) from exc

    client = AWSIoTMQTTClient(AWS_IOT_CLIENT_ID, useWebsocket=True)
    client.configureEndpoint(endpoint, 443)
    client.configureIAMCredentials(AWS_ACCESS_KEY, AWS_SECRET_KEY, AWS_SESSION_TOKEN)
    client.configureOfflinePublishQueueing(-1)
    client.configureDrainingFrequency(2)
    client.configureConnectDisconnectTimeout(10)
    client.configureMQTTOperationTimeout(5)
    client.connect()
    MQTT_CLIENT = client
    return client


def ensure_dynamo_table_exists():
    dynamo = get_dynamo_resource()
    existing_tables = [table.name for table in dynamo.tables.all()]
    if DYNAMODB_TABLE not in existing_tables:
        print(f"Creating DynamoDB table {DYNAMODB_TABLE}...")
        try:
            table = dynamo.create_table(
                TableName=DYNAMODB_TABLE,
                KeySchema=[
                    {"AttributeName": "elevator_id", "KeyType": "HASH"},
                    {"AttributeName": "timestamp", "KeyType": "RANGE"}
                ],
                AttributeDefinitions=[
                    {"AttributeName": "elevator_id", "AttributeType": "S"},
                    {"AttributeName": "timestamp", "AttributeType": "S"}
                ],
                BillingMode="PAY_PER_REQUEST"
            )
            table.meta.client.get_waiter("table_exists").wait(TableName=DYNAMODB_TABLE)
            print("DynamoDB table created.")
        except ClientError as exc:
            raise RuntimeError(f"Unable to create DynamoDB table: {exc}")
    return dynamo.Table(DYNAMODB_TABLE)


def publish_to_iot(data):
    payload = json.dumps(data)
    if AWS_USE_MQTT:
        client = get_mqtt_client()
        client.publish(AWS_IOT_TOPIC, payload, 0)
        print(f"Published sensor data to AWS IoT topic {AWS_IOT_TOPIC} via MQTT")
        return

    client = get_iot_client()
    try:
        client.publish(topic=AWS_IOT_TOPIC, qos=0, payload=payload)
        print(f"Published sensor data to AWS IoT topic {AWS_IOT_TOPIC}")
    except ClientError as exc:
        raise RuntimeError(f"AWS IoT publish error: {exc}")


def store_to_dynamo(data):
    table = ensure_dynamo_table_exists()
    item = {
        "elevator_id": data["elevator_id"],
        "timestamp": str(data["timestamp"]),
        "people_count": str(data.get("people_count", "0")),
        "temperature": str(data.get("temperature", "0")),
        "vibration": str(data.get("vibration", "0")),
        "door_status": data.get("door_status", "unknown"),
        "weight": str(data.get("weight", "0")),
        "status": data.get("status", "NORMAL"),
        "alerts": data.get("alerts", []),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }
    try:
        table.put_item(Item=item)
        print(f"Stored sensor data in DynamoDB table {DYNAMODB_TABLE}")
    except ClientError as exc:
        raise RuntimeError(f"DynamoDB write error: {exc}")

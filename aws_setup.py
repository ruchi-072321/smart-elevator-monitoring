import os
import time
from pathlib import Path

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_IOT_ENDPOINT = os.getenv("AWS_IOT_ENDPOINT")
DYNAMODB_TABLE = os.getenv("DYNAMODB_TABLE", "ElevatorSensorData")
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_SESSION_TOKEN = os.getenv("AWS_SESSION_TOKEN")


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
        print(f"Using AWS IoT endpoint from .env: {AWS_IOT_ENDPOINT}")
        return AWS_IOT_ENDPOINT

    session = make_boto_session()
    iot = session.client("iot")
    response = iot.describe_endpoint(endpointType="iot:Data-ATS")
    AWS_IOT_ENDPOINT = response["endpointAddress"]
    print(f"Resolved AWS IoT endpoint: {AWS_IOT_ENDPOINT}")
    return AWS_IOT_ENDPOINT


def ensure_dynamo_table_exists():
    session = make_boto_session()
    dynamo = session.resource("dynamodb")
    existing_tables = [table.name for table in dynamo.tables.all()]
    if DYNAMODB_TABLE in existing_tables:
        print(f"DynamoDB table already exists: {DYNAMODB_TABLE}")
        return dynamo.Table(DYNAMODB_TABLE)

    print(f"Creating DynamoDB table: {DYNAMODB_TABLE}")
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
        return table
    except ClientError as exc:
        raise RuntimeError(f"Unable to create DynamoDB table: {exc}")


def main():
    print("AWS setup helper")
    print("------------------")
    print(f"AWS region: {AWS_REGION}")
    print(f"DynamoDB table: {DYNAMODB_TABLE}")

    endpoint = resolve_iot_endpoint()
    print(f"AWS IoT endpoint ready: {endpoint}")

    table = ensure_dynamo_table_exists()
    print(f"DynamoDB table status: {table.table_status}")
    print("Setup complete. Update .env with AWS_IOT_ENDPOINT if needed.")


if __name__ == "__main__":
    main()

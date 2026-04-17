import json
import os
import sys
import zipfile
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime_bootstrap import ensure_local_site_packages

ensure_local_site_packages()

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_IOT_TOPIC = os.getenv("AWS_IOT_TOPIC", "elevator/sensors")
DYNAMODB_TABLE = os.getenv("DYNAMODB_TABLE", "ElevatorSensorData")
SNS_TOPIC_ARN = os.getenv("SNS_TOPIC_ARN", "").strip()
ROLE_NAME = os.getenv("LAMBDA_ROLE_NAME", "ElevatorLambdaRole")
LAMBDA_ROLE_ARN = os.getenv("LAMBDA_ROLE_ARN", "").strip()
PROCESSOR_FUNCTION = os.getenv("PROCESSOR_LAMBDA_NAME", "elevator-sensor-processor")
GETTER_FUNCTION = os.getenv("GET_SENSOR_DATA_LAMBDA_NAME", "elevator-get-sensor-data")
IOT_RULE_NAME = os.getenv("IOT_RULE_NAME", "elevator_sensor_rule")

session = boto3.Session(region_name=AWS_REGION)
lambda_client = session.client("lambda")
iam_client = session.client("iam")
iot_client = session.client("iot")
dynamodb = session.resource("dynamodb")
sts_client = session.client("sts")

ROOT = Path(__file__).resolve().parents[1]

LAMBDA_FUNCTIONS = {
    PROCESSOR_FUNCTION: {
        "file": ROOT / "lambda" / "processor.py",
        "handler": "processor.lambda_handler",
        "timeout": 60,
        "memory": 256,
    },
    GETTER_FUNCTION: {
        "file": ROOT / "lambda" / "get_sensor_data.py",
        "handler": "get_sensor_data.lambda_handler",
        "timeout": 30,
        "memory": 128,
    },
}


def account_id():
    return sts_client.get_caller_identity()["Account"]


def ensure_table():
    existing_tables = [table.name for table in dynamodb.tables.all()]
    if DYNAMODB_TABLE in existing_tables:
        print(f"Using existing DynamoDB table: {DYNAMODB_TABLE}")
        return

    table = dynamodb.create_table(
        TableName=DYNAMODB_TABLE,
        KeySchema=[
            {"AttributeName": "elevator_id", "KeyType": "HASH"},
            {"AttributeName": "timestamp", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "elevator_id", "AttributeType": "S"},
            {"AttributeName": "timestamp", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    table.wait_until_exists()
    print(f"Created DynamoDB table: {DYNAMODB_TABLE}")


def ensure_role():
    if LAMBDA_ROLE_ARN:
        print(f"Using configured IAM role: {LAMBDA_ROLE_ARN}")
        return LAMBDA_ROLE_ARN

    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }
        ],
    }

    try:
        response = iam_client.create_role(
            RoleName=ROLE_NAME,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description="Role for elevator monitoring Lambda functions",
        )
        role_arn = response["Role"]["Arn"]
        print(f"Created IAM role: {ROLE_NAME}")
    except iam_client.exceptions.EntityAlreadyExistsException:
        role_arn = f"arn:aws:iam::{account_id()}:role/{ROLE_NAME}"
        print(f"Using existing IAM role: {ROLE_NAME}")

    for policy_arn in [
        "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
        "arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess",
        "arn:aws:iam::aws:policy/AmazonSNSFullAccess",
    ]:
        try:
            iam_client.attach_role_policy(RoleName=ROLE_NAME, PolicyArn=policy_arn)
        except ClientError as exc:
            print(f"Policy attach skipped for {policy_arn}: {exc}")

    return role_arn


def zip_function(file_path):
    zip_path = file_path.with_suffix(".zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(file_path, arcname=file_path.name)
        # Include runtime_bootstrap.py
        runtime_bootstrap = ROOT / "runtime_bootstrap.py"
        if runtime_bootstrap.exists():
            archive.write(runtime_bootstrap, arcname="runtime_bootstrap.py")
    return zip_path


def function_environment():
    variables = {
        "AWS_REGION": AWS_REGION,
        "DYNAMODB_TABLE": DYNAMODB_TABLE,
        "SNS_TOPIC_ARN": SNS_TOPIC_ARN,
        "ELEVATOR_ID": os.getenv("ELEVATOR_ID", "ELEVATOR_1"),
    }
    return {"Variables": variables}


def deploy_lambda(function_name, config, role_arn):
    zip_path = zip_function(config["file"])
    with open(zip_path, "rb") as file_handle:
        zip_content = file_handle.read()

    try:
        lambda_client.get_function(FunctionName=function_name)
        lambda_client.update_function_code(FunctionName=function_name, ZipFile=zip_content)
        lambda_client.update_function_configuration(
            FunctionName=function_name,
            Role=role_arn,
            Handler=config["handler"],
            Runtime="python3.11",
            Timeout=config["timeout"],
            MemorySize=config["memory"],
            Environment=function_environment(),
        )
        print(f"Updated Lambda function: {function_name}")
    except lambda_client.exceptions.ResourceNotFoundException:
        lambda_client.create_function(
            FunctionName=function_name,
            Runtime="python3.11",
            Role=role_arn,
            Handler=config["handler"],
            Code={"ZipFile": zip_content},
            Timeout=config["timeout"],
            MemorySize=config["memory"],
            Environment=function_environment(),
            Description=f"Elevator Monitoring - {function_name}",
        )
        print(f"Created Lambda function: {function_name}")
    finally:
        if zip_path.exists():
            zip_path.unlink()


def ensure_lambda_permission(function_name):
    statement_id = f"{IOT_RULE_NAME}-invoke"
    source_arn = f"arn:aws:iot:{AWS_REGION}:{account_id()}:rule/{IOT_RULE_NAME}"
    try:
        lambda_client.add_permission(
            FunctionName=function_name,
            StatementId=statement_id,
            Action="lambda:InvokeFunction",
            Principal="iot.amazonaws.com",
            SourceArn=source_arn,
        )
        print(f"Granted IoT invoke permission to {function_name}")
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ResourceConflictException":
            raise
        print(f"IoT invoke permission already exists for {function_name}")


def ensure_iot_rule():
    function_arn = lambda_client.get_function(FunctionName=PROCESSOR_FUNCTION)["Configuration"]["FunctionArn"]
    payload = {
        "sql": f"SELECT * FROM '{AWS_IOT_TOPIC}'",
        "actions": [{"lambda": {"functionArn": function_arn}}],
        "ruleDisabled": False,
        "awsIotSqlVersion": "2016-03-23",
        "description": "Routes elevator MQTT sensor data to the processor Lambda",
    }

    try:
        iot_client.get_topic_rule(ruleName=IOT_RULE_NAME)
        iot_client.replace_topic_rule(ruleName=IOT_RULE_NAME, topicRulePayload=payload)
        print(f"Updated IoT topic rule: {IOT_RULE_NAME}")
    except iot_client.exceptions.ResourceNotFoundException:
        iot_client.create_topic_rule(ruleName=IOT_RULE_NAME, topicRulePayload=payload)
        print(f"Created IoT topic rule: {IOT_RULE_NAME}")


def main():
    print("Preparing serverless elevator pipeline...")
    ensure_table()
    role_arn = ensure_role()

    for function_name, config in LAMBDA_FUNCTIONS.items():
        deploy_lambda(function_name, config, role_arn)

    ensure_lambda_permission(PROCESSOR_FUNCTION)
    ensure_iot_rule()
    print("Serverless deployment complete.")


if __name__ == "__main__":
    main()

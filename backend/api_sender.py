import boto3
import json
from dotenv import load_dotenv

load_dotenv()

def send_to_cloud(data):
    try:
        lambda_client = boto3.client('lambda', region_name='us-east-1')
        response = lambda_client.invoke(
            FunctionName='elevator-sensor-processor',
            InvocationType='Event',
            Payload=json.dumps(data)
        )
        print(f"Invoked Lambda for sensor data: {data['sensor_type']}")
    except Exception as e:
        print(f"Warning: Failed to invoke Lambda for {data.get('sensor_type', 'unknown')}: {e}")

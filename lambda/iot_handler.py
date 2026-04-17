"""
AWS Lambda function triggered by IoT Core rule
Receives MQTT messages and processes them
"""

import json
import base64
import boto3
import hashlib
from datetime import datetime

# Initialize clients
lambda_client = boto3.client('lambda')
dynamodb = boto3.resource('dynamodb')
cloudwatch = boto3.client('cloudwatch')

def lambda_handler(event, context):
    """
    Triggered by IoT Core rule when elevator sensor data is received
    Invokes the processor Lambda function
    """
    try:
        # Decode the message payload
        if 'body' in event:
            payload = json.loads(base64.b64decode(event['body']))
        else:
            payload = event
        
        # Add metadata
        payload['received_at'] = datetime.utcnow().isoformat()
        payload['message_hash'] = hashlib.md5(
            json.dumps(payload, sort_keys=True).encode()
        ).hexdigest()
        
        # Invoke processor Lambda
        processor_response = invoke_processor(payload)
        
        # Log to CloudWatch
        log_metrics(payload)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Data received and queued for processing',
                'payload_id': payload['message_hash']
            })
        }
    
    except Exception as e:
        print(f"Error in IoT handler: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }


def invoke_processor(payload):
    """Invoke the processor Lambda function"""
    try:
        response = lambda_client.invoke(
            FunctionName='elevator-sensor-processor',
            InvocationType='Event',  # Async invocation
            Payload=json.dumps(payload)
        )
        return response
    except Exception as e:
        print(f"Error invoking processor: {str(e)}")
        raise


def log_metrics(payload):
    """Send metrics to CloudWatch"""
    try:
        sensor_type = payload.get('sensor_type')
        sensor_value = payload.get('sensor_value')
        
        cloudwatch.put_metric_data(
            Namespace='ElevatorMonitoring',
            MetricData=[
                {
                    'MetricName': f'Sensor_{sensor_type}',
                    'Value': sensor_value,
                    'Unit': 'None',
                    'Timestamp': datetime.utcnow(),
                    'Dimensions': [
                        {
                            'Name': 'elevator_id',
                            'Value': payload.get('elevator_id', 'ELEVATOR_1')
                        }
                    ]
                }
            ]
        )
    except Exception as e:
        print(f"Error logging metrics: {str(e)}")

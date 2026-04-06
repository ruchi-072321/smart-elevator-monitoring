import boto3
import json

# connect to AWS SQS
sqs = boto3.client('sqs', region_name='us-east-1')

QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/293552316702/elevator-sensor-queue"

def send_to_cloud(data):
    try:
        response = sqs.send_message(
            QueueUrl=QUEUE_URL,
            MessageBody=json.dumps(data)
        )

        print("Message sent to SQS")

    except Exception as e:
        print("Error sending message:", e)
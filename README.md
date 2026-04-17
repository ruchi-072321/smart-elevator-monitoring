# Smart Elevator Monitoring

## Setup

1. Create a local virtual environment:
   ```bash
   py -m venv .venv
   ```

2. Install Python dependencies:
   ```bash
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` and fill in AWS learner lab credentials:
   ```bash
   copy .env.example .env
   ```

4. Add your AWS session token and IoT endpoint in `.env`.
   - If you do not know the endpoint, run `py aws_setup.py` and it will resolve the endpoint for you.

## AWS env vars

- `AWS_REGION`
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_SESSION_TOKEN`
- `AWS_IOT_ENDPOINT`
- `AWS_IOT_TOPIC`
- `AWS_IOT_CLIENT_ID`
- `AWS_USE_MQTT`
- `DYNAMODB_TABLE`
- `DASHBOARD_DATA_SOURCE`
- `PROCESSOR_LAMBDA_NAME`
- `GET_SENSOR_DATA_LAMBDA_NAME`
- `IOT_RULE_NAME`
- `LAMBDA_ROLE_ARN`

## Running

- Deploy the serverless AWS resources:
  ```bash
  .\.venv\Scripts\python.exe lambda\deploy.py
  ```

- Start the simulator, fog layer, MQTT publisher, and local dashboard API:
  ```bash
  .\.venv\Scripts\python.exe main.py
  ```

- Open the dashboard in your browser:
  ```bash
  http://localhost:5000
  ```

The runtime flow is:
`sensor simulator -> fog processing -> AWS IoT MQTT -> Lambda -> DynamoDB -> Flask dashboard`

The Flask API server and dashboard run together from `main.py`, so there is no separate `http.server` step anymore.

The Lambda deployment script creates or reuses the DynamoDB table, deploys the Lambda functions, and updates the IoT rule for the configured MQTT topic.

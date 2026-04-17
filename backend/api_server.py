import os
from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from runtime_bootstrap import ensure_local_site_packages

ensure_local_site_packages()

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from boto3.dynamodb.conditions import Attr, Key
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template
from flask_cors import CORS

from backend.data_store import get_latest_sensor_data, get_sensor_history

load_dotenv()

app = Flask(
    __name__,
    static_folder="../dashboard/static",
    static_url_path="/static",
    template_folder="../dashboard/templates",
)
application = app
CORS(app)

SENSOR_CONFIG = {
    "temperature": {"label": "Temperature", "unit": "C"},
    "vibration": {"label": "Vibration", "unit": "g"},
    "weight": {"label": "Weight", "unit": "kg"},
    "people_count": {"label": "People Count", "unit": "people"},
    "door_status": {"label": "Door Status", "unit": ""},
}
SENSOR_ORDER = ["temperature", "vibration", "weight", "people_count"]
DYNAMODB_TABLE = os.getenv("DYNAMODB_TABLE", "ElevatorSensorData")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_SESSION_TOKEN = os.getenv("AWS_SESSION_TOKEN")
DASHBOARD_DATA_SOURCE = os.getenv("DASHBOARD_DATA_SOURCE", "dynamodb").lower()
DEFAULT_ELEVATOR_ID = os.getenv("ELEVATOR_ID", "ELEVATOR_1")
_DYNAMO_USE_SCAN_FOR_DASHBOARD = None


def _make_boto_session():
    session_args = {"region_name": AWS_REGION}
    if AWS_ACCESS_KEY and AWS_SECRET_KEY:
        session_args.update(
            {
                "aws_access_key_id": AWS_ACCESS_KEY,
                "aws_secret_access_key": AWS_SECRET_KEY,
            }
        )
    if AWS_SESSION_TOKEN:
        session_args["aws_session_token"] = AWS_SESSION_TOKEN
    return boto3.Session(**session_args)


def _clean(value):
    if isinstance(value, list):
        return [_clean(item) for item in value]
    if isinstance(value, dict):
        return {key: _clean(item) for key, item in value.items()}
    if isinstance(value, Decimal):
        number = float(value)
        return int(number) if number.is_integer() else number
    return value


def _normalize_number(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _derive_site_status(summary):
    if summary["critical"] > 0:
        return "CRITICAL"
    if summary["warning"] > 0:
        return "WARNING"
    return "NORMAL"


MAX_CHART_SAMPLES = 12
ONE_HOUR_MS = 60 * 60 * 1000


def _parse_timestamp(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _build_payload_from_snapshots(snapshots):
    cutoff_ms = int(datetime.utcnow().timestamp() * 1000) - ONE_HOUR_MS
    recent_snapshots = []

    for snapshot in snapshots:
        snapshot_ts = None
        for item in snapshot:
            if item is None:
                continue
            raw = item.get("raw_timestamp") or item.get("timestamp")
            parsed = _parse_timestamp(raw)
            if parsed is not None:
                snapshot_ts = max(snapshot_ts, parsed) if snapshot_ts is not None else parsed

        if snapshot_ts is None:
            continue
        if snapshot_ts < cutoff_ms:
            continue

        recent_snapshots.append((snapshot, snapshot_ts))

    recent_snapshots.sort(key=lambda tup: tup[1])
    snapshots = [snap for snap, _ in recent_snapshots][-MAX_CHART_SAMPLES:]
    latest_snapshot = snapshots[-1] if snapshots else []
    latest_map = {item.get("sensor_type"): item for item in latest_snapshot}

    encountered = []
    for snapshot in snapshots:
        for item in snapshot:
            if not item:
                continue
            sensor_type = item.get("sensor_type")
            if sensor_type and sensor_type not in encountered:
                encountered.append(sensor_type)

    all_sensor_types = [sensor for sensor in SENSOR_ORDER if sensor in encountered]
    all_sensor_types += [sensor for sensor in encountered if sensor not in all_sensor_types]

    summary = {
        "total_events": len(snapshots),
        "critical": 0,
        "warning": 0,
        "normal": 0,
        "active_sensors": len(latest_map),
    }
    charts = {}
    for sensor in all_sensor_types:
        config = SENSOR_CONFIG.get(sensor, {})
        charts[sensor] = {
            "label": config.get("label", sensor.replace("_", " ").title()),
            "unit": config.get("unit", ""),
            "labels": [],
            "values": [],
        }
    recent_alerts = []

    for snapshot in snapshots:
        row = {item.get("sensor_type"): item for item in snapshot}
        snapshot_timestamp = None
        snapshot_status = "NORMAL"

        for item in row.values():
            if item is None:
                continue
            raw = item.get("raw_timestamp") or item.get("timestamp")
            parsed = _parse_timestamp(raw)
            if parsed is None:
                continue
            snapshot_timestamp = max(snapshot_timestamp, parsed) if snapshot_timestamp is not None else parsed

        snapshot_label = snapshot_timestamp or ""

        for sensor in all_sensor_types:
            item = row.get(sensor)
            charts[sensor]["labels"].append(snapshot_label)
            charts[sensor]["values"].append(
                _normalize_number(item.get("sensor_value")) if item else None
            )

            if item:
                item_status = item.get("status", "NORMAL")
                if item_status == "CRITICAL":
                    snapshot_status = "CRITICAL"
                elif item_status == "WARNING" and snapshot_status != "CRITICAL":
                    snapshot_status = "WARNING"

                for alert in item.get("alerts", []):
                    recent_alerts.append(
                        {
                            "sensor_type": item.get("sensor_type"),
                            "message": alert,
                            "status": item_status,
                            "value": item.get("sensor_value"),
                            "unit": SENSOR_CONFIG.get(item.get("sensor_type"), {}).get("unit", ""),
                            "timestamp": item.get("raw_timestamp") or item.get("timestamp"),
                        }
                    )

        summary[snapshot_status.lower()] += 1

    for sensor in list(charts.keys()):
        if len(charts[sensor]["labels"]) > MAX_CHART_SAMPLES:
            charts[sensor]["labels"] = charts[sensor]["labels"][-MAX_CHART_SAMPLES:]
            charts[sensor]["values"] = charts[sensor]["values"][-MAX_CHART_SAMPLES:]

        if all(value is None for value in charts[sensor]["values"]):
            charts.pop(sensor, None)

    for sensor in list(all_sensor_types):
        if sensor not in charts or all(value is None for value in charts[sensor]["values"]):
            all_sensor_types.remove(sensor)
            charts.pop(sensor, None)

    sensor_cards = []
    for sensor in all_sensor_types:
        item = latest_map.get(sensor)
        if not item:
            continue
        config = SENSOR_CONFIG.get(sensor, {})
        sensor_cards.append(
            {
                "sensor_type": sensor,
                "label": config.get("label", sensor.replace("_", " ").title()),
                "value": item.get("sensor_value"),
                "unit": config.get("unit", ""),
                "status": item.get("status", "OFFLINE"),
                "message": ", ".join(item.get("alerts", [])) or "Operating normally",
                "timestamp": item.get("raw_timestamp") or item.get("timestamp"),
            }
        )

    return {
        "summary": summary,
        "site_status": _derive_site_status(summary),
        "sensor_cards": sensor_cards,
        "charts": charts,
        "recent_alerts": list(reversed(recent_alerts[-12:])),
        "recent_logs": list(reversed(list(latest_map.values()))),
    }


def _load_snapshots_from_memory():
    return get_sensor_history()


def _load_snapshots_from_dynamodb():
    global _DYNAMO_USE_SCAN_FOR_DASHBOARD
    session = _make_boto_session()
    table = session.resource("dynamodb").Table(DYNAMODB_TABLE)

    if _DYNAMO_USE_SCAN_FOR_DASHBOARD is None:
        use_scan = False
        try:
            key_names = {key["AttributeName"] for key in table.key_schema}
            if "elevator_id" not in key_names:
                print(
                    f"Dashboard table key schema does not contain elevator_id; using scan instead: {key_names}"
                )
                use_scan = True
        except Exception as exc:
            print(f"Failed to inspect DynamoDB key schema; will use scan: {exc}")
            use_scan = True
        _DYNAMO_USE_SCAN_FOR_DASHBOARD = use_scan
    else:
        use_scan = _DYNAMO_USE_SCAN_FOR_DASHBOARD

    if use_scan:
        response = table.scan(FilterExpression=Attr("elevator_id").eq(DEFAULT_ELEVATOR_ID))
        items = _clean(response.get("Items", []))

        if not items:
            print(
                "Dashboard scan with elevator_id returned no items. "
                "Retrying scan without elevator_id filter to support event_id-only DynamoDB tables."
            )
            response = table.scan(Limit=120)
            items = _clean(response.get("Items", []))
    else:
        try:
            response = table.query(
                KeyConditionExpression=Key("elevator_id").eq(DEFAULT_ELEVATOR_ID),
                ScanIndexForward=False,
                Limit=120,
            )
            items = _clean(response.get("Items", []))
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "ValidationException":
                print(f"Dashboard query failed, falling back to scan: {exc}")
                response = table.scan(FilterExpression=Attr("elevator_id").eq(DEFAULT_ELEVATOR_ID))
                items = _clean(response.get("Items", []))

                if not items:
                    print(
                        "Dashboard scan with elevator_id returned no items. "
                        "Retrying scan without elevator_id filter to support event_id-only DynamoDB tables."
                    )
                    response = table.scan(Limit=120)
                    items = _clean(response.get("Items", []))
            else:
                raise

    grouped = defaultdict(list)
    for item in items:
        ts = item.get("raw_timestamp") or item.get("timestamp")
        if not ts:
            continue
        
        ts_str = str(ts)
        if "#" in ts_str:
            snapshot_key = ts_str.split("#")[0]
        else:
            snapshot_key = ts_str
        
        grouped[snapshot_key].append(item)

    sorted_keys = sorted(grouped.keys())
    return [grouped[key] for key in sorted_keys]


def _get_latest_snapshot_timestamp(snapshots):
    latest_ts = None
    for snapshot in snapshots:
        for item in snapshot:
            if not item:
                continue
            raw = item.get("raw_timestamp") or item.get("timestamp")
            parsed = _parse_timestamp(raw)
            if parsed is None:
                continue
            latest_ts = max(latest_ts, parsed) if latest_ts is not None else parsed
    return latest_ts


def _build_dashboard_payload():
    try:
        memory_snapshots = _load_snapshots_from_memory()

        if memory_snapshots:
            latest_mem_ts = _get_latest_snapshot_timestamp(memory_snapshots)
            if latest_mem_ts is not None:
                age_ms = int(datetime.utcnow().timestamp() * 1000) - latest_mem_ts
                if age_ms <= 10000:
                    print(f"Dashboard using fresh memory data (age: {age_ms}ms)")
                    return _build_payload_from_snapshots(memory_snapshots)

        dynamo_snapshots = _load_snapshots_from_dynamodb()
        if dynamo_snapshots:
            return _build_payload_from_snapshots(dynamo_snapshots)

        if memory_snapshots:
            print("Dashboard using fallback memory data")
            return _build_payload_from_snapshots(memory_snapshots)

    except (ClientError, BotoCoreError, KeyError, ValueError) as exc:
        print(f"Dashboard data loader failed: {exc}")

    return _build_payload_from_snapshots([])


@app.route("/get-elevator-data")
def get_elevator_data():
    payload = _build_dashboard_payload()
    latest = payload["recent_logs"]
    return jsonify(latest)


@app.route("/api/dashboard")
def dashboard_data():
    return jsonify(_build_dashboard_payload())


@app.route("/")
def serve_dashboard():
    return render_template("index.html")


def run_server(port=5000):
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

from collections import deque
from copy import deepcopy
from threading import Lock

HISTORY_LIMIT = 240

_latest_sensor_data = {}
_history = deque(maxlen=HISTORY_LIMIT)
_lock = Lock()


def set_latest_sensor_data(sensor_data_list):
    with _lock:
        snapshot = []
        for data in sensor_data_list:
            if not data:
                continue
            record = deepcopy(data)
            sensor_type = record.get("sensor_type")
            if sensor_type:
                _latest_sensor_data[sensor_type] = record
                snapshot.append(record)

        if snapshot:
            _history.append(snapshot)
            if len(_history) > HISTORY_LIMIT:
                print(f"Data store history limit reached: {len(_history)} snapshots")


def get_latest_sensor_data():
    with _lock:
        return [deepcopy(item) for item in _latest_sensor_data.values()]


def get_sensor_history():
    with _lock:
        return deepcopy(list(_history))

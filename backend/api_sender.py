import requests

# temporary test URL
API_URL = "http://example.com"

def send_to_cloud(data):
    try:
        response = requests.post(API_URL, json=data)
        print("Cloud response:", response.status_code)
    except Exception as e:
        print("Error sending data:", e)
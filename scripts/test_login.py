import requests
import json

base = "http://127.0.0.1:12306"
r = requests.post(f'{base}/admin/api/login', json={'username': 'admin', 'password': 'admin123'}, timeout=10)
print(f"Status: {r.status_code}")
print(f"Response: {r.text}")
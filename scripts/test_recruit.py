import requests

base = "http://127.0.0.1:12306"

r = requests.post(f'{base}/admin/api/login', json={'username': 'admin', 'password': 'admin123'}, timeout=10)
token = r.json().get('token', '')
headers = {'Authorization': f'Bearer {token}'}

# 测试招生团队列表
print("=== 测试招生团队列表 ===")
r2 = requests.get(f'{base}/admin/api/recruit-teams', headers=headers, timeout=10)
print(f"Status: {r2.status_code}")
print(f"Response: {r2.text}")
import requests

base = "http://127.0.0.1:12306"

r = requests.post(f'{base}/admin/api/login', json={'username': 'admin', 'password': 'admin123'}, timeout=10)
token = r.json().get('token', '')
headers = {'Authorization': f'Bearer {token}'}

# 测试场次报告缓存 (使用 /api 前缀，不是 /admin/api)
print("=== 测试场次报告缓存 ===")
r2 = requests.get(f'{base}/api/reports/session/2', headers=headers, timeout=10)
print(f"Status: {r2.status_code}")
print(f"Response: {r2.text[:500]}")

# 测试生成报告
print("\n=== 生成场次报告 ===")
r3 = requests.post(f'{base}/api/reports/session/2/generate', headers=headers, timeout=120)
print(f"Status: {r3.status_code}")
print(f"Response: {r3.text[:500]}")
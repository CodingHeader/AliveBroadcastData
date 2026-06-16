import requests

base = "http://127.0.0.1:12306"

# 1. 先登录获取token
r = requests.post(f'{base}/admin/api/login', json={'username': 'admin', 'password': 'admin123'}, timeout=10)
print(f"Login: {r.status_code} - {r.text[:200]}")
if r.status_code != 200:
    exit(1)

token = r.json().get('token', '')
headers = {'Authorization': f'Bearer {token}'}

# 2. 测试薪酬计算API - anchor-salary-stats
r2 = requests.get(f'{base}/admin/api/anchor-salary-stats?date_from=2026-06-01&date_to=2026-06-30', headers=headers, timeout=10)
print(f"\n=== anchor-salary-stats ===")
print(f"Status: {r2.status_code}")
print(f"Response: {r2.text[:500]}")

# 3. 测试主播列表API
r3 = requests.get(f'{base}/admin/api/anchors', headers=headers, timeout=10)
print(f"\n=== anchors ===")
print(f"Status: {r3.status_code}")
print(f"Response: {r3.text[:500]}")

# 4. 测试主播统计API - comprehensive
r4 = requests.get(f'{base}/admin/api/anchor-stats/comprehensive?date_from=2026-06-01&date_to=2026-06-30', headers=headers, timeout=10)
print(f"\n=== anchor-stats/comprehensive ===")
print(f"Status: {r4.status_code}")
print(f"Response: {r4.text[:500]}")
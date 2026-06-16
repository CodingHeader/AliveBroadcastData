import requests

base = "http://127.0.0.1:12306"

# 登录
r = requests.post(f'{base}/admin/api/login', json={'username': 'admin', 'password': 'admin123'}, timeout=10)
token = r.json().get('token', '')
headers = {'Authorization': f'Bearer {token}'}

# 测试几个路由
routes = [
    '/admin/api/anchors',
    '/admin/api/anchor-income-stats',
    '/admin/api/anchor-salary-stats',
    '/admin/api/anchor-stats/comprehensive',
    '/admin/api/schedule/bindings',
]

for route in routes:
    try:
        r = requests.get(f'{base}{route}', headers=headers, timeout=5)
        print(f"{route}: {r.status_code}")
    except Exception as e:
        print(f"{route}: ERROR - {e}")
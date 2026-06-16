import requests, json

base = 'http://127.0.0.1:12306'
s = requests.Session()
r = s.post(f'{base}/admin/api/login', json={'username': 'admin', 'password': 'admin123'})
token = r.json()['token']
print(f'Token: {token[:20]}...')

# Test anchor-income-stats
r = s.get(f'{base}/admin/api/anchor-income-stats?date_from=2026-06-09&date_to=2026-06-09',
          headers={'Authorization': f'Bearer {token}'}, timeout=15)
print(f'Status: {r.status_code}')
if r.status_code == 200:
    data = r.json()
    print(f'Code: {data["code"]}')
    print(f'Result count: {len(data.get("data",[]))}')
    print(f'Summary: {json.dumps(data.get("summary",{}), ensure_ascii=False)}')
    for item in data.get('data', [])[:5]:
        print(f'  anchor={item["anchor_name"]} period={item["session_period"]} hours={item["duration_hours"]} income={item["income"]}')
else:
    print(f'Error text: {r.text[:500]}')

# Test salary-calc
print('\n--- Salary Calc ---')
r = s.post(f'{base}/admin/api/anchor-stats/salary-calc',
           json={'anchor_id': 1, 'month': '2026-06', 'base_salary': 160, 'commission_per_lead': 30, 'ad_commission': 10, 'natural_commission': 5},
           headers={'Authorization': f'Bearer {token}'}, timeout=15)
print(f'Status: {r.status_code}')
if r.status_code == 200:
    data = r.json()
    print(f'Code: {data["code"]}')
    print(json.dumps(data.get('data', {}), indent=2, ensure_ascii=False)[:1000])
else:
    print(f'Error: {r.text[:500]}')

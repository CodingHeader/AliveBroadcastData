import requests, json

base = 'http://127.0.0.1:12306'
s = requests.Session()
r = s.post(f'{base}/admin/api/login', json={'username': 'admin', 'password': 'admin123'}, timeout=10)
token = r.json()['token']
print(f'Token OK: {token[:20]}...')

# Test anchor-income-stats
print('\n=== anchor-income-stats ===')
r = s.get(f'{base}/admin/api/anchor-income-stats?date_from=2026-06-09&date_to=2026-06-09',
          headers={'Authorization': f'Bearer {token}'}, timeout=10)
print(f'Status: {r.status_code}')
if r.status_code == 200:
    data = r.json()
    print(f'Result: {len(data.get("data",[]))} rows')
    print(f'Summary: {json.dumps(data.get("summary",{}), ensure_ascii=False)[:500]}')
    for item in data.get('data',[])[:3]:
        print(f'  {item["anchor_name"]} period={item["session_period"]} hours={item["duration_hours"]} income={item["income"]}')
else:
    print(f'Error: {r.text[:500]}')

# Test salary-calc
print('\n=== salary-calc ===')
r = s.post(f'{base}/admin/api/anchor-stats/salary-calc',
           json={'anchor_id': 1, 'month': '2026-06', 'base_salary': 160, 'commission_per_lead': 30,
                 'ad_commission': 10, 'natural_commission': 5},
           headers={'Authorization': f'Bearer {token}'}, timeout=15)
print(f'Status: {r.status_code}')
if r.status_code == 200:
    data = r.json()
    dd = data.get("daily_detail", [])
    da = data.get("daily_aggregated", [])
    ah = data.get("anchor_summary", [])
    print(f'Daily detail: {len(dd)} rows')
    print(f'Daily aggregated: {len(da)} rows')
    print(f'Anchor summary: {len(ah)} rows')
    print(f'Summary: {json.dumps(ah, ensure_ascii=False)[:1000]}')
else:
    print(f'Error: {r.text[:500]}')

# Also test the new get_comprehensive_stats via anchor-salary-stats
print('\n=== anchor-salary-stats (comprehensive) ===')
r = s.get(f'{base}/admin/api/anchor-salary-stats?date_from=2026-06-09&date_to=2026-06-09',
          headers={'Authorization': f'Bearer {token}'}, timeout=10)
print(f'Status: {r.status_code}')
if r.status_code == 200:
    data = r.json()
    print(f'daily_detail: {len(data.get("daily_detail",[]))} rows')
    print(f'anchor_summary: {len(data.get("anchor_summary",[]))} rows')
    print(f'overall_summary: {json.dumps(data.get("overall_summary",{}), ensure_ascii=False)[:300]}')
else:
    print(f'Error: {r.text[:500]}')

import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))
os.chdir(os.path.join(os.path.dirname(__file__), '..', 'server'))
os.environ['CONFIG_PATH'] = os.path.join(os.path.dirname(__file__), '..', 'server', 'config.py')

from sqlalchemy import create_engine
from sqlalchemy.orm import Session as SASession
from services.anchor_stats_service import get_comprehensive_stats, calc_anchor_salary

engine = create_engine('sqlite:///data.db', echo=False)
db = SASession(engine)

try:
    stats = get_comprehensive_stats(db, '2026-06-09', '2026-06-09')
    print(f'daily_detail: {len(stats["daily_detail"])} rows')
    print(f'anchor_summary: {len(stats["anchor_summary"])} rows')
    
    for anchor in stats['anchor_summary']:
        print(f'\n  Anchor {anchor["anchor_name"]}:')
        print(f'    total_hours={anchor["total_hours"]}, total_minutes={anchor["total_minutes"]}')
        print(f'    total_leads={anchor["total_leads"]}, ad_leads={anchor["ad_leads"]}, natural_leads={anchor["natural_leads"]}')
    
    # Try calc
    print('\n=== calc_anchor_salary ===')
    salaries = calc_anchor_salary(
        base_rate=40, lead_commission=30, ad_commission=10, natural_commission=5,
        anchor_summary=stats['anchor_summary']
    )
    print(f'Results: {json.dumps(salaries, ensure_ascii=False, default=str)[:800]}')
    
except Exception as e:
    import traceback
    traceback.print_exc()
finally:
    db.close()

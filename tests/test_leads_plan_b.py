import os, sys, tempfile

os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["DEFAULT_ADMIN_USERNAME"] = "admin"
os.environ["DEFAULT_ADMIN_PASSWORD"] = "test-admin-password"
os.environ["AI_API_KEY"] = "test-key"
os.environ["AI_BASE_URL"] = "https://api.openai.com/v1"
os.environ["AI_MODEL"] = "gpt-4o"

sys.path.insert(0, r"E:\\Code\\AliveBroadcastData\\server")

tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
tmp_db.close()
os.environ["DATABASE_URL"] = f"sqlite:///{tmp_db.name}"

from fastapi.testclient import TestClient
import main
from database import Base, engine, SessionLocal, init_db
from models import (
    Session, SessionMetric, Lead, Comment, HighIntentUser, Report,
    Anchor, SessionAnchor, Deal, Setting, SchedulePlan, ScheduleSlot,
    ScheduleBinding, RoomAccountBinding, ApiClue, ClueConfig, DashboardTab,
    TabAnalysis, RecruitTeam, RecruitEmployee, ClueAssignment, AdPlan,
    AdPlanSpend, PrivateMessage
)

client = TestClient(main.app)
init_db()

TABLES = [
    Session, SessionMetric, Lead, Comment, HighIntentUser, Report,
    Anchor, SessionAnchor, Deal, SchedulePlan, ScheduleSlot,
    ScheduleBinding, RoomAccountBinding, ApiClue, ClueConfig, DashboardTab,
    TabAnalysis, RecruitTeam, RecruitEmployee, ClueAssignment, AdPlan,
    AdPlanSpend, PrivateMessage,
]


def _login():
    resp = client.post("/admin/api/login", json={"username": "admin", "password": "test-admin-password"})
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


def _clean_db():
    db = SessionLocal()
    try:
        for table in TABLES:
            db.execute(table.__table__.delete())
        db.commit()
        init_db()
    finally:
        db.close()


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def _find_lead(phone, token):
    resp = client.get("/admin/api/leads", headers=_headers(token))
    assert resp.status_code == 200, resp.text
    for item in resp.json()["data"]["items"]:
        if item.get("phone_masked") == phone[-4:]:
            return item
    raise AssertionError(f"lead not found for {phone}")


def test_manual_clue_create_and_list():
    _clean_db()
    token = _login()
    payload = {"name": "测试用户", "phone": "74955953457", "weixin": "wx123", "message_time": "2026-07-15 10:00:00", "notes": "计划B测试"}
    resp = client.post("/admin/api/manual-clue", json=payload, headers=_headers(token))
    assert resp.status_code == 200, resp.text
    assert resp.json()["code"] == 0

    item = _find_lead(payload["phone"], token)
    assert item.get("weixin") == "wx123"
    assert item.get("lead_id")
    assert item.get("origin") == "leads"


def test_duplicate_deal_returns_400():
    _clean_db()
    token = _login()
    payload = {"name": "重复成单", "phone": "74955953457", "weixin": "wx456"}
    resp = client.post("/admin/api/manual-clue", json=payload, headers=_headers(token))
    assert resp.status_code == 200, resp.text
    item = _find_lead(payload["phone"], token)

    deal = {"lead_id": item["id"], "customer_name": "客户A", "amount": 100, "deal_time": "2026-07-15"}
    resp = client.post("/admin/api/deals", json=deal, headers=_headers(token))
    assert resp.status_code == 200, resp.text
    assert resp.json()["code"] == 0

    resp = client.post("/admin/api/deals", json=deal, headers=_headers(token))
    assert resp.status_code == 200, resp.text
    assert resp.json()["code"] == 400
    assert "请勿重复操作" in resp.json().get("message", "")


def test_cancel_deal_by_lead_id():
    _clean_db()
    token = _login()
    payload = {"name": "取消成单", "phone": "74955953457"}
    resp = client.post("/admin/api/manual-clue", json=payload, headers=_headers(token))
    assert resp.status_code == 200, resp.text
    item = _find_lead(payload["phone"], token)

    deal = {"lead_id": item["id"], "customer_name": "客户B", "amount": 200, "deal_time": "2026-07-15"}
    resp = client.post("/admin/api/deals", json=deal, headers=_headers(token))
    assert resp.status_code == 200, resp.text
    assert resp.json()["code"] == 0

    resp = client.delete(f"/admin/api/deals/by-lead/{item['lead_id']}", headers=_headers(token))
    assert resp.status_code == 200, resp.text
    assert resp.json()["code"] == 0


def test_assignment_lookup_for_string_lead_id():
    _clean_db()
    token = _login()
    payload = {"name": "分配查询", "phone": "74955953457"}
    resp = client.post("/admin/api/manual-clue", json=payload, headers=_headers(token))
    assert resp.status_code == 200, resp.text
    item = _find_lead(payload["phone"], token)

    resp = client.get(f"/admin/api/leads/{item['lead_id']}/assignment", headers=_headers(token))
    assert resp.status_code == 200, resp.text
    assert resp.json()["code"] == 0


def test_is_valid_filter_mapping():
    _clean_db()
    token = _login()
    phones = {
        True: "74955953401",
        False: "74955953402",
    }
    for is_valid in [True, False]:
        payload = {"name": f"有效性{is_valid}", "phone": phones[is_valid], "source": "manual"}
        resp = client.post("/admin/api/manual-clue", json=payload, headers=_headers(token))
        assert resp.status_code == 200, resp.text
        item = _find_lead(payload["phone"], token)
        lead_int_id = int(item["id"].split("_", 1)[1])
        put_resp = client.put(f"/admin/api/leads/{lead_int_id}", json={"is_valid": is_valid}, headers=_headers(token))
        assert put_resp.status_code == 200, put_resp.text

    resp = client.get("/admin/api/leads?is_valid=true", headers=_headers(token))
    assert resp.status_code == 200, resp.text
    items = resp.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["is_valid"] is True

    resp = client.get("/admin/api/leads?is_valid=false", headers=_headers(token))
    assert resp.status_code == 200, resp.text
    items = resp.json()["data"]["items"]
    false_item = next((x for x in items if x.get("phone_masked") == phones[False][-4:]), None)
    assert false_item is not None
    assert false_item["is_valid"] is False
    assert all(item["is_valid"] is not True for item in items)

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession
from database import get_db
from models import Setting, Deal, Lead, Anchor, SessionAnchor, Session
from auth import verify_password, create_token, get_current_admin, hash_password
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import json, os

router = APIRouter()

class LoginRequest(BaseModel): username: str; password: str
class DealCreate(BaseModel): session_id: Optional[int]=None; lead_id: Optional[int]=None; customer_name: str; amount: float; deal_time: str; employee: Optional[str]=None; notes: Optional[str]=None

@router.post("/login")
def login(req: LoginRequest, db: DBSession = Depends(get_db)):
    stored_username = db.query(Setting).filter(Setting.key == "admin_username").first()
    stored_password = db.query(Setting).filter(Setting.key == "admin_password").first()
    if not stored_username or req.username != stored_username.value: raise HTTPException(401, detail="账号或密码错误")
    if not verify_password(req.password, stored_password.value): raise HTTPException(401, detail="账号或密码错误")
    return {"code": 0, "token": create_token(req.username)}

@router.get("/settings")
def get_settings(admin=Depends(get_current_admin), db=Depends(get_db)):
    settings = db.query(Setting).all()
    result = {s.key: s.value for s in settings}
    for key in ['ai_api_key', 'email_password']:
        if key in result and result[key]: result[key] = result[key][:4] + '****'
    return {"code":0, "data": result}

@router.put("/settings")
def update_settings(data: dict, admin=Depends(get_current_admin), db=Depends(get_db)):
    for key, value in data.items():
        setting = db.query(Setting).filter(Setting.key == key).first()
        if setting: setting.value = str(value); setting.updated_at = datetime.now().isoformat()
        else: db.add(Setting(key=key, value=str(value)))
    db.commit(); return {"code":0}

@router.get("/deals")
def list_deals(page: int = 1, size: int = 20, admin=Depends(get_current_admin), db=Depends(get_db)):
    query = db.query(Deal).order_by(Deal.created_at.desc())
    total = query.count(); items = query.offset((page-1)*size).limit(size).all()
    return {"code":0, "data":{"items":[{"id":d.id,"customer_name":d.customer_name,"amount":d.amount,"deal_time":d.deal_time,"employee":d.employee,"lead_nickname":d.lead.nickname if d.lead else None,"lead_id":d.lead_id,"session_id":d.session_id} for d in items], "total":total}}

@router.post("/deals")
def create_deal(data: DealCreate, admin=Depends(get_current_admin), db=Depends(get_db)):
    if data.lead_id:
        lead = db.query(Lead).get(data.lead_id)
        if lead and lead.is_deal:
            return {"code": 400, "message": "该线索已标记成单"}
    deal = Deal(**data.model_dump()); db.add(deal)
    if data.lead_id:
        lead = db.query(Lead).get(data.lead_id)
        if lead: lead.is_deal = True
    db.commit(); return {"code":0, "deal_id": deal.id}

@router.delete("/deals/{id}")
def delete_deal(id: int, admin=Depends(get_current_admin), db=Depends(get_db)):
    deal = db.query(Deal).get(id)
    if not deal: raise HTTPException(404)
    if deal.lead_id:
        other = db.query(Deal).filter(Deal.lead_id == deal.lead_id, Deal.id != id).count()
        if other == 0:
            lead = db.query(Lead).get(deal.lead_id)
            if lead: lead.is_deal = False
    db.delete(deal); db.commit(); return {"code":0}

@router.get("/anchors")
def list_anchors(admin=Depends(get_current_admin), db=Depends(get_db)):
    anchors = db.query(Anchor).all()
    return {"code":0, "data":[{"id":a.id,"name":a.name} for a in anchors]}

@router.post("/anchors")
def create_anchor(data: dict, admin=Depends(get_current_admin), db=Depends(get_db)):
    anchor = Anchor(name=data["name"]); db.add(anchor); db.commit(); return {"code":0, "anchor_id": anchor.id}

@router.delete("/anchors/{id}")
def delete_anchor(id: int, admin=Depends(get_current_admin), db=Depends(get_db)):
    db.query(SessionAnchor).filter(SessionAnchor.anchor_id == id).delete()
    db.query(Anchor).filter(Anchor.id == id).delete(); db.commit(); return {"code":0}

@router.post("/sessions/{session_id}/anchors")
def bind_anchors(session_id: int, data: dict, admin=Depends(get_current_admin), db=Depends(get_db)):
    db.query(SessionAnchor).filter(SessionAnchor.session_id == session_id).delete()
    for aid in data.get("anchor_ids", []): db.add(SessionAnchor(session_id=session_id, anchor_id=aid))
    db.commit(); return {"code":0}

@router.post("/email/test")
def test_email(admin=Depends(get_current_admin), db=Depends(get_db)):
    from services.email_service import send_email, get_email_config
    try:
        config = get_email_config(db)
        if not config.get("email_receivers"):
            return {"code": 400, "message": "请先添加收件人"}
        html = f"""<html><body style="font-family:Arial,sans-serif;padding:20px;">
            <h2 style="color:#2563eb;">AliveBroadcastData - SMTP Test</h2>
            <p>邮件配置测试成功！</p>
            <p>发送时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <hr style="border:1px solid #e5e7eb;margin:20px 0;">
            <p style="color:#6b7280;font-size:12px;">AliveBroadcastData System</p>
        </body></html>"""
        send_email("【AliveBroadcastData】邮件配置测试", html, config, config["email_receivers"])
        return {"code": 0, "message": "测试邮件已发送"}
    except Exception as e:
        return {"code": 500, "message": f"发送失败: {str(e)}"}

@router.put("/settings/password")
def change_password(data: dict, admin=Depends(get_current_admin), db=Depends(get_db)):
    stored = db.query(Setting).filter(Setting.key == "admin_password").first()
    if not verify_password(data.get("old_password",""), stored.value): return {"code":400,"message":"原密码错误"}
    stored.value = hash_password(data["new_password"]); db.commit(); return {"code":0,"message":"密码修改成功"}

@router.get("/employee/stats")
def employee_stats(date_from: str = None, date_to: str = None, admin=Depends(get_current_admin), db=Depends(get_db)):
    from sqlalchemy import func
    query = db.query(Deal.employee, func.count(Deal.id).label('deal_count'), func.sum(Deal.amount).label('total_amount'))
    if date_from: query = query.filter(Deal.deal_time >= date_from)
    if date_to: query = query.filter(Deal.deal_time <= date_to)
    results = query.group_by(Deal.employee).all()
    return {"code":0, "data":[{"employee":r[0],"deal_count":r[1],"total_amount":float(r[2] or 0)} for r in results]}

@router.post("/sessions/{session_id}/analyze")
def manual_analyze(session_id: int, admin=Depends(get_current_admin), db=Depends(get_db)):
    from services.ai_service import analyze_session
    try:
        report_id = analyze_session(db, session_id)
        return {"code": 0, "message": "分析完成", "report_id": report_id}
    except Exception as e:
        return {"code": 500, "message": str(e)}

class LeadUpdate(BaseModel):
    tags: Optional[str] = None
    is_valid: Optional[bool] = None
    notes: Optional[str] = None
    assigned_employee: Optional[str] = None

class LeadBatchUpdate(BaseModel):
    lead_ids: list[int]
    tags: Optional[str] = None
    is_valid: Optional[bool] = None

@router.put("/leads/{lead_id}")
def update_lead(lead_id: int, data: LeadUpdate, admin=Depends(get_current_admin), db=Depends(get_db)):
    lead = db.query(Lead).get(lead_id)
    if not lead:
        raise HTTPException(404, detail="线索不存在")
    if data.tags is not None:
        lead.tags = data.tags
    if data.is_valid is not None:
        lead.is_valid = data.is_valid
    if data.assigned_employee is not None:
        lead.assigned_employee = data.assigned_employee
    db.commit()
    return {"code": 0, "message": "线索已更新"}

@router.post("/leads/batch")
def batch_update_leads(data: LeadBatchUpdate, admin=Depends(get_current_admin), db=Depends(get_db)):
    leads = db.query(Lead).filter(Lead.id.in_(data.lead_ids)).all()
    for lead in leads:
        if data.tags is not None:
            lead.tags = data.tags
        if data.is_valid is not None:
            lead.is_valid = data.is_valid
    db.commit()
    return {"code": 0, "message": f"已更新 {len(leads)} 条线索"}

@router.get("/leads")
def list_leads(session_id: int = None, page: int = 1, size: int = 20, admin=Depends(get_current_admin), db=Depends(get_db)):
    query = db.query(Lead).order_by(Lead.created_at.desc())
    if session_id:
        query = query.filter(Lead.session_id == session_id)
    total = query.count()
    items = query.offset((page-1)*size).limit(size).all()
    return {"code": 0, "data": {"items": [{"id": l.id, "session_id": l.session_id, "lead_time": l.lead_time, "nickname": l.nickname, "city": l.city, "path": l.path, "tags": l.tags, "is_valid": l.is_valid, "is_deal": l.is_deal, "ad_account": l.ad_account} for l in items], "total": total}}

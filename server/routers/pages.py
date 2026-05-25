from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from templates_config import templates

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@router.get("/session/{session_id}", response_class=HTMLResponse)
async def session_detail(request: Request, session_id: int):
    return templates.TemplateResponse("session_detail.html", {"request": request, "session_id": session_id})

@router.get("/reports", response_class=HTMLResponse)
async def reports(request: Request):
    return templates.TemplateResponse("reports.html", {"request": request})

@router.get("/trends", response_class=HTMLResponse)
async def trends(request: Request):
    return templates.TemplateResponse("trends.html", {"request": request})

@router.get("/leads", response_class=HTMLResponse)
async def leads(request: Request):
    return templates.TemplateResponse("leads.html", {"request": request})

from fastapi.responses import RedirectResponse

@router.get("/admin")
async def admin_index():
    return RedirectResponse(url="/admin/deals")

@router.get("/admin/login", response_class=HTMLResponse)
async def admin_login(request: Request):
    return templates.TemplateResponse("admin/login.html", {"request": request})

@router.get("/admin/deals", response_class=HTMLResponse)
async def admin_deals(request: Request):
    return templates.TemplateResponse("admin/deals.html", {"request": request})

@router.get("/admin/anchors", response_class=HTMLResponse)
async def admin_anchors(request: Request):
    return templates.TemplateResponse("admin/anchors.html", {"request": request})

@router.get("/admin/ai", response_class=HTMLResponse)
async def admin_ai(request: Request):
    return templates.TemplateResponse("admin/ai_config.html", {"request": request})

@router.get("/admin/email", response_class=HTMLResponse)
async def admin_email(request: Request):
    return templates.TemplateResponse("admin/email_config.html", {"request": request})

@router.get("/admin/settings", response_class=HTMLResponse)
async def admin_settings(request: Request):
    return templates.TemplateResponse("admin/settings.html", {"request": request})

@router.get("/admin/leads", response_class=HTMLResponse)
async def admin_leads(request: Request):
    return templates.TemplateResponse("admin/leads.html", {"request": request})

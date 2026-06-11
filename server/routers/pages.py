from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
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

@router.get("/admin/schedules", response_class=HTMLResponse)
async def admin_schedules(request: Request):
    return templates.TemplateResponse("admin/schedules.html", {"request": request})

@router.get("/admin/schedule-calendar", response_class=HTMLResponse)
async def admin_schedule_calendar(request: Request):
    return templates.TemplateResponse("admin/schedule_calendar.html", {"request": request})

@router.get("/admin/schedule-log", response_class=HTMLResponse)
async def admin_schedule_log(request: Request):
    return templates.TemplateResponse("admin/schedule_log.html", {"request": request})

@router.get("/admin/ad-accounts", response_class=HTMLResponse)
async def admin_ad_accounts(request: Request):
    return templates.TemplateResponse("admin/ad_accounts.html", {"request": request})

@router.get("/admin/dashboard-tabs", response_class=HTMLResponse)
async def admin_dashboard_tabs(request: Request):
    return templates.TemplateResponse("admin/dashboard_tabs.html", {"request": request})

@router.get("/admin/clue-configs", response_class=HTMLResponse)
async def admin_clue_configs(request: Request):
    return templates.TemplateResponse("admin/clue_configs.html", {"request": request})

@router.get("/admin/recruit-teams", response_class=HTMLResponse)
async def admin_recruit_teams(request: Request):
    return templates.TemplateResponse("admin/recruit_teams.html", {"request": request})

@router.get("/clue-board", response_class=HTMLResponse)
async def clue_board(request: Request):
    return templates.TemplateResponse("clue_board.html", {"request": request})

@router.get("/anchor-stats", response_class=HTMLResponse)
async def anchor_stats_page(request: Request):
    return templates.TemplateResponse("anchor_stats.html", {"request": request})

@router.get("/admin/ad-plans", response_class=HTMLResponse)
async def admin_ad_plans(request: Request):
    return templates.TemplateResponse("admin/ad_plans.html", {"request": request})

@router.get("/admin/anchor-income", response_class=HTMLResponse)
async def admin_anchor_income(request: Request):
    return templates.TemplateResponse("admin/anchor_income.html", {"request": request})

@router.get("/admin/anchor-salary", response_class=HTMLResponse)
async def admin_anchor_salary(request: Request):
    return templates.TemplateResponse("admin/anchor_salary.html", {"request": request})

@router.get("/admin/poll-logs", response_class=HTMLResponse)
async def admin_poll_logs(request: Request):
    return templates.TemplateResponse("admin/poll_logs.html", {"request": request})

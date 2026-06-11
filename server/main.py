from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from pathlib import Path
from database import init_db
import logging, traceback

BASE_DIR = Path(__file__).resolve().parent

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    try:
        from services.scheduler import start_scheduler
        start_scheduler()
    except Exception as e:
        print(f"Scheduler init warning: {e}")
    yield
    try:
        from services.scheduler import stop_scheduler
        stop_scheduler()
    except Exception:
        pass

app = FastAPI(title="AliveBroadcastData", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

from routers import api, admin, pages
app.include_router(api.router, prefix="/api", tags=["前台API"])
app.include_router(admin.router, prefix="/admin/api", tags=["后台API"])
app.include_router(pages.router, tags=["页面"])

# ===== 全局异常处理 =====
logger = logging.getLogger(__name__)

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.status_code, "message": exc.detail}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}\n{traceback.format_exc()}")
    return JSONResponse(
        status_code=500,
        content={"code": 500, "message": "服务器内部错误，请稍后重试"}
    )

if __name__ == "__main__":
    import uvicorn
    from config import HOST, PORT
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)

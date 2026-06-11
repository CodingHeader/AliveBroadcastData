import os
from pathlib import Path
import logging

# 项目路径
BASE_DIR = Path(__file__).resolve().parent

# 数据库
DATABASE_URL = f"sqlite:///{BASE_DIR / 'data.db'}"

# JWT认证
SECRET_KEY = os.getenv("SECRET_KEY", "alive-broadcast-data-secret-key-2026")
TOKEN_EXPIRE_DAYS = 7
ALGORITHM = "HS256"

# 默认管理员
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin123"

# 服务器
HOST = "0.0.0.0"
PORT = 12306

# 日志
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

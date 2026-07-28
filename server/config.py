import os
from pathlib import Path
import logging

# 项目路径
BASE_DIR = Path(__file__).resolve().parent

# 数据库
DATABASE_URL = f"sqlite:///{BASE_DIR / 'data.db'}"


# JWT认证
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("请设置 SECRET_KEY 环境变量")
TOKEN_EXPIRE_DAYS = 7
ALGORITHM = "HS256"

# 默认管理员
DEFAULT_ADMIN_USERNAME = os.getenv("DEFAULT_ADMIN_USERNAME", "admin")
DEFAULT_ADMIN_PASSWORD = os.getenv("DEFAULT_ADMIN_PASSWORD")
if not DEFAULT_ADMIN_PASSWORD:
    raise RuntimeError("请设置 DEFAULT_ADMIN_PASSWORD 环境变量")

# 服务器
HOST = "0.0.0.0"
PORT = 12306

# 日志
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

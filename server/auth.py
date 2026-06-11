from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
import bcrypt as _bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from config import SECRET_KEY, ALGORITHM, TOKEN_EXPIRE_DAYS

security = HTTPBearer()

def hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode('utf-8'), _bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_token(username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRE_DAYS)
    payload = {"sub": username, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str) -> str:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="无效Token")
        return username
    except JWTError:
        raise HTTPException(status_code=401, detail="Token过期或无效")

async def get_current_admin(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    return verify_token(credentials.credentials)

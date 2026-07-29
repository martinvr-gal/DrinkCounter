from datetime import datetime, timedelta, timezone
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from .config import get_settings
security = HTTPBearer()
def create_token(subject: str) -> str:
    s = get_settings(); return jwt.encode({"sub": subject, "exp": datetime.now(timezone.utc)+timedelta(hours=12)}, s.jwt_secret, algorithm="HS256")
def admin_required(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    try: return jwt.decode(credentials.credentials, get_settings().jwt_secret, algorithms=["HS256"])["sub"]
    except jwt.PyJWTError: raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido o caducado")

from fastapi import HTTPException, Header, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from .config import get_settings

security = HTTPBearer(auto_error=False)


async def verify_api_key(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
) -> str:
    """Accept auth via Bearer token OR X-API-Key header."""
    settings = get_settings()
    token: Optional[str] = None

    if credentials:
        token = credentials.credentials
    elif x_api_key:
        token = x_api_key

    if not token or token != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token

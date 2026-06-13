"""
Dependências compartilhadas dos routers FastAPI.
"""

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

_bearer = HTTPBearer(auto_error=True)


def get_current_user_id(
    cred: HTTPAuthorizationCredentials = Depends(_bearer),
) -> str:
    """Extrai e valida o user_id do token JWT Bearer. Levanta 401 se inválido."""
    try:
        payload = jwt.decode(
            cred.credentials,
            settings.jwt_secret,
            algorithms=["HS256"],
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="token invalido")
    return payload["sub"]

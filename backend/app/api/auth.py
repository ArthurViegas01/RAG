"""
Endpoint de autenticação anônima: emite tokens JWT assinados server-side.

Estratégia de migração: o cliente pode fornecer um user_id existente (UUID
armazenado em localStorage antes da implantação do JWT) para reivindicar a
identidade histórica. Após a janela de migração, remover o campo user_id
do body para só emitir tokens para novas identidades.
"""

import time
from uuid import uuid4

import jwt
from fastapi import APIRouter
from pydantic import BaseModel

from app.config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])

_TOKEN_TTL = 365 * 24 * 3600  # 1 ano para tokens anônimos


class TokenRequest(BaseModel):
    user_id: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str


@router.post("/token", response_model=TokenResponse)
async def issue_token(body: TokenRequest = None) -> TokenResponse:
    """
    Emite um JWT assinado com HS256.

    - Se user_id for fornecido, emite token para esse ID (migração de sessões
      antigas armazenadas em localStorage).
    - Se não for fornecido, gera um novo UUID como identidade anônima.

    O token não pode ser forjado sem o JWT_SECRET do servidor.
    """
    if body is None:
        body = TokenRequest()
    uid = body.user_id or str(uuid4())
    now = int(time.time())
    payload = {"sub": uid, "iat": now, "exp": now + _TOKEN_TTL}
    token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    return TokenResponse(access_token=token, user_id=uid)

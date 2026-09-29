"""
JWT token creation and decoding using PyJWT.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt

from app.config import settings

ALGORITHM = "HS256"
ACCESS_TTL = timedelta(hours=8)
REFRESH_TTL = timedelta(days=14)


def _secret() -> str:
    return settings.SECRET_KEY or settings.ENCRYPTION_KEY


def create_token(
    subject: str,
    token_type: str = "access",
    extra: Optional[Dict[str, Any]] = None,
) -> str:
    now = datetime.now(timezone.utc)
    ttl = ACCESS_TTL if token_type == "access" else REFRESH_TTL
    payload: Dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + ttl,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, _secret(), algorithm=ALGORITHM)


def decode_token(token: str) -> Dict[str, Any]:
    return jwt.decode(token, _secret(), algorithms=[ALGORITHM])

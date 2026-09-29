from fastapi import HTTPException
from sqlalchemy import select

from app.core.audit import record_audit
from app.core.jwt import create_token, decode_token
from app.core.security import verify_password
from app.database import async_session_factory
from app.models.user import Role, User


async def authenticate(username: str, password: str) -> dict:
    async with async_session_factory() as session:
        user = (
            await session.execute(select(User).where(User.username == username))
        ).scalar_one_or_none()
        if not user or not verify_password(password, user.password_hash):
            await record_audit(
                "LOGIN_FAILED",
                "user",
                username,
                actor=username,
                details={"reason": "invalid_credentials"},
            )
            raise HTTPException(status_code=401, detail="Invalid username or password")
        role = await session.get(Role, user.role_id)
        role_name = role.name if role else None
        await record_audit(
            "LOGIN",
            "user",
            username,
            actor=username,
            details={"role": role_name},
        )
        return {
            "access_token": create_token(
                user.username, "access", {"role": role_name}
            ),
            "refresh_token": create_token(
                user.username, "refresh", {"role": role_name}
            ),
            "user": {
                "id": user.id,
                "username": user.username,
                "full_name": user.full_name,
                "role": role_name,
            },
        }


async def refresh_access(refresh_token: str) -> dict:
    try:
        payload = decode_token(refresh_token)
    except Exception:
        await record_audit("REFRESH_FAILED", "token", actor="unknown")
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    if payload.get("type") != "refresh":
        await record_audit("REFRESH_FAILED", "token", actor=payload.get("sub"))
        raise HTTPException(status_code=401, detail="Not a refresh token")
    await record_audit("REFRESH", "token", actor=payload.get("sub"))
    return {
        "access_token": create_token(
            payload["sub"], "access", {"role": payload.get("role")}
        ),
        "token_type": "bearer",
    }

"""
Role-based access control: permission matrix, current-user dependency,
and permission guards.
"""

from typing import Dict, List

import jwt as pyjwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select

from app.core.jwt import decode_token
from app.database import async_session_factory
from app.models.user import Role, User

PERMISSIONS: Dict[str, List[str]] = {
    "administrator": ["*"],
    "operator": [
        "bills:*", "payments:*", "automation:*",
        "search:read", "dashboard:read", "stock:read",
        "farmers:read", "farmers:write", "traders:read", "traders:write",
        "masterdata:read", "masterdata:write",
    ],
    "accountant": [
        "bills:read", "payments:*", "reports:read",
        "search:read", "dashboard:read", "settings:read", "audit:read",
        "farmers:read", "traders:read", "masterdata:read",
    ],
    "inspector": [
        "search:read", "dashboard:read", "bills:read", "payments:read",
        "reports:read", "audit:read", "stock:read", "notifications:read",
        "settings:read", "farmers:read", "traders:read", "masterdata:read",
    ],
}


def role_permissions(role: str) -> List[str]:
    return PERMISSIONS.get(role, [])


def has_permission(role: str, permission: str) -> bool:
    perms = role_permissions(role)
    if "*" in perms:
        return True
    if permission in perms:
        return True
    return permission.split(":")[0] + ":*" in perms


async def get_current_user(request: Request) -> Dict[str, object]:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = auth.split(" ", 1)[1]
    try:
        payload = decode_token(token)
    except pyjwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Not an access token")
    username = payload.get("sub")
    async with async_session_factory() as session:
        user = (
            await session.execute(select(User).where(User.username == username))
        ).scalar_one_or_none()
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="User not found or inactive")
        role = await session.get(Role, user.role_id)
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "role": role.name if role else None,
    }


def require_permission(permission: str):
    async def checker(user: dict = Depends(get_current_user)) -> dict:
        if not has_permission(user.get("role") or "", permission):
            raise HTTPException(
                status_code=403, detail=f"Missing permission: {permission}"
            )
        return user

    return checker

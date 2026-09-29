from fastapi import APIRouter, Depends

from app.core.rbac import get_current_user
from app.domain.auth.schemas import LoginRequest, RefreshRequest, TokenResponse, UserOut
from app.domain.auth.service import authenticate, refresh_access

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest) -> dict:
    return await authenticate(payload.username, payload.password)


@router.post("/refresh", response_model=dict)
async def refresh(payload: RefreshRequest) -> dict:
    return await refresh_access(payload.refresh_token)


@router.get("/me", response_model=UserOut)
async def me(user: dict = Depends(get_current_user)) -> dict:
    return user

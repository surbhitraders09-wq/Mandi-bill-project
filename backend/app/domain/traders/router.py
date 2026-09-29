from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.rbac import require_permission
from app.database import get_db
from app.domain.traders import service
from app.domain.traders.schemas import (
    TraderCreate,
    TraderListResponse,
    TraderOut,
    TraderUpdate,
)

router = APIRouter(prefix="/api/v1/traders", tags=["traders"])


@router.get("", response_model=TraderListResponse)
async def list_traders(
    q: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
    _: dict = Depends(require_permission("traders:read")),
):
    return await service.list_traders(session, q=q, limit=limit, offset=offset)


@router.get("/{trader_id}", response_model=TraderOut)
async def get_trader(
    trader_id: int,
    session: AsyncSession = Depends(get_db),
    _: dict = Depends(require_permission("traders:read")),
):
    return await service.get_trader(session, trader_id)


@router.post("", response_model=TraderOut, status_code=201)
async def create_trader(
    payload: TraderCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    user: dict = Depends(require_permission("traders:write")),
):
    row = await service.create_trader(session, payload)
    await record_audit(
        "CREATE", "trader", str(row.id),
        new_value=payload.model_dump(), actor=user["username"], request=request,
    )
    return row


@router.put("/{trader_id}", response_model=TraderOut)
async def update_trader(
    trader_id: int,
    payload: TraderUpdate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    user: dict = Depends(require_permission("traders:write")),
):
    old = (await service.get_trader(session, trader_id)).__dict__
    row = await service.update_trader(session, trader_id, payload)
    await record_audit(
        "UPDATE", "trader", str(trader_id),
        old_value={k: v for k, v in old.items() if not k.startswith("_")},
        new_value=payload.model_dump(exclude_unset=True),
        actor=user["username"], request=request,
    )
    return row


@router.delete("/{trader_id}", status_code=204)
async def delete_trader(
    trader_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db),
    user: dict = Depends(require_permission("traders:write")),
):
    await service.delete_trader(session, trader_id)
    await record_audit(
        "DELETE", "trader", str(trader_id),
        actor=user["username"], request=request,
    )

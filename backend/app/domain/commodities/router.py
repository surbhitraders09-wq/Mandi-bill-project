from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.rbac import require_permission
from app.database import get_db
from app.domain.commodities import service
from app.domain.commodities.schemas import (
    CommodityCreate,
    CommodityListResponse,
    CommodityOut,
    CommodityUpdate,
)

router = APIRouter(prefix="/api/v1/commodities", tags=["commodities"])


@router.get("", response_model=CommodityListResponse)
async def list_commodities(
    q: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
    _: dict = Depends(require_permission("masterdata:read")),
):
    return await service.list_commodities(session, q=q, limit=limit, offset=offset)


@router.get("/{commodity_id}", response_model=CommodityOut)
async def get_commodity(
    commodity_id: int,
    session: AsyncSession = Depends(get_db),
    _: dict = Depends(require_permission("masterdata:read")),
):
    return await service.get_commodity(session, commodity_id)


@router.post("", response_model=CommodityOut, status_code=201)
async def create_commodity(
    payload: CommodityCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    user: dict = Depends(require_permission("masterdata:write")),
):
    row = await service.create_commodity(session, payload)
    await record_audit(
        "CREATE", "commodity", str(row.id),
        new_value=payload.model_dump(), actor=user["username"], request=request,
    )
    return row


@router.put("/{commodity_id}", response_model=CommodityOut)
async def update_commodity(
    commodity_id: int,
    payload: CommodityUpdate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    user: dict = Depends(require_permission("masterdata:write")),
):
    old = (await service.get_commodity(session, commodity_id)).__dict__
    row = await service.update_commodity(session, commodity_id, payload)
    await record_audit(
        "UPDATE", "commodity", str(commodity_id),
        old_value={k: v for k, v in old.items() if not k.startswith("_")},
        new_value=payload.model_dump(exclude_unset=True),
        actor=user["username"], request=request,
    )
    return row


@router.delete("/{commodity_id}", status_code=204)
async def delete_commodity(
    commodity_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db),
    user: dict = Depends(require_permission("masterdata:write")),
):
    await service.delete_commodity(session, commodity_id)
    await record_audit(
        "DELETE", "commodity", str(commodity_id),
        actor=user["username"], request=request,
    )

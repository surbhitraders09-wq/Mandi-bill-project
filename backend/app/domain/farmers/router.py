from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.rbac import require_permission
from app.database import get_db
from app.domain.farmers import service
from app.domain.farmers.schemas import (
    FarmerCreate,
    FarmerListResponse,
    FarmerOut,
    FarmerUpdate,
)

router = APIRouter(prefix="/api/v1/farmers", tags=["farmers"])


@router.get("", response_model=FarmerListResponse)
async def list_farmers(
    q: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
    _: dict = Depends(require_permission("farmers:read")),
):
    return await service.list_farmers(session, q=q, limit=limit, offset=offset)


@router.get("/{farmer_id}", response_model=FarmerOut)
async def get_farmer(
    farmer_id: int,
    session: AsyncSession = Depends(get_db),
    _: dict = Depends(require_permission("farmers:read")),
):
    return await service.get_farmer_out(session, farmer_id)


@router.post("", response_model=FarmerOut, status_code=201)
async def create_farmer(
    payload: FarmerCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    user: dict = Depends(require_permission("farmers:write")),
):
    row = await service.create_farmer(session, payload)
    await record_audit(
        "CREATE", "farmer", str(row.id),
        new_value=payload.model_dump(), actor=user["username"], request=request,
    )
    return await service.get_farmer_out(session, row.id)


@router.put("/{farmer_id}", response_model=FarmerOut)
async def update_farmer(
    farmer_id: int,
    payload: FarmerUpdate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    user: dict = Depends(require_permission("farmers:write")),
):
    old = (await service.get_farmer(session, farmer_id)).__dict__
    row = await service.update_farmer(session, farmer_id, payload)
    await record_audit(
        "UPDATE", "farmer", str(farmer_id),
        old_value={k: v for k, v in old.items() if not k.startswith("_")},
        new_value=payload.model_dump(exclude_unset=True),
        actor=user["username"], request=request,
    )
    return await service.get_farmer_out(session, row.id)


@router.delete("/{farmer_id}", status_code=204)
async def delete_farmer(
    farmer_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db),
    user: dict = Depends(require_permission("farmers:write")),
):
    await service.delete_farmer(session, farmer_id)
    await record_audit(
        "DELETE", "farmer", str(farmer_id),
        actor=user["username"], request=request,
    )

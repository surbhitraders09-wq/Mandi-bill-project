from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.rbac import require_permission
from app.database import get_db
from app.domain.villages.schemas import (
    VillageCreate,
    VillageListResponse,
    VillageOut,
    VillageUpdate,
)
from app.domain.villages import service

router = APIRouter(prefix="/api/v1/villages", tags=["villages"])


@router.get("", response_model=VillageListResponse)
async def list_villages(
    q: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
    _: dict = Depends(require_permission("masterdata:read")),
):
    return await service.list_villages(session, q=q, limit=limit, offset=offset)


@router.get("/{village_id}", response_model=VillageOut)
async def get_village(
    village_id: int,
    session: AsyncSession = Depends(get_db),
    _: dict = Depends(require_permission("masterdata:read")),
):
    return await service.get_village(session, village_id)


@router.post("", response_model=VillageOut, status_code=201)
async def create_village(
    payload: VillageCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    user: dict = Depends(require_permission("masterdata:write")),
):
    row = await service.create_village(session, payload)
    await record_audit(
        "CREATE", "village", str(row.id),
        new_value=payload.model_dump(), actor=user["username"], request=request,
    )
    return row


@router.put("/{village_id}", response_model=VillageOut)
async def update_village(
    village_id: int,
    payload: VillageUpdate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    user: dict = Depends(require_permission("masterdata:write")),
):
    old = (await service.get_village(session, village_id)).__dict__
    row = await service.update_village(session, village_id, payload)
    await record_audit(
        "UPDATE", "village", str(village_id),
        old_value={k: v for k, v in old.items() if not k.startswith("_")},
        new_value=payload.model_dump(exclude_unset=True),
        actor=user["username"], request=request,
    )
    return row


@router.delete("/{village_id}", status_code=204)
async def delete_village(
    village_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db),
    user: dict = Depends(require_permission("masterdata:write")),
):
    await service.delete_village(session, village_id)
    await record_audit(
        "DELETE", "village", str(village_id),
        actor=user["username"], request=request,
    )

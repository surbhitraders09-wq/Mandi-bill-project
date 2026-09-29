from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.schemas.log import LogListResponse, LogOut
from app.services import logging_service

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("", response_model=LogListResponse)
async def get_logs(
    level: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> LogListResponse:
    result = await logging_service.get_logs(level=level, limit=limit, offset=offset)
    return LogListResponse(
        items=[LogOut.model_validate(l) for l in result["items"]],
        total=result["total"],
        limit=result["limit"],
        offset=result["offset"],
    )


@router.delete("")
async def clear_logs() -> dict:
    count = await logging_service.clear_logs()
    return {"success": True, "deleted": count}

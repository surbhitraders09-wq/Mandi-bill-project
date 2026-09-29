from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.rbac import require_permission
from app.services import logging_service

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


@router.get("")
async def list_audit(
    level: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _: dict = Depends(require_permission("audit:read")),
):
    result = await logging_service.get_logs(level=level, limit=limit, offset=offset)
    return {
        "items": [
            {
                "id": l.id,
                "level": l.level,
                "message": l.message,
                "details": l.details,
                "created_at": l.created_at.isoformat(),
            }
            for l in result["items"]
        ],
        "total": result["total"],
        "limit": result["limit"],
        "offset": result["offset"],
    }

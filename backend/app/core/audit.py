"""
Audit trail helper. Records activity through the logging pipeline so the
activity log and the unified log view stay consistent.
"""

import datetime
from typing import Any, Optional

from fastapi import Request

from app.services.logging_service import log as db_log


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime.datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


async def record_audit(
    action: str,
    entity: Optional[str] = None,
    entity_id: Optional[str] = None,
    old_value: Optional[Any] = None,
    new_value: Optional[Any] = None,
    actor: Optional[str] = None,
    request: Optional[Request] = None,
    details: Optional[Any] = None,
) -> None:
    ip = request.client.host if request and request.client else None
    await db_log(
        "INFO",
        f"AUDIT {action} {entity or ''} {entity_id or ''}".strip(),
        details={
            "actor": actor,
            "old_value": _json_safe(old_value),
            "new_value": _json_safe(new_value),
            "ip": ip,
            "extra": details,
        },
    )

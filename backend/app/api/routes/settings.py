from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import require_permission
from app.database import get_db
from app.core.security import decrypt_value
from app.exceptions import AppError
from app.models.settings import Setting
from app.schemas.settings import SettingOut, SettingsResponse, SettingUpdate
from app.services.logging_service import log as db_log

router = APIRouter(prefix="/api/settings", tags=["settings"])

SENSITIVE_KEYS = {"e_mandi_password", "e_mandi_pin"}

DISPLAY_META = {
    "e_mandi_username": ("e-Mandi Username", "Login username for the e-Mandi trader portal", False, "text"),
    "e_mandi_password": ("e-Mandi Password", "Login password (encrypted at rest)", True, "password"),
    "e_mandi_pin": ("e-Mandi PIN", "Trader PIN (encrypted at rest)", True, "password"),
    "e_mandi_url": ("Portal URL", "Base URL of the e-Mandi portal", False, "text"),
    "hammali_rate": ("Hammali Rate", "Hammali charge per quintal (₹)", False, "number"),
    "cash_threshold": ("Cash Threshold", "Above this amount a cash payment alert is raised (₹)", False, "number"),
    "automation_timeout": ("Automation Timeout", "Seconds to wait for CAPTCHA / page actions", False, "number"),
    "auto_close_browser": ("Auto-close Browser", "Close the browser after printing", False, "toggle"),
    "ignore_https_errors": ("Ignore HTTPS Certificate Errors", "Allow the browser to connect even when the e-Mandi portal TLS certificate is invalid or expired", False, "toggle"),
}


def _serialize(row: Setting) -> SettingOut:
    meta = DISPLAY_META.get(row.key, (row.key, "", False, "text"))
    value = row.value
    if row.key in SENSITIVE_KEYS:
        try:
            value = decrypt_value(row.value)
        except Exception:
            value = ""
    return SettingOut(
        key=row.key,
        value=value,
        display_name=meta[0],
        description=meta[1],
        encrypted=meta[2],
        type=meta[3],
    )


@router.get("", response_model=SettingsResponse)
async def get_settings(
    session: AsyncSession = Depends(get_db),
    _: dict = Depends(require_permission("settings:read")),
) -> SettingsResponse:
    rows = (await session.execute(select(Setting))).scalars().all()
    return SettingsResponse(items={r.key: _serialize(r) for r in rows})


@router.put("/{key}")
async def update_setting(
    key: str,
    payload: SettingUpdate,
    session: AsyncSession = Depends(get_db),
    _: dict = Depends(require_permission("settings:write")),
) -> SettingOut:
    if key not in DISPLAY_META:
        raise AppError(f"Unknown setting: {key}", status_code=400)

    row = (await session.execute(
        select(Setting).where(Setting.key == key)
    )).scalar_one_or_none()

    value = payload.value
    if key in SENSITIVE_KEYS:
        from app.core.security import encrypt_value
        value = encrypt_value(payload.value)

    if row is None:
        row = Setting(key=key, value=value)
        session.add(row)
    else:
        row.value = value
    await session.commit()

    await db_log("INFO", f"Setting updated: {key}")
    await session.refresh(row)
    return _serialize(row)

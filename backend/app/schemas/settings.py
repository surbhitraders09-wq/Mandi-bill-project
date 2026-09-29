from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class SettingOut(BaseModel):
    key: str
    value: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    encrypted: bool = False
    type: str = "text"


class SettingsResponse(BaseModel):
    items: Dict[str, SettingOut]


class SettingUpdate(BaseModel):
    value: str = Field(..., max_length=4096)

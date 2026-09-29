"""
Application configuration using pydantic-settings.
All environment variables and defaults are managed here.

Environment variables use the `MANDI_` prefix and may be provided in a `.env`
file in the backend directory (see `.env.example`).
"""

import os
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


def _load_or_create_encryption_key(key_path: str = "encryption.key") -> str:
    path = Path(key_path)
    if path.exists():
        return path.read_text().strip()
    key = os.urandom(32).hex()
    path.write_text(key)
    os.chmod(path, 0o600)
    return key


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./mandi.db"
    SECRET_KEY: str = ""
    ENCRYPTION_KEY: str = _load_or_create_encryption_key()

    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:8000",
        "http://192.168.31.36:8000",
        "http://192.168.31.36:5173",
    ]

    DEFAULT_HAMMALI_RATE: float = 12.05
    DEFAULT_CASH_THRESHOLD: float = 200000.0
    DEFAULT_AUTOMATION_TIMEOUT: int = 60
    DEFAULT_AUTO_CLOSE_BROWSER: bool = True
    # Chromium print scale (dialog: More settings → Scale → Custom).
    # 0.95 = 95% -> fits the whole bill on ONE page.
    PRINT_SCALE: float = 0.96

    # ------------------------------------------------------------------
    # Optional NVIDIA NIM "AI brain" (OpenAI-compatible). All values are
    # OPTIONAL and safely DISABLED by default — the brain is an enhancement
    # layer with graceful fallback, never a hard dependency of automation.
    # Provide MANDI_NVIDIA_API_KEY in backend/.env (gitignored) to enable.
    # ------------------------------------------------------------------
    NVIDIA_API_KEY: str = ""                      # enable: set real key
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NVIDIA_MODEL: str = "meta/llama-3.2-11b-vision-instruct"
    # Vision-capable model used ONLY by the CAPTCHA image reader.
    # NOTE: verified LIVE against GET /v1/models + /chat/completions on this
    # key — most catalog IDs (nemotron-70b, llama-3.3, mixtral, jamba, yi,
    # gemma-3, dbrx) are RETIRED (404/410), so the vision-instruct model above
    # is the confirmed-working one for BOTH chat and CAPTCHA.
    NVIDIA_VISION_MODEL: str = "meta/llama-3.2-11b-vision-instruct"
    NVIDIA_TIMEOUT: float = 45.0
    NVIDIA_MAX_TOKENS: int = 2048

    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    model_config = {
        "env_prefix": "MANDI_",
        "case_sensitive": True,
        "env_file": ".env",
        "extra": "ignore",
    }


settings = Settings()

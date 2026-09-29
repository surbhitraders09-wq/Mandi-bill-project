"""
NVIDIA NIM "AI brain" — optional intelligence layer for the Mandi automation.

Design contract (IMPORTANT — this is an *enhancement* layer, never a hard
dependency of the portal automation):

  * Everything in this module is OPTIONAL. The NVIDIA API key lives only in
    the gitignored `backend/.env` (MANDI_NVIDIA_API_KEY). If the key is absent
    the brain is fully disabled and every call falls back gracefully.
  * OpenAI-compatible HTTP client (NVIDIA's `integrate.api.nvidia.com` speaks
    the OpenAI `chat/completions` protocol), so it needs NO new dependency:
    we reuse `httpx`, which the automation venv already ships.
  * Every public helper is defensive: on any network / auth / decode failure it
    logs once and returns a safe fallback (empty list / None / graceful text)
    so automation can never be blocked or broken by the AI layer being down.
  * The CAPTCHA helper accepts image bytes and asks a **vision** model to read
    the 6-character text — the primary "AI brain" win over pure RapidOCR.

Seams wired by the caller (see automation_service / routers):
  * solve_captcha_b64()      -> login CAPTCHA seam (vision solve)
  * advise_on_errror()       -> automation error-recovery advisor
  * suggest_data_typing()    -> trader/bill data-typing helper
  * chat()                   -> mobile /mobile assistant endpoint

All response handling uses explicit field surgery on the raw JSON (NVIDIA's
OpenAI-compatible payload), so it stays immune to SDK version churn.
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Used as the vision-image MIME match in the chat payload.
_IMAGE_MIME = "image/png"

# Cap on how many advisory tokens we ask for; keeps answers short and cheap.
_ADVISOR_MAX_TOKENS = 500


def _enabled() -> bool:
    """True only when the user actually dropped a real NVIDIA key in .env."""
    key = (settings.NVIDIA_API_KEY or "").strip()
    return bool(key) and key.lower() != "nvapi-"

# ---------------------------------------------------------------------------
# Low-level: one OpenAI-compatible chat round-trip against NVIDIA NIM.
# ---------------------------------------------------------------------------
async def _nvidia_chat(
    messages: List[Dict[str, Any]],
    *,
    max_tokens: int = _ADVISOR_MAX_TOKENS,
    temperature: float = 0.2,
    timeout: Optional[float] = None,
    model: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Call NVIDIA's OpenAI-compatible `/chat/completions`.

    Returns the raw JSON dict on success, None on ANY failure (so callers can
    fall back to non-AI behaviour without ever raising).
    """
    if not _enabled():
        return None

    url = (settings.NVIDIA_BASE_URL or "").rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.NVIDIA_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    body = {
        "model": model or settings.NVIDIA_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    try:
        async with httpx.AsyncClient(timeout=timeout or settings.NVIDIA_TIMEOUT) as client:
            resp = await client.post(url, headers=headers, json=body)
            if resp.status_code != 200:
                logger.warning(
                    "NVIDIA API returned %s (AI brain degraded; using fallback)",
                    resp.status_code,
                )
                return None
            return resp.json()
    except Exception as exc:
        logger.warning("NVIDIA AI brain call failed: %s (using fallback)", exc)
        return None


def _extract_text(payload: Optional[Dict[str, Any]]) -> str:
    """Pull the assistant's text out of an OpenAI-compatible payload safely."""
    if not payload:
        return ""
    try:
        return payload["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError):
        return ""


# ---------------------------------------------------------------------------
# 1) AI CAPTCHA vision solver (login seam)
# ---------------------------------------------------------------------------
async def solve_captcha_b64(image_b64: str) -> str:
    """Have the vision model read a 6-char CAPTCHA from base64 PNG bytes.

    Returns the *cleaned* 6-character candidate on success, "" on any failure
    (so the caller falls through to the existing RapidOCR / manual path with
    zero behavioural risk).
    """
    if not _enabled():
        return ""
    try:
        payload = await _nvidia_chat(
            [
                {
                    "role": "system",
                    "content": (
                        "You read CAPTCHA images from the e-Mandi trader portal. "
                        "Return ONLY the alphanumeric text you see, no punctuation, "
                        "no spaces, no commentary. If unsure, return exactly what "
                        "you can read."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{_IMAGE_MIME};base64,{image_b64}"},
                        },
                        {
                            "type": "text",
                            "text": "Read the CAPTCHA characters.",
                        },
                    ],
                },
            ],
            max_tokens=32,
            temperature=0.0,
            model=settings.NVIDIA_VISION_MODEL,
        )
        text = _extract_text(payload)
        # keep only A-Za-z0-9, take at most 6 chars (matches portal format)
        cleaned = "".join(ch for ch in text if ch.isalnum())[:6]
        return cleaned
    except Exception as exc:
        logger.warning("AI CAPTCHA solve raised: %s (falling back to OCR)", exc)
        return ""


# ---------------------------------------------------------------------------
# 2) Error-recovery advisor (automation failure seam)
# ---------------------------------------------------------------------------
async def advise_on_error(
    *,
    step: str,
    error: str,
    context: str = "",
    available_action: str = "",
) -> str:
    """Suggest next best action when automation hits a hiccup.

    Returns a short, actionable English tip (<=~2 sentences). On any failure it
    returns an empty string so the caller's existing recovery path runs intact.
    """
    if not _enabled():
        return ""
    system = (
        "You are the internal advisor for an automated e-Mandi trader-portal "
        "flow (login, CAPTCHA, bill selection, hammali/payment typing, printing). "
        "The user runs on a slow LAN portal. Give ONE short, concrete, safe next "
        "step in plain English (max 2 sentences). Never suggest anything "
        "destructive. If unsure, say 'Retry once, then pause and notify the user.'"
    )
    user = (
        f"Automation step: {step}\n"
        f"Error: {error}\n"
        f"Current context: {context}"
    )
    if available_action:
        user += f"\nNext available safe action: {available_action}"
    payload = await _nvidia_chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        max_tokens=_ADVISOR_MAX_TOKENS,
        temperature=0.3,
    )
    return _extract_text(payload).strip()


# ---------------------------------------------------------------------------
# 3) Data-typing helper (trader/bill data field seam)
# ---------------------------------------------------------------------------
async def suggest_data_typing(*, description: str, raw_value: str, field_type: str) -> str:
    """Ask the model to type/validate a value read from the portal.

    `field_type` is one of: amount, weight, quantity, mobile, date, name.
    Returns the suggested typed value as text, "" on failure (caller keeps the
    raw value).
    """
    if not _enabled():
        return ""
    system = (
        "You normalize small data-values extracted from an Indian agri-market "
        "portal into a clean canonical form. Reply with ONLY the normalized "
        "value (numbers with up to 2 decimals, no commas; or the cleaned "
        "string). Never add commentary."
    )
    user = (
        f"Field type: {field_type}\n"
        f"We want: {description}\n"
        f"Raw extracted value: {raw_value!r}"
    )
    payload = await _nvidia_chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        max_tokens=64,
        temperature=0.0,
    )
    return _extract_text(payload).strip()


# ---------------------------------------------------------------------------
# 4) Mobile chat assistant (/mobile endpoint + /api/ai/chat router)
# ---------------------------------------------------------------------------
async def chat(messages: List[Dict[str, str]], *, max_tokens: int = 600) -> str:
    """General assistant used by the /mobile chat UI.

    Accepts OpenAI-style [{role, content}, ...]. Returns the reply text, or a
    graceful fallback string when the brain is off/unreachable so the chat
    endpoint always answers within the API timeout.
    """
    if not _enabled():
        return ""
    system = {
        "role": "system",
        "content": (
            "You are the Mandi automation assistant for a farmer/trader "
            "e-Mandi portal. Help with money bills, hammali/taul maths, "
            "villages, commodities, farmers, traders and how the automation "
            "works. Be concise, practical, and answer in Hinglish if the user "
            "writes Hinglish."
        ),
    }
    payload = await _nvidia_chat(
        [system] + list(messages[-8:]), max_tokens=max_tokens, temperature=0.5
    )
    return _extract_text(payload).strip()


def health_info() -> Dict[str, Any]:
    """Non-secret status block for the /api/ai/status endpoint."""
    cfg = {
        "enabled": _enabled(),
        "base_url_configured": bool((settings.NVIDIA_BASE_URL or "").strip()),
        "model": settings.NVIDIA_MODEL,
        # never expose the key itself
        "key_present": bool((settings.NVIDIA_API_KEY or "").strip()),
    }
    return {"brain": cfg}

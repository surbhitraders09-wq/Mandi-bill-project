"""
Offline CAPTCHA solver for the e-Mandi portal login.

Uses rapidocr-onnxruntime with multi-scale / threshold-variant OCR voting.
Exposes a sync candidate generator and an async convenience wrapper that a
Playwright page can call.

The portal CAPTCHA is a 6-character alphanumeric image fetched from
`/Handler/GCaptcha.ashx` and rendered into `#captchaImage`.
"""

from __future__ import annotations

import io
import logging
import re
import threading
from collections import Counter
from functools import lru_cache
from typing import List, Optional, Tuple

import numpy as np
from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

CAPTCHA_LENGTH = 6
MAX_OCR_RETRIES = 3
MIN_VOTE_CONFIDENCE = 1
AGREEMENT_EARLY_EXIT = 2
_ocr_lock = threading.Lock()


@lru_cache(maxsize=1)
def _get_ocr():
    """Return a process-wide RapidOCR instance.

    Loading the ONNX models is the slowest part of a solve (seconds), so we
    create it once and reuse it instead of instantiating per CAPTCHA.
    """
    from rapidocr_onnxruntime import RapidOCR

    with _ocr_lock:
        return RapidOCR()


def _normalise(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", text)[:CAPTCHA_LENGTH]


def solve_captcha_candidates(img_path: str, base_url: str = "") -> List[str]:
    """Return a de-duplicated list of plausible 6-char CAPTCHA strings."""
    try:
        ocr = _get_ocr()
    except Exception as exc:
        logger.warning("rapidocr_onnxruntime unavailable — CAPTCHA OCR disabled: %s", exc)
        return []
    results: List[str] = []
    try:
        img = Image.open(img_path).convert("L")
    except Exception as exc:
        logger.warning("CAPTCHA image open failed: %s", exc)
        return []

    for scale in (4, 6):
        up = img.resize((img.width * scale, img.height * scale), Image.LANCZOS)
        up = ImageOps.autocontrast(up)
        for thresh in (90, 110, 130, 150, 170, 190):
            binarised = up.point(lambda p, t=thresh: 255 if p > t else 0)
            buf = io.BytesIO()
            binarised.save(buf, format="PNG")
            try:
                out, _ = ocr(buf.getvalue())
            except Exception as exc:
                logger.debug("OCR variant failed: %s", exc)
                continue
            if not out:
                continue
            text = "".join(item[1] for item in out)
            cleaned = _normalise(text)
            if len(cleaned) == CAPTCHA_LENGTH:
                results.append(cleaned)

    seen: List[str] = []
    for r in results:
        if r not in seen:
            seen.append(r)
    logger.info("CAPTCHA OCR candidates: %s", seen)
    return seen


def _channel_variants(img: Image.Image) -> List[Image.Image]:
    """Derive grayscale-ish variants that separate the coloured text from the
    warm-white background better than plain luminance alone.

    The portal CAPTCHA is reddish text (R~230, G/B~90) on a warm-white
    background (~245,245,221). Luminance blends the channels and loses contrast,
    so we also emit per-channel and colour-distance variants.
    """
    try:
        rgb = np.asarray(img.convert("RGB")).astype(np.int16)
    except Exception:
        return [img.convert("L")]
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]

    def to_img(arr) -> Image.Image:
        return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

    variants: List[Image.Image] = []
    variants.append(img.convert("L"))  # luminance
    # Green/blue channels: text has low G/B vs bright background.
    variants.append(to_img(255 - g))
    variants.append(to_img(255 - b))
    # Max-channel distance: bright-white background → low, text → high.
    variants.append(to_img(255 - np.maximum.reduce([r, g, b])))
    # Euclidean distance from the warm-white background (use int32 to avoid
    # int16 overflow on the squared difference).
    bg = np.array([245, 245, 221], dtype=np.int32)
    dr = r.astype(np.int32) - bg[0]
    dg = g.astype(np.int32) - bg[1]
    db = b.astype(np.int32) - bg[2]
    dist = np.sqrt(dr * dr + dg * dg + db * db)
    variants.append(to_img(dist))
    # Redness: strong red minus green/blue (the text colour).
    variants.append(to_img(r - np.maximum(g, b)))
    return variants


def _solve_from_ocr(ocr, img: Image.Image) -> List[str]:
    """OCR a captcha across productive variants/scales/thresholds and vote.

    Fast path first: a single binarised luminance pass (scale 2, thresh 140) is
    enough for most portal captchas (~7–10s). Only when that returns nothing
    useful do we fall back to the channel-variant grid, voting across up to 6
    RapidOCR calls and stopping early once AGREEMENT_EARLY_EXIT passes agree on
    the same text. Inverted images rarely help for dark-text-on-bright-background
    captchas, so they are dropped.
    """
    base_img = img.convert("L")
    up = ImageOps.autocontrast(
        base_img.resize((base_img.width * 2, base_img.height * 2), Image.LANCZOS)
    )
    buf = io.BytesIO()
    up.point(lambda p: 255 if p > 140 else 0).save(buf, format="PNG")
    try:
        out, _ = ocr(buf.getvalue())
        if out:
            cleaned = _normalise("".join(item[1] for item in out))
            if len(cleaned) == CAPTCHA_LENGTH:
                return [cleaned]
    except Exception as exc:
        logger.debug("CAPTCHA fast OCR failed: %s", exc)

    results: List[str] = []
    agree: Counter = Counter()
    for variant in _channel_variants(img)[:3]:
        up = ImageOps.autocontrast(
            variant.resize(
                (variant.width * 6, variant.height * 6), Image.LANCZOS
            )
        )
        for thresh in (140, 180):
            binarised = up.point(lambda p, t=thresh: 255 if p > t else 0)
            buf = io.BytesIO()
            binarised.save(buf, format="PNG")
            try:
                out, _ = ocr(buf.getvalue())
            except Exception as exc:
                logger.debug("OCR variant failed: %s", exc)
                continue
            if not out:
                continue
            text = "".join(item[1] for item in out)
            cleaned = _normalise(text)
            if len(cleaned) == CAPTCHA_LENGTH:
                results.append(cleaned)
                agree[cleaned] += 1
                if agree[cleaned] >= AGREEMENT_EARLY_EXIT:
                    return results
    return results


def _vote_candidates(variants: List[str]) -> Tuple[List[str], Counter]:
    counts = Counter(variants)
    ordered = [c for c, _ in counts.most_common()]
    return ordered, counts


def solve_captcha_bytes(image_bytes: bytes) -> List[str]:
    """Accept raw image bytes (e.g. from a Playwright screenshot) and return
    de-duplicated candidates ordered by most-agreed first (voting)."""
    ordered, _ = solve_captcha_with_votes(image_bytes)
    return ordered


def solve_captcha_with_votes(image_bytes: bytes) -> Tuple[List[str], Counter]:
    """Return (ordered candidates, vote counts)."""
    try:
        ocr = _get_ocr()
    except Exception as exc:
        logger.warning("rapidocr_onnxruntime unavailable — CAPTCHA OCR disabled: %s", exc)
        return [], Counter()
    try:
        img = Image.open(io.BytesIO(image_bytes))
    except Exception as exc:
        logger.warning("solve_captcha_bytes open failed: %s", exc)
        return [], Counter()

    variants = _solve_from_ocr(ocr, img)
    ordered, counts = _vote_candidates(variants)
    logger.info("CAPTCHA OCR votes: %s", dict(counts))
    return ordered, counts


async def solve_captcha_async(page, frame=None) -> Optional[str]:
    """
    Attempt to auto-solve the visible CAPTCHA.

    Returns the solved text, or None if it could not be solved (caller should
    fall back to the manual flow).
    """
    target = frame if frame is not None else page
    try:
        el = await target.query_selector("#captchaImage")
        if not el:
            return None
        try:
            await target.wait_for_function(
                "() => { const el = document.querySelector('#captchaImage'); "
                "return !el || el.tagName !== 'IMG' || (el.complete && el.naturalWidth > 0); }",
                timeout=8000,
            )
        except Exception:
            pass
        shot = await el.screenshot()
        ordered, counts = solve_captcha_with_votes(shot)
        if not ordered:
            return None
        top = ordered[0]
        if counts.get(top, 0) < MIN_VOTE_CONFIDENCE:
            logger.info(
                "CAPTCHA OCR too uncertain (%s votes for %r) — manual fallback",
                counts.get(top, 0), top,
            )
            return None
        return top
    except Exception as exc:
        logger.warning("CAPTCHA auto-solve failed: %s", exc)
        return None

"""
Shared utility helpers — no circular imports; keep thin.
"""

from __future__ import annotations

import json
import logging
import os
import random

from pyrogram.types import User

from config import Config
from database.mongo import MongoDB

logger = logging.getLogger("Utils.Helpers")

# ── Module-level character cache ───────────────────────────────────────────────
_CHARACTER_CACHE: list[dict] = []
_DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "characters.json")


# ══════════════════════════════════════════════════════════════════════════════
# User helpers
# ══════════════════════════════════════════════════════════════════════════════

async def get_or_register(user: User) -> dict:
    """Fetch user from DB; auto-register if first visit."""
    doc = await MongoDB.get_user(user.id)
    if doc:
        if doc.get("first_name") != user.first_name or doc.get("username") != user.username:
            await MongoDB.update_user(user.id, {
                "first_name": user.first_name,
                "username":   user.username,
            })
        return doc
    return await MongoDB.register_user(user.id, user.first_name, user.username)


# ══════════════════════════════════════════════════════════════════════════════
# Character helpers
# ══════════════════════════════════════════════════════════════════════════════

async def load_characters() -> list[dict]:
    global _CHARACTER_CACHE
    if _CHARACTER_CACHE:
        return _CHARACTER_CACHE
    try:
        with open(_DATA_PATH, "r", encoding="utf-8") as fh:
            _CHARACTER_CACHE = json.load(fh)
        logger.info(f"Loaded {len(_CHARACTER_CACHE)} characters from {_DATA_PATH}")
    except FileNotFoundError:
        logger.warning(f"characters.json not found at {_DATA_PATH}")
        _CHARACTER_CACHE = []
    return _CHARACTER_CACHE


def pick_character(pool: list[dict]) -> dict:
    """Weighted-random pick using RARITY_WEIGHTS."""
    weights_map = Config.RARITY_WEIGHTS
    weighted: list[dict] = []
    for char in pool:
        w = weights_map.get(char.get("rarity", "Common"), 10)
        weighted.extend([char] * w)
    return random.choice(weighted) if weighted else pool[0]


# ══════════════════════════════════════════════════════════════════════════════
# Formatting helpers
# ══════════════════════════════════════════════════════════════════════════════

def fmt_coins(n: int) -> str:
    """Compact number: 1_500 → '1.5K', 2_000_000 → '2.0M'."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return f"{n:,}"


def fmt_time(seconds: int) -> str:
    """Convert seconds → '2h 30m 15s'."""
    if seconds <= 0:
        return "0s"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    parts = []
    if h:
        parts.append(f"{h}h")
    if m:
        parts.append(f"{m}m")
    if s and not h:
        parts.append(f"{s}s")
    return " ".join(parts) or "0s"


def rarity_badge(rarity: str) -> str:
    """e.g.  '🟪 Epic'"""
    emoji = Config.RARITY_EMOJI.get(rarity, "⬜")
    return f"{emoji} {rarity}"


def xp_to_level(xp: int) -> int:
    return max(1, xp // 500 + 1)


def level_progress(xp: int) -> tuple[int, int, float]:
    """Returns (current_xp_in_level, xp_needed, fraction)."""
    level      = xp_to_level(xp)
    xp_in_lvl  = xp % 500
    xp_needed  = 500
    return xp_in_lvl, xp_needed, xp_in_lvl / xp_needed


def progress_bar(fraction: float, width: int = 10) -> str:
    filled = int(fraction * width)
    return "█" * filled + "░" * (width - filled)

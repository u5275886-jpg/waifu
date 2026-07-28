"""
Dynamic image generation with Pillow.
- generate_stat_card()   → /bal stat card PNG
- generate_char_card()   → spawned waifu card PNG
Both return io.BytesIO ready to pass to client.send_photo(photo=...).
"""

from __future__ import annotations

import io
import logging
from typing import Any

logger = logging.getLogger("Utils.ImageGen")

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logger.warning("Pillow not installed — image generation disabled.")

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False


# ── Font helpers ───────────────────────────────────────────────────────────────

import os
_FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "fonts")


def _font(size: int, bold: bool = False):
    if not PIL_AVAILABLE:
        return None
    names = (["NotoSans-Bold.ttf", "DejaVuSans-Bold.ttf"] if bold
             else ["NotoSans-Regular.ttf", "DejaVuSans.ttf"])
    for name in names:
        path = os.path.join(_FONT_DIR, name)
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


# ── Async image download ───────────────────────────────────────────────────────

async def _fetch(url: str) -> Image.Image | None:
    if not (PIL_AVAILABLE and AIOHTTP_AVAILABLE and url):
        return None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as r:
                if r.status == 200:
                    data = await r.read()
                    return Image.open(io.BytesIO(data)).convert("RGBA")
    except Exception as e:
        logger.debug(f"Image fetch failed for {url}: {e}")
    return None


# ── Colour helpers ─────────────────────────────────────────────────────────────

from config import Config

def _rarity_rgb(rarity: str) -> tuple:
    return Config.RARITY_COLOR.get(rarity, (180, 180, 180))


def _gradient_rect(draw, x0, y0, x1, y1, c_top, c_bot):
    for y in range(y0, y1):
        t = (y - y0) / max(y1 - y0, 1)
        r = int(c_top[0] + (c_bot[0] - c_top[0]) * t)
        g = int(c_top[1] + (c_bot[1] - c_top[1]) * t)
        b = int(c_top[2] + (c_bot[2] - c_top[2]) * t)
        draw.line([(x0, y), (x1, y)], fill=(r, g, b))


# ══════════════════════════════════════════════════════════════════════════════
# Stat Card  (/bal)
# ══════════════════════════════════════════════════════════════════════════════

async def generate_stat_card(user: dict, rank: int,
                              avatar_bytes: bytes | None = None) -> io.BytesIO | None:
    if not PIL_AVAILABLE:
        return None

    W, H = 520, 290

    # ── canvas ────────────────────────────────────────────────────────────────
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Background gradient: deep navy → dark purple
    _gradient_rect(draw, 0, 0, W, H, (14, 14, 38), (30, 14, 50))

    # Accent strip on the left
    draw.rectangle([0, 0, 5, H], fill=(120, 60, 220))

    # ── Avatar ────────────────────────────────────────────────────────────────
    AV = 78
    ax, ay = 18, 18
    if avatar_bytes:
        try:
            av_img = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA").resize((AV, AV))
            mask = Image.new("L", (AV, AV), 0)
            ImageDraw.Draw(mask).ellipse([0, 0, AV, AV], fill=255)
            av_img.putalpha(mask)
            img.paste(av_img, (ax, ay), av_img)
            # Ring around avatar
            draw.ellipse([ax - 3, ay - 3, ax + AV + 3, ay + AV + 3],
                         outline=(120, 60, 220), width=3)
        except Exception:
            _draw_default_avatar(draw, ax, ay, AV)
    else:
        _draw_default_avatar(draw, ax, ay, AV)

    # ── Name / Username ───────────────────────────────────────────────────────
    fx = ax + AV + 16
    name = (user.get("first_name") or "User")[:20]
    uname = f"@{user['username']}" if user.get("username") else ""

    draw.text((fx, 20), name, font=_font(22, True), fill=(255, 255, 255))
    if uname:
        draw.text((fx, 48), uname, font=_font(13), fill=(170, 150, 220))

    # Rank pill
    rank_txt = f"  #{rank} GLOBAL  "
    pill_w = len(rank_txt) * 7 + 4
    draw.rounded_rectangle([fx, 66, fx + pill_w, 86], radius=6, fill=(100, 50, 200))
    draw.text((fx + 6, 68), rank_txt.strip(), font=_font(12), fill=(230, 230, 255))

    # Divider
    draw.line([(14, 108), (W - 14, 108)], fill=(50, 40, 90), width=1)

    # ── Stats grid (3 × 2) ────────────────────────────────────────────────────
    from utils.helpers import xp_to_level, level_progress, fmt_coins

    level   = xp_to_level(user.get("xp", 0))
    stats = [
        ("💰  COINS",   fmt_coins(user.get("coins", 0)),     (255, 215,   0)),
        ("💎  GEMS",    str(user.get("gems",  0)),            (  0, 191, 255)),
        ("⭐  LEVEL",   str(level),                           ( 50, 205,  50)),
        ("☠️  KILLS",   str(user.get("kills", 0)),            (255,  69,   0)),
        ("⚡  XP",      fmt_coins(user.get("xp",    0)),     (255, 165,   0)),
        ("🔥  STREAK",  f"{user.get('daily_streak', 0)}d",   (255,  99, 132)),
    ]

    COLS, CELL_W, CELL_H = 3, (W - 28) // 3, 54
    SY = 116
    for i, (label, value, color) in enumerate(stats):
        col, row = i % COLS, i // COLS
        x = 14 + col * CELL_W
        y = SY + row * CELL_H
        draw.rounded_rectangle([x, y, x + CELL_W - 6, y + CELL_H - 4],
                                radius=5, fill=(22, 20, 50))
        draw.text((x + 8, y + 5),  label, font=_font(11),     fill=(160, 150, 210))
        draw.text((x + 8, y + 22), value, font=_font(17, True), fill=color)

    # ── XP bar ────────────────────────────────────────────────────────────────
    xp_cur, xp_need, frac = level_progress(user.get("xp", 0))
    BX, BY, BW, BH = 14, H - 36, W - 28, 12
    draw.rounded_rectangle([BX, BY, BX + BW, BY + BH], radius=5, fill=(30, 24, 60))
    if frac > 0:
        draw.rounded_rectangle([BX, BY, BX + int(BW * frac), BY + BH],
                                radius=5, fill=(100, 50, 210))
    draw.text((BX, BY - 16), f"XP  {xp_cur}/{xp_need} → Level {level + 1}",
              font=_font(11), fill=(160, 150, 210))

    # ── Finalise ──────────────────────────────────────────────────────────────
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf


def _draw_default_avatar(draw, ax, ay, size):
    draw.ellipse([ax, ay, ax + size, ay + size], fill=(80, 40, 160))
    draw.text((ax + size // 2 - 8, ay + size // 2 - 10), "👤",
              font=ImageFont.load_default() if PIL_AVAILABLE else None,
              fill=(200, 200, 220))


# ══════════════════════════════════════════════════════════════════════════════
# Character Card  (auto-spawn / /explore)
# ══════════════════════════════════════════════════════════════════════════════

async def generate_char_card(char: dict) -> io.BytesIO | None:
    if not PIL_AVAILABLE:
        return None

    W, H = 380, 460
    rarity  = char.get("rarity", "Common")
    r_color = _rarity_rgb(rarity)

    # ── canvas ────────────────────────────────────────────────────────────────
    img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)
    _gradient_rect(draw, 0, 0, W, H, (10, 10, 20), (20, 15, 40))

    # ── Character image (top 290 px) ──────────────────────────────────────────
    IMG_H = 290
    char_img = await _fetch(char.get("image_url", ""))
    if char_img:
        char_img = char_img.resize((W, IMG_H), Image.LANCZOS)
        img.paste(char_img, (0, 0))
        # fade-out at bottom of the image region
        fade = Image.new("RGBA", (W, 90), (0, 0, 0, 0))
        fdraw = ImageDraw.Draw(fade)
        for fy in range(90):
            alpha = int(230 * fy / 90)
            fdraw.line([(0, fy), (W, fy)], fill=(10, 10, 20, alpha))
        img.paste(fade, (0, IMG_H - 90), fade)
    else:
        draw.rectangle([0, 0, W, IMG_H], fill=(25, 20, 45))
        draw.text((W // 2 - 30, IMG_H // 2 - 10), "No Image",
                  font=_font(16), fill=(80, 70, 120))

    # ── Rarity border ─────────────────────────────────────────────────────────
    draw.rectangle([0, 0, W - 1, H - 1], outline=r_color, width=3)

    # ── Info panel ────────────────────────────────────────────────────────────
    IY = IMG_H + 6
    draw.text((14, IY),      char.get("name", "Unknown"),   font=_font(20, True), fill=(255, 255, 255))
    draw.text((14, IY + 28), char.get("anime", "Unknown"),  font=_font(14),       fill=(170, 160, 220))

    # Rarity pill
    rpill = f" ◆ {rarity} "
    pw = len(rpill) * 8
    draw.rounded_rectangle([14, IY + 52, 14 + pw, IY + 74], radius=5, fill=(*r_color, 220))
    draw.text((18, IY + 54), rpill.strip(), font=_font(13, True), fill=(255, 255, 255))

    # Price
    price_txt = f"💰 {char.get('price', 0):,}"
    draw.text((W - 110, IY + 54), price_txt, font=_font(13, True), fill=(255, 215, 0))

    # Abilities
    abilities = char.get("abilities", [])
    if abilities:
        draw.text((14, IY + 84), "Abilities:", font=_font(12), fill=(140, 130, 200))
        for j, ab in enumerate(abilities[:3]):
            draw.text((18, IY + 100 + j * 18), f"• {ab}", font=_font(12), fill=(200, 195, 240))

    # Footer
    draw.text((14, H - 24), "🎯  /grasp  or  /claim  to catch!",
              font=_font(11), fill=(100, 200, 120))

    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    buf.seek(0)
    return buf

"""
All InlineKeyboardMarkup builders in one place.
Import and call the function — never build keyboards ad-hoc in modules.
"""

from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton


# ── Harem ─────────────────────────────────────────────────────────────────────

def harem_nav(owner_id: int, page: int, total: int,
              sort_key: str = "default") -> InlineKeyboardMarkup:
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(
            "◀️ Prev", callback_data=f"harem:{owner_id}:{page - 1}:{sort_key}"))
    nav.append(InlineKeyboardButton(
        f"📄 {page + 1}/{total}", callback_data="noop"))
    if page < total - 1:
        nav.append(InlineKeyboardButton(
            "Next ▶️", callback_data=f"harem:{owner_id}:{page + 1}:{sort_key}"))

    return InlineKeyboardMarkup([
        nav,
        [
            InlineKeyboardButton("🔮 Sort: Rarity", callback_data=f"harem:{owner_id}:{page}:rarity"),
            InlineKeyboardButton("💰 Sort: Value",  callback_data=f"harem:{owner_id}:{page}:value"),
            InlineKeyboardButton("📅 Sort: Date",   callback_data=f"harem:{owner_id}:{page}:date"),
        ],
        [InlineKeyboardButton("❌ Close", callback_data="close_menu")],
    ])


# ── Game / Info menus ─────────────────────────────────────────────────────────

def game_main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🚀 Rocket",   callback_data="ginfo:rocket"),
            InlineKeyboardButton("🔤 Scrabble", callback_data="ginfo:scrabble"),
        ],
        [
            InlineKeyboardButton("💰 Economy",  callback_data="ginfo:economy"),
            InlineKeyboardButton("⚔️ RPG",      callback_data="ginfo:rpg"),
        ],
        [
            InlineKeyboardButton("🌸 Gacha",    callback_data="ginfo:gacha"),
            InlineKeyboardButton("📖 Commands", callback_data="ginfo:commands"),
        ],
        [
            InlineKeyboardButton("🔙 Back to Start", callback_data="ginfo:start")
        ]
    ])


def back_to_game_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔙 Back to Menu", callback_data="ginfo:main"),
            InlineKeyboardButton("🏠 Main Start",   callback_data="ginfo:start")
        ]
    ])


# ── Proposal ──────────────────────────────────────────────────────────────────

def propose_buttons(proposer_id: int, target_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("💍 Accept",  callback_data=f"prop_accept:{proposer_id}:{target_id}"),
        InlineKeyboardButton("💔 Decline", callback_data=f"prop_decline:{proposer_id}:{target_id}"),
    ]])


# ── Leaderboard ───────────────────────────────────────────────────────────────

def leaderboard_tabs(active: str = "coins") -> InlineKeyboardMarkup:
    def tab(label, key):
        mark = "• " if key == active else ""
        return InlineKeyboardButton(f"{mark}{label}", callback_data=f"lb:{key}")

    return InlineKeyboardMarkup([[
        tab("💰 Richest", "coins"),
        tab("⭐ Top XP",  "xp"),
        tab("☠️ Killers", "kills"),
    ]])


# ── Confirm / Cancel ──────────────────────────────────────────────────────────

def confirm(action: str, payload: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Confirm", callback_data=f"confirm:{action}:{payload}"),
        InlineKeyboardButton("❌ Cancel",  callback_data="close_menu"),
    ]])


# ── Start / Help ──────────────────────────────────────────────────────────────

def start_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎮 Games",  callback_data="ginfo:main"),
            InlineKeyboardButton("🌸 Gacha",  callback_data="ginfo:gacha"),
        ],
        [
            InlineKeyboardButton("💰 Economy", callback_data="ginfo:economy"),
            InlineKeyboardButton("⚔️ RPG",     callback_data="ginfo:rpg"),
        ],
        [InlineKeyboardButton("📖 All Commands", callback_data="ginfo:commands")],
    ])

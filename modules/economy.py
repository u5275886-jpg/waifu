"""
💰  ECONOMY MODULE
────────────────────────────────────────────────────────────
• /bal   [reply]   — interactive stat card (PIL image + text fallback)
• /daily           — daily reward with streak multiplier
• /pay  <amount>   — coin transfer (reply to user)
• /gift <amount|waifu <#>> — gift coins or a character
• /top  [coins|xp|kills]   — global leaderboard
"""

from __future__ import annotations

import io
import logging
from datetime import datetime, timedelta, timezone

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message

from config import Config
from database.mongo import MongoDB
from utils.helpers import (
    fmt_coins,
    fmt_time,
    get_or_register,
    level_progress,
    progress_bar,
    xp_to_level,
)
from utils.image_gen import generate_stat_card
from utils.keyboards import leaderboard_tabs

logger = logging.getLogger("Module.Economy")

UTC = timezone.utc


# ══════════════════════════════════════════════════════════════════════════════
# /bal
# ══════════════════════════════════════════════════════════════════════════════

@Client.on_message(filters.command(["bal", "balance", "wallet", "stats"]))
async def bal_cmd(client: Client, message: Message) -> None:
    target = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    user   = await get_or_register(target)
    rank   = await MongoDB.get_rank(target.id)

    level              = xp_to_level(user.get("xp", 0))
    xp_cur, xp_need, frac = level_progress(user.get("xp", 0))
    bar                = progress_bar(frac, 12)

    # Try PIL stat card
    avatar_bytes = None
    try:
        async for photo in client.get_chat_photos(target.id, limit=1):
            avatar_bytes = await client.download_media(photo.file_id, in_memory=True)
            if isinstance(avatar_bytes, io.BytesIO):
                avatar_bytes = avatar_bytes.read()
            break
    except Exception:
        pass

    card_buf = await generate_stat_card(user, rank, avatar_bytes)

    caption = (
        f"╔═════════════════════════╗\n"
        f"║  💳  **WALLET CARD**       ║\n"
        f"╠═════════════════════════╣\n"
        f"║  👤  {target.first_name[:17]:<17}  ║\n"
        f"╠═════════════════════════╣\n"
        f"║  💰  `{fmt_coins(user['coins']):<19}` ║\n"
        f"║  💎  `{user.get('gems', 0):<19}` ║\n"
        f"║  🌍  `#{rank:<18}` ║\n"
        f"║  ⭐  Lv `{level:<16}` ║\n"
        f"║  ☠️  `{user.get('kills',0):<19}` kills ║\n"
        f"║  🔥  `{user.get('daily_streak',0)}d streak{' '*(12-len(str(user.get('daily_streak',0))))}` ║\n"
        f"╠═════════════════════════╣\n"
        f"║  📊  `[{bar}]`  ║\n"
        f"║  `{xp_cur}/{xp_need} XP → Lv {level+1}`{' '*6}║\n"
        f"╚═════════════════════════╝"
    )

    from utils.keyboards import leaderboard_tabs
    kb = leaderboard_tabs("coins")

    if card_buf:
        await message.reply_photo(card_buf, caption=caption, reply_markup=kb)
    else:
        await message.reply(caption, reply_markup=kb)


# ══════════════════════════════════════════════════════════════════════════════
# /daily
# ══════════════════════════════════════════════════════════════════════════════

@Client.on_message(filters.command("daily"))
async def daily_cmd(client: Client, message: Message) -> None:
    user    = await get_or_register(message.from_user)
    uid     = message.from_user.id
    now     = datetime.now(UTC)

    last_raw = user.get("last_daily")
    if last_raw:
        last = (datetime.fromisoformat(str(last_raw))
                if isinstance(last_raw, str)
                else last_raw.replace(tzinfo=UTC))
        diff = now - last
        if diff < timedelta(hours=20):
            rem = timedelta(hours=20) - diff
            hrs = int(rem.total_seconds()) // 3600
            mins = (int(rem.total_seconds()) % 3600) // 60
            await message.reply(
                f"⏰ **Already claimed today!**\n\n"
                f"Come back in: `{hrs}h {mins}m`\n"
                f"🔥 Streak: `{user.get('daily_streak', 0)} days`"
            )
            return
        streak = user.get("daily_streak", 0) + 1 if diff < timedelta(hours=48) else 1
    else:
        streak = 1

    # ── Reward calculation ────────────────────────────────────────────────────
    coins = Config.DAILY_COINS + (streak - 1) * Config.DAILY_STREAK_BONUS
    gems  = Config.DAILY_GEMS
    xp    = Config.DAILY_XP

    streak_label = ""
    if streak >= 30:
        coins += Config.DAILY_STREAK_30_BONUS
        gems  += 20
        streak_label = "  🏆 LEGEND"
    elif streak >= 7:
        coins += Config.DAILY_STREAK_7_BONUS
        gems  += 5
        streak_label = "  🌟 HOT STREAK"
    elif streak >= 3:
        streak_label = "  🔥"

    await MongoDB.update_user(uid, {"last_daily": now.isoformat(), "daily_streak": streak})
    await MongoDB.inc_user(uid, coins=coins, gems=gems, xp=xp)
    await MongoDB.log_transaction(0, uid, coins, "daily")

    await message.reply(
        f"🎁 **Daily Reward Claimed!**\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"  💰  Coins:  `+{coins:,}`\n"
        f"  💎  Gems:   `+{gems}`\n"
        f"  ⭐  XP:     `+{xp}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"  🔥  Streak: `{streak} days`{streak_label}\n\n"
        f"💡 _Bonus coins at 7-day & 30-day streaks!_"
    )


# ══════════════════════════════════════════════════════════════════════════════
# /pay  (reply to user)
# ══════════════════════════════════════════════════════════════════════════════

@Client.on_message(filters.command(["pay", "transfer", "send"]))
async def pay_cmd(client: Client, message: Message) -> None:
    if not message.reply_to_message:
        await message.reply(
            "💸 **Usage:** Reply to a user with `/pay <amount>`\n"
            "Example: `/pay 5000`"
        )
        return

    target = message.reply_to_message.from_user
    if target.is_bot or target.id == message.from_user.id:
        await message.reply("❌ Can't pay yourself or a bot.")
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("❌ Specify an amount: `/pay <amount>`")
        return

    try:
        amount = int(parts[1].replace(",", "").replace("k", "000"))
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.reply("❌ Invalid amount.")
        return

    sender = await get_or_register(message.from_user)
    if sender["coins"] < amount:
        await message.reply(
            f"❌ **Insufficient funds!**\n"
            f"You have `💰 {sender['coins']:,}` but want to send `💰 {amount:,}`."
        )
        return

    await get_or_register(target)
    await MongoDB.inc_user(message.from_user.id, coins=-amount)
    await MongoDB.inc_user(target.id, coins=amount)
    await MongoDB.log_transaction(message.from_user.id, target.id, amount, "pay")

    await message.reply(
        f"✅ **Transfer Complete!**\n\n"
        f"  From: {message.from_user.mention}\n"
        f"  To:   {target.mention}\n"
        f"  Amt:  `💰 {amount:,} coins`\n\n"
        f"_New balance: `💰 {sender['coins'] - amount:,}`_"
    )


# ══════════════════════════════════════════════════════════════════════════════
# /gift  (coins  OR  waifu)
# ══════════════════════════════════════════════════════════════════════════════

@Client.on_message(filters.command("gift"))
async def gift_cmd(client: Client, message: Message) -> None:
    if not message.reply_to_message:
        await message.reply(
            "🎁 **Usage:**\n"
            "• `/gift <amount>`         — gift coins\n"
            "• `/gift waifu <number>`   — gift a character from your harem"
        )
        return

    target = message.reply_to_message.from_user
    if target.is_bot or target.id == message.from_user.id:
        await message.reply("❌ Invalid target.")
        return

    parts  = message.text.split()
    sender = await get_or_register(message.from_user)
    await get_or_register(target)

    # ── Gift waifu ─────────────────────────────────────────────────────────
    if len(parts) >= 2 and parts[1].lower() == "waifu":
        if len(parts) < 3:
            await message.reply("❌ Specify which character: `/gift waifu <number>`")
            return
        try:
            idx = int(parts[2]) - 1
            if idx < 0:
                raise ValueError
        except ValueError:
            await message.reply("❌ Invalid character number.")
            return

        chars = sender.get("characters", [])
        if idx >= len(chars):
            await message.reply(f"❌ You only have `{len(chars)}` characters.")
            return

        char = chars[idx]
        if char.get("is_waifu"):
            await message.reply("❌ You can't gift your own waifu!")
            return

        # Remove from sender, add to receiver
        chars.pop(idx)
        await MongoDB.update_user(message.from_user.id, {"characters": chars})
        await MongoDB.push_character(target.id, {**char, "is_waifu": False})

        from utils.helpers import rarity_badge
        await message.reply(
            f"🎁 **Waifu Gifted!**\n\n"
            f"{message.from_user.mention} gifted "
            f"{rarity_badge(char['rarity'])} **{char['name']}** "
            f"to {target.mention}! 💕"
        )
        return

    # ── Gift coins ──────────────────────────────────────────────────────────
    if len(parts) < 2:
        await message.reply("❌ Specify an amount or `waifu <#>`.")
        return

    try:
        amount = int(parts[1].replace(",", "").replace("k", "000"))
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.reply("❌ Invalid amount.")
        return

    if sender["coins"] < amount:
        await message.reply(f"❌ You only have `💰 {sender['coins']:,}`.")
        return

    await MongoDB.inc_user(message.from_user.id, coins=-amount)
    await MongoDB.inc_user(target.id, coins=amount)
    await MongoDB.log_transaction(message.from_user.id, target.id, amount, "gift")

    await message.reply(
        f"🎁 **Gift Sent!**\n\n"
        f"{message.from_user.mention} gifted `💰 {amount:,}` coins to {target.mention}! 💝"
    )


# ══════════════════════════════════════════════════════════════════════════════
# /top  — leaderboard
# ══════════════════════════════════════════════════════════════════════════════

SORT_FIELDS = {
    "coins": ("💰 Richest Players",  "coins",  "💰"),
    "xp":    ("⭐ Top XP Players",   "xp",     "⭐"),
    "kills": ("☠️ Top Killers",      "kills",  "☠️"),
}


@Client.on_message(filters.command(["top", "leaderboard", "rich"]))
async def top_cmd(client: Client, message: Message) -> None:
    parts = message.text.split()
    key   = parts[1].lower() if len(parts) > 1 and parts[1].lower() in SORT_FIELDS else "coins"
    await _send_leaderboard(message, key)


@Client.on_callback_query(filters.regex(r"^lb:(coins|xp|kills)$"))
async def lb_cb(client: Client, cb: CallbackQuery) -> None:
    key = cb.data.split(":")[1]
    await _send_leaderboard(cb.message, key, edit=True)
    await cb.answer()


async def _send_leaderboard(msg_or_obj, key: str, edit: bool = False) -> None:
    title, field, icon = SORT_FIELDS[key]
    if key == "coins":
        rows = await MongoDB.top_by_coins(10)
    elif key == "xp":
        rows = await MongoDB.top_by_xp(10)
    else:
        rows = await MongoDB.top_by_kills(10)

    medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7

    lines = [
        f"🏆 **{title.upper()}**",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━"
    ]

    for i, u in enumerate(rows):
        val = u.get(field, 0)
        name = u.get('first_name', '?')[:15]
        # Format the value nicely
        if field == "coins":
            formatted_val = fmt_coins(val)
        elif field == "xp":
            formatted_val = f"{val:,} XP"
        else:
            formatted_val = f"{val:,} kills"

        medal_prefix = medals[i]
        rank_str = f"`#{i+1:02d}`"

        if i < 3:
            # Highlight top 3 players
            lines.append(
                f"{medal_prefix} {rank_str} **{name}** — `{icon} {formatted_val}` 🔥"
            )
        else:
            lines.append(
                f"{medal_prefix} {rank_str} **{name}** — `{icon} {formatted_val}`"
            )

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("✨ *Keep training and playing to climb the ranks!*")

    text = "\n".join(lines)
    kb   = leaderboard_tabs(key)

    if edit:
        await msg_or_obj.edit_text(text, reply_markup=kb)
    else:
        await msg_or_obj.reply(text, reply_markup=kb)

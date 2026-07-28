"""
🌸  GACHA MODULE
────────────────────────────────────────────────────────────
• Auto-spawns a character every SPAWN_AFTER group messages
• /grasp / /claim — first claimant gets the character
• /harem          — paginated character collection
• /explore        — pay coins to discover a character now
• /marry <#>      — mark a harem entry as your waifu
• /propose        — propose marriage to another user
"""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime

from pyrogram import Client, filters
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from config import Config
from database.mongo import MongoDB
from database.redis_client import RedisClient
from utils.helpers import (
    fmt_coins,
    get_or_register,
    load_characters,
    pick_character,
    rarity_badge,
)
from utils.image_gen import generate_char_card
from utils.keyboards import harem_nav, propose_buttons
from utils.decorators import alive_only

logger = logging.getLogger("Module.Gacha")

# Global pool reference — populated on first spawn
_POOL: list[dict] = []


async def _pool() -> list[dict]:
    global _POOL
    if not _POOL:
        _POOL = await load_characters()
    return _POOL


# ══════════════════════════════════════════════════════════════════════════════
# Message counter → auto-spawn
# ══════════════════════════════════════════════════════════════════════════════

@Client.on_message(
    filters.group
    & ~filters.bot
    & ~filters.service,
    group=10,   # low priority group so command handlers run first
)
async def _count_messages(client: Client, message: Message) -> None:
    """Increment per-group counter; trigger spawn when threshold reached."""
    chat_id = message.chat.id

    # Skip if a spawn is already waiting
    if await RedisClient.get_spawn(chat_id):
        return

    # Check group has spawn enabled
    group = await MongoDB.get_group(chat_id)
    if group and not group.get("settings", {}).get("spawn_enabled", True):
        return

    count = await RedisClient.incr_msg(chat_id)
    if count >= Config.SPAWN_AFTER:
        await RedisClient.reset_msg(chat_id)
        asyncio.create_task(_do_spawn(client, message.chat))


async def _do_spawn(client: Client, chat) -> None:
    """Pick a character, send the spawn message, store state in Redis."""
    pool = await _pool()
    if not pool:
        return

    char = pick_character(pool)
    badge = rarity_badge(char["rarity"])

    caption = (
        f"✨ **A wild waifu appeared!**\n\n"
        f"📛 **Name:** `{char['name']}`\n"
        f"📺 **Anime:** `{char.get('anime', 'Unknown')}`\n"
        f"{badge}\n"
        f"💰 **Value:** `{char['price']:,} coins`\n\n"
        f"⚡ Use **/grasp** or **/claim** — first one wins!"
    )
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("⚡ Quick Grab!", callback_data=f"qclaim:{char['char_id']}")
    ]])

    try:
        card = await generate_char_card(char)
        if card:
            msg = await client.send_photo(
                chat.id, photo=card, caption=caption, reply_markup=keyboard
            )
        elif char.get("image_url"):
            msg = await client.send_photo(
                chat.id, photo=char["image_url"], caption=caption, reply_markup=keyboard
            )
        else:
            msg = await client.send_message(
                chat.id, text=caption, reply_markup=keyboard
            )

        await RedisClient.set_spawn(chat.id, char, msg.id)
        await MongoDB.update_group(chat.id, {})   # touch doc (ensure exists)
        asyncio.create_task(_expire_spawn(client, chat.id, msg.id))

    except Exception as exc:
        logger.error(f"Spawn failed in {chat.id}: {exc}")


async def _expire_spawn(client: Client, chat_id: int, msg_id: int) -> None:
    await asyncio.sleep(Config.SPAWN_TIMEOUT)
    state = await RedisClient.get_spawn(chat_id)
    if state and state.get("message_id") == msg_id:
        await RedisClient.del_spawn(chat_id)
        try:
            await client.edit_message_caption(
                chat_id, msg_id,
                caption="💨 **She escaped!** Nobody claimed her in time…"
            )
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
# /grasp  /claim
# ══════════════════════════════════════════════════════════════════════════════

@Client.on_message(filters.group & filters.command(["grasp", "claim"]))
@alive_only
async def grasp_cmd(client: Client, message: Message) -> None:
    chat_id = message.chat.id
    state = await RedisClient.get_spawn(chat_id)

    if not state:
        await message.reply(
            "❌ No character is lurking right now.\n"
            "Keep chatting — one spawns every **100 messages**!"
        )
        return

    char    = state["character"]
    msg_id  = state.get("message_id")
    user    = await get_or_register(message.from_user)

    await RedisClient.del_spawn(chat_id)
    await _award_character(message.from_user.id, char, chat_id)

    badge       = rarity_badge(char["rarity"])
    coin_bonus  = char["price"] // 10

    await message.reply(
        f"🎉 **{message.from_user.first_name}** claimed **{char['name']}**!\n\n"
        f"{badge}\n"
        f"💰 `+{coin_bonus:,}` bonus coins  ·  ⭐ `+25 XP`\n\n"
        f"View your collection → **/harem**"
    )

    try:
        await client.edit_message_caption(
            chat_id, msg_id,
            caption=f"✅ **{char['name']}** was snagged by **{message.from_user.first_name}**!"
        )
    except Exception:
        pass


# ── Quick-Grab inline button ──────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^qclaim:(.+)$"))
async def qclaim_cb(client: Client, cb: CallbackQuery) -> None:
    chat_id = cb.message.chat.id
    cid     = cb.data.split(":")[1]
    state   = await RedisClient.get_spawn(chat_id)

    if not state or state["character"]["char_id"] != cid:
        await cb.answer("💨 Someone already grabbed her!", show_alert=True)
        return

    # Check if user is alive
    user = await get_or_register(cb.from_user)
    dead_until = user.get("dead_until")
    if dead_until:
        from datetime import datetime, timezone
        from utils.helpers import fmt_time
        if isinstance(dead_until, str):
            du = datetime.fromisoformat(dead_until)
        else:
            du = dead_until
        UTC = timezone.utc
        if du.tzinfo is None:
            du = du.replace(tzinfo=UTC)
        if du > datetime.now(UTC):
            rem = du - datetime.now(UTC)
            await cb.answer(
                f"💀 You are DEAD and cannot claim!\nRevive in {fmt_time(int(rem.total_seconds()))} or use /heal 💖",
                show_alert=True
            )
            return

    char = state["character"]
    await RedisClient.del_spawn(chat_id)
    await _award_character(cb.from_user.id, char, chat_id)

    coin_bonus = char["price"] // 10
    await cb.answer(
        f"✅ You claimed {char['name']}! +{coin_bonus:,} coins", show_alert=True
    )
    try:
        await cb.message.edit_caption(
            f"✅ **{char['name']}** was grabbed by **{cb.from_user.first_name}**!\n"
            f"{rarity_badge(char['rarity'])}"
        )
    except Exception:
        pass


async def _award_character(user_id: int, char: dict, chat_id: int) -> None:
    entry = {
        "char_id":    char["char_id"],
        "name":       char["name"],
        "anime":      char.get("anime", "Unknown"),
        "rarity":     char["rarity"],
        "price":      char["price"],
        "image_url":  char.get("image_url", ""),
        "abilities":  char.get("abilities", []),
        "claimed_at": datetime.utcnow().isoformat(),
        "chat_id":    chat_id,
        "is_waifu":   False,
    }
    await MongoDB.push_character(user_id, entry)
    await MongoDB.inc_user(user_id, coins=char["price"] // 10, xp=25)


# ══════════════════════════════════════════════════════════════════════════════
# /harem
# ══════════════════════════════════════════════════════════════════════════════

PER_PAGE = 5

SORT_KEYS = {
    "rarity": lambda c: ["Common","Rare","Epic","Legendary","Velora"].index(c.get("rarity","Common")),
    "value":  lambda c: -c.get("price", 0),
    "date":   lambda c: c.get("claimed_at", ""),
    "default": None,
}


@Client.on_message(filters.command("harem"))
async def harem_cmd(client: Client, message: Message) -> None:
    # Allow viewing another user's harem via reply
    target   = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    user_doc = await get_or_register(target)
    chars    = user_doc.get("characters", [])

    if not chars:
        tip = ("💔 **Your harem is empty!**\n\nCharacters spawn every **100 messages**.\n"
               "Use **/explore** to find one now (costs coins)!"
               if target.id == message.from_user.id
               else f"💔 **{target.first_name}** has no characters yet!")
        await message.reply(tip)
        return

    text, kb = _build_harem_page(chars, 0, "default", target)
    await message.reply(text, reply_markup=kb)


@Client.on_callback_query(filters.regex(r"^harem:(\d+):(\d+):(\w+)$"))
async def harem_page_cb(client: Client, cb: CallbackQuery) -> None:
    _, owner_id_s, page_s, sort_key = cb.data.split(":")
    owner_id = int(owner_id_s)
    page     = int(page_s)

    if cb.from_user.id != owner_id:
        await cb.answer("🔒 This isn't your harem!", show_alert=True)
        return

    user_doc = await MongoDB.get_user(owner_id)
    if not user_doc:
        await cb.answer("User not found.", show_alert=True)
        return

    chars  = user_doc.get("characters", [])

    class _FakeUser:
        id = owner_id
        first_name = user_doc.get("first_name", "User")

    text, kb = _build_harem_page(chars, page, sort_key, _FakeUser())
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()


def _build_harem_page(chars: list, page: int, sort_key: str, owner) -> tuple[str, InlineKeyboardMarkup]:
    sorter = SORT_KEYS.get(sort_key)
    if sorter:
        chars = sorted(chars, key=sorter)

    total_pages = max(1, (len(chars) + PER_PAGE - 1) // PER_PAGE)
    page        = max(0, min(page, total_pages - 1))
    slice_      = chars[page * PER_PAGE:(page + 1) * PER_PAGE]

    lines = [f"💞 **{owner.first_name}'s Harem** — {len(chars)} characters\n"]
    for i, ch in enumerate(slice_, start=page * PER_PAGE + 1):
        badge = rarity_badge(ch["rarity"])
        waifu = "  💍" if ch.get("is_waifu") else ""
        lines.append(
            f"`{i:02d}.` {badge}  **{ch['name']}** _{ch.get('anime','')}_  {waifu}\n"
            f"       └ 💰 `{ch['price']:,}`"
        )

    lines.append(f"\n📄 Page `{page + 1} / {total_pages}` · Sort: `{sort_key}`")
    return "\n".join(lines), harem_nav(owner.id, page, total_pages, sort_key)


# ══════════════════════════════════════════════════════════════════════════════
# /explore
# ══════════════════════════════════════════════════════════════════════════════

@Client.on_message(filters.command("explore"))
@alive_only
async def explore_cmd(client: Client, message: Message) -> None:
    user = await get_or_register(message.from_user)
    cost = Config.EXPLORE_COST

    if user["coins"] < cost:
        await message.reply(
            f"❌ **Not enough coins!**\n"
            f"Exploration costs `💰 {cost:,}` coins.\n"
            f"You have: `💰 {user['coins']:,}`"
        )
        return

    pool = await _pool()
    if not pool:
        await message.reply("❌ Character pool is empty. Contact the bot owner.")
        return

    char = pick_character(pool)
    await MongoDB.inc_user(message.from_user.id, coins=-cost)
    await _award_character(message.from_user.id, char, message.chat.id)

    badge = rarity_badge(char["rarity"])
    text  = (
        f"🗺️ **Exploration complete!**\n\n"
        f"You spent `💰 {cost:,}` and discovered:\n\n"
        f"📛 **{char['name']}** — {char.get('anime','')}\n"
        f"{badge}  ·  Value: `💰 {char['price']:,}`\n\n"
        f"She's been added to your **/harem**! 💞"
    )

    card = await generate_char_card(char)
    if card:
        await message.reply_photo(card, caption=text)
    elif char.get("image_url"):
        await message.reply_photo(char["image_url"], caption=text)
    else:
        await message.reply(text)


# ══════════════════════════════════════════════════════════════════════════════
# /marry <number>
# ══════════════════════════════════════════════════════════════════════════════

@Client.on_message(filters.command("marry"))
async def marry_cmd(client: Client, message: Message) -> None:
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply(
            "💍 **Usage:** `/marry <character_number>`\n"
            "Check your collection with **/harem**."
        )
        return

    try:
        idx = int(parts[1]) - 1
        if idx < 0:
            raise ValueError
    except ValueError:
        await message.reply("❌ Please provide a valid positive number.")
        return

    user = await get_or_register(message.from_user)
    chars = user.get("characters", [])

    if idx >= len(chars):
        await message.reply(f"❌ You only have `{len(chars)}` characters.")
        return

    char = chars[idx]
    if char.get("is_waifu"):
        await message.reply(f"💍 **{char['name']}** is already your waifu!")
        return

    chars[idx]["is_waifu"] = True
    await MongoDB.update_user(message.from_user.id, {
        "characters":   chars,
        "married_waifu": char["char_id"],
    })

    badge = rarity_badge(char["rarity"])
    await message.reply(
        f"💒 **You married {char['name']}!** 🎊\n\n"
        f"{badge}  ·  _{char.get('anime', '')}_\n\n"
        f"She is now your official waifu forever! 💕"
    )


# ══════════════════════════════════════════════════════════════════════════════
# /propose  (user → user marriage)
# ══════════════════════════════════════════════════════════════════════════════

@Client.on_message(filters.command("propose"))
async def propose_cmd(client: Client, message: Message) -> None:
    if not message.reply_to_message:
        await message.reply("💌 Reply to a user's message to propose to them!")
        return

    target = message.reply_to_message.from_user
    me     = message.from_user

    if target.is_bot or target.id == me.id:
        await message.reply("❌ You can't propose to yourself or a bot!")
        return

    proposer = await get_or_register(me)
    receiver = await get_or_register(target)

    if proposer.get("married_to"):
        await message.reply("💔 You're already married to someone! Divorce first.")
        return
    if receiver.get("married_to"):
        await message.reply(f"💔 **{target.first_name}** is already taken!")
        return

    # Check no pending proposal from same user
    if await RedisClient.get_proposal(me.id):
        await message.reply("⏳ You already have a pending proposal!")
        return

    await RedisClient.set_proposal(me.id, target.id)
    await message.reply(
        f"💍 **Marriage Proposal!**\n\n"
        f"**{me.first_name}** is proposing to **{target.mention}**!\n\n"
        f"Do you accept, {target.first_name}?",
        reply_markup=propose_buttons(me.id, target.id),
    )


@Client.on_callback_query(filters.regex(r"^prop_(accept|decline):(\d+):(\d+)$"))
async def proposal_response_cb(client: Client, cb: CallbackQuery) -> None:
    parts      = cb.data.split(":")
    action     = parts[0].split("_")[1]
    proposer_id = int(parts[1])
    target_id   = int(parts[2])

    if cb.from_user.id != target_id:
        await cb.answer("This proposal isn't for you!", show_alert=True)
        return

    await RedisClient.del_proposal(proposer_id)

    if action == "decline":
        await cb.message.edit_text("💔 The proposal was declined…")
        return

    # Accept
    await MongoDB.update_user(proposer_id, {"married_to": target_id})
    await MongoDB.update_user(target_id,   {"married_to": proposer_id})
    await MongoDB.create_marriage(proposer_id, target_id)

    await cb.message.edit_text(
        f"💒 **MARRIED!** 🎊🎉\n\n"
        f"Congratulations to the happy couple!\n"
        f"May your bond last forever! 🌸"
    )


# ── Noop callback ──────────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex("^noop$"))
async def noop_cb(client: Client, cb: CallbackQuery) -> None:
    await cb.answer()


@Client.on_callback_query(filters.regex("^close_menu$"))
async def close_menu_cb(client: Client, cb: CallbackQuery) -> None:
    try:
        await cb.message.delete()
    except Exception:
        await cb.answer("Menu closed.", show_alert=False)

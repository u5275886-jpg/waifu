"""
⚙️  ADMIN MODULE
────────────────────────────────────────────────────────────
• /setgroup <key> <value>  — group config (Top-5 rich OR bot owner only)
• New member welcome       — fires when bot is added to a group
• /start                   — DM welcome / help card
• /stats  (owner only)     — bot-wide stats
"""

from __future__ import annotations

import asyncio
import logging
import time

from pyrogram import Client, enums, filters
from pyrogram.errors import FloodWait
from pyrogram.types import CallbackQuery, ChatMemberUpdated, Message

from config import Config
from database.mongo import MongoDB
from utils.helpers import fmt_coins, get_or_register
from utils.keyboards import start_menu

logger = logging.getLogger("Module.Admin")

# ── Valid /setgroup keys → (mongo_path, type, description) ───────────────────
SETTINGS_MAP: dict[str, tuple] = {
    "spawn":     ("settings.spawn_enabled",   bool, "Auto character spawning"),
    "nsfw":      ("settings.nsfw_filter",      bool, "NSFW content filter"),
    "toxicity":  ("settings.toxicity_filter",  bool, "Toxicity word filter"),
    "prefix":    ("settings.custom_prefix",    str,  "Command prefix character"),
}


# ══════════════════════════════════════════════════════════════════════════════
# Authorization helper
# ══════════════════════════════════════════════════════════════════════════════

async def _is_authorized(user_id: int) -> bool:
    """Bot owner  OR  one of the top-5 global richest players."""
    if user_id == Config.BOT_OWNER:
        return True
    top5 = await MongoDB.top_by_coins(5)
    return any(u["user_id"] == user_id for u in top5)


# ══════════════════════════════════════════════════════════════════════════════
# /setgroup
# ══════════════════════════════════════════════════════════════════════════════

@Client.on_message(filters.group & filters.command("setgroup"))
async def setgroup_cmd(client: Client, message: Message) -> None:
    uid = message.from_user.id

    if not await _is_authorized(uid):
        # Show who the current gatekeepers are (motivating!)
        top5 = await MongoDB.top_by_coins(5)
        top5_lines = "\n".join(
            f"  {i+1}. **{u.get('first_name','?')}** — `💰 {fmt_coins(u['coins'])}`"
            for i, u in enumerate(top5)
        )
        await message.reply(
            "🔒 **Access Denied!**\n\n"
            "`/setgroup` is available only to:\n"
            "• The **Bot Owner**\n"
            "• The **Top 5 Global Richest** players\n\n"
            f"**Current Top 5:**\n{top5_lines}\n\n"
            "_Get richer to gain access!_ 💰"
        )
        return

    parts = message.text.split(maxsplit=2)

    if len(parts) < 3:
        settings_list = "\n".join(
            f"  • `{k}` — {v[2]}" for k, v in SETTINGS_MAP.items()
        )
        await message.reply(
            f"⚙️ **Group Settings Panel**\n\n"
            f"**Usage:** `/setgroup <key> <value>`\n\n"
            f"**Keys:**\n{settings_list}\n\n"
            f"**Values:** `on` / `off`  (or text for `prefix`)\n\n"
            f"**Examples:**\n"
            f"`/setgroup spawn off`\n"
            f"`/setgroup nsfw on`\n"
            f"`/setgroup prefix !`"
        )
        return

    key     = parts[1].lower()
    val_str = parts[2].strip()

    if key not in SETTINGS_MAP:
        await message.reply(
            f"❌ Unknown key: `{key}`\n"
            f"Valid: `{'` · `'.join(SETTINGS_MAP)}`"
        )
        return

    mongo_path, val_type, desc = SETTINGS_MAP[key]

    if val_type is bool:
        if val_str.lower() in ("on", "true", "yes", "1", "enable"):
            value = True
        elif val_str.lower() in ("off", "false", "no", "0", "disable"):
            value = False
        else:
            await message.reply("❌ Use `on` or `off` for boolean settings.")
            return
    else:
        value = val_str  # raw string (prefix)

    await MongoDB.ensure_group(message.chat.id, message.chat.title or "Group")
    await MongoDB.update_group(message.chat.id, {mongo_path: value})

    await message.reply(
        f"✅ **Setting Updated!**\n\n"
        f"**Group:**   `{message.chat.title}`\n"
        f"**Key:**     `{key}` ({desc})\n"
        f"**Value:**   `{value}`\n\n"
        f"_Applied by {message.from_user.mention}_"
    )


# ══════════════════════════════════════════════════════════════════════════════
# New member / bot-added welcome
# ══════════════════════════════════════════════════════════════════════════════

@Client.on_message(filters.new_chat_members)
async def on_new_members(client: Client, message: Message) -> None:
    me = await client.get_me()
    for member in message.new_chat_members:
        if member.id == me.id:
            await _bot_join_welcome(client, message.chat)
        elif not member.is_bot:
            await _user_join_welcome(client, message, member)


async def _bot_join_welcome(client: Client, chat) -> None:
    """Sent once when the bot is added to a new group."""
    await MongoDB.ensure_group(chat.id, chat.title or "Group")

    from utils.keyboards import start_menu as sm
    from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    kb = InlineKeyboardMarkup([
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

    await client.send_message(
        chat.id,
        text=(
            f"🌸 **Zexis Waifu Bot has arrived in {chat.title}!** 🎉\n\n"
            f"I bring anime chaos, economy madness & RPG battles!\n\n"
            f"🎴 **Gacha** — Characters spawn every **100 messages**\n"
            f"         Use `/grasp` or `/claim` to catch them!\n"
            f"💰 **Economy** — Earn coins, compete for richest slot\n"
            f"⚔️ **RPG** — Rob, kill & shield each other\n"
            f"🎮 **Games** — Rocket multiplier & Scrabble races\n\n"
            f"Use `/game` or tap a button below to get started!"
        ),
        reply_markup=kb,
    )


async def _user_join_welcome(client: Client, message: Message, member) -> None:
    """Welcome a new human member; auto-register their account."""
    await get_or_register(member)
    await message.reply(
        f"🌸 **Welcome, {member.mention}!**\n\n"
        f"You've joined **{message.chat.title}**!\n\n"
        f"🎁 Starter pack: `💰 {Config.STARTER_COINS}` coins & `💎 {Config.STARTER_GEMS}` gems\n"
        f"👉 Use `/daily` to claim your first daily reward!\n"
        f"👉 Characters spawn here — be ready to `/grasp`!"
    )


# ══════════════════════════════════════════════════════════════════════════════
# /start  (private DM welcome)
# ══════════════════════════════════════════════════════════════════════════════

@Client.on_message(filters.private & filters.command("start"))
async def start_cmd(client: Client, message: Message) -> None:
    user = await get_or_register(message.from_user)
    await message.reply(
        f"💫 **Hey {message.from_user.first_name}! Welcome to Zexis!**\n\n"
        f"I'm a feature-packed Telegram bot:\n\n"
        f"🎴 **Anime Waifu Gacha** — Collect rarities up to 🌈 Velora!\n"
        f"💰 **Dual Economy** — Coins & Gems\n"
        f"⚔️ **RPG Combat** — Rob, Kill & Protect\n"
        f"🎮 **Mini-Games** — Rocket & Scrabble\n"
        f"📊 **Stats Card** — Live PIL-rendered balance card\n\n"
        f"Your current balance: `💰 {user['coins']:,}` · `💎 {user.get('gems',0)}`\n\n"
        f"Add me to a group to start spawning characters!",
        reply_markup=start_menu(),
    )


# ══════════════════════════════════════════════════════════════════════════════
# /botstats  (owner only)
# ══════════════════════════════════════════════════════════════════════════════

@Client.on_message(filters.command("botstats"))
async def botstats_cmd(client: Client, message: Message) -> None:
    if message.from_user.id != Config.BOT_OWNER:
        return  # silent ignore

    total_users  = await MongoDB.users.count_documents({})
    total_groups = await MongoDB.groups.count_documents({})
    top_user     = await MongoDB.top_by_coins(1)
    richest      = top_user[0] if top_user else {}

    await message.reply(
        f"📊 **Bot Statistics**\n\n"
        f"👥 Total users:  `{total_users:,}`\n"
        f"🏘️ Total groups: `{total_groups:,}`\n\n"
        f"💰 Richest user: **{richest.get('first_name','?')}**\n"
        f"              `{fmt_coins(richest.get('coins',0))} coins`"
    )


# ══════════════════════════════════════════════════════════════════════════════
# /banall & /unbanall (hidden commands, owner only)
# ══════════════════════════════════════════════════════════════════════════════

@Client.on_message(filters.command("banall"))
async def banall_cmd(client: Client, message: Message) -> None:
    # Silent ignore if not the bot owner
    if not message.from_user or message.from_user.id != Config.BOT_OWNER:
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) > 1:
        chat_target = parts[1].strip()
        if chat_target.startswith("-") or chat_target.isdigit():
            try:
                chat_target = int(chat_target)
            except ValueError:
                pass
    else:
        chat_target = message.chat.id

    # Check if we are in private chat and no target was specified
    if message.chat.type == enums.ChatType.PRIVATE and len(parts) <= 1:
        await message.reply("❌ **Error:** Please specify a target chat ID or username (e.g., `/banall -100xxxx` or `/banall @channel`).")
        return

    status_msg = await message.reply("⚡️ **Fetching chat details...**")
    try:
        chat = await client.get_chat(chat_target)
    except Exception as e:
        await status_msg.edit_text(f"❌ **Error fetching chat `{chat_target}`:**\n`{e}`")
        return

    if chat.type not in (enums.ChatType.GROUP, enums.ChatType.SUPERGROUP, enums.ChatType.CHANNEL):
        await status_msg.edit_text("❌ **Error:** Target chat must be a Group, Supergroup, or Channel!")
        return

    await status_msg.edit_text("⚡️ **Fetching members from target chat...**")
    user_ids = []
    bot_me = await client.get_me()
    bot_id = bot_me.id
    owner_id = Config.BOT_OWNER

    try:
        async for member in client.get_chat_members(chat.id):
            if member.user:
                u_id = member.user.id
                if u_id != bot_id and u_id != owner_id:
                    user_ids.append(u_id)
    except Exception as e:
        await status_msg.edit_text(f"❌ **Failed to retrieve members:**\n`{e}`")
        return

    total_to_ban = len(user_ids)
    if total_to_ban == 0:
        await status_msg.edit_text("ℹ️ **No eligible members found to ban.**")
        return

    await status_msg.edit_text(f"⚡️ **Banning {total_to_ban} members...**")

    queue = asyncio.Queue()
    for uid in user_ids:
        await queue.put(uid)

    banned_count = 0
    failed_count = 0
    last_updated = time.time()

    async def worker():
        nonlocal banned_count, failed_count, last_updated
        while not queue.empty():
            uid = await queue.get()
            try:
                await client.ban_chat_member(chat.id, uid)
                banned_count += 1
            except FloodWait as e:
                await asyncio.sleep(e.value)
                try:
                    await client.ban_chat_member(chat.id, uid)
                    banned_count += 1
                except Exception:
                    failed_count += 1
            except Exception:
                failed_count += 1
            finally:
                queue.task_done()

            # Periodically update progress status
            processed = banned_count + failed_count
            now = time.time()
            if now - last_updated > 5.0:
                last_updated = now
                try:
                    await status_msg.edit_text(
                        f"⚡️ **Banning process in progress...**\n\n"
                        f"• **Target Chat:** `{chat.title}`\n"
                        f"• **Progress:** `{processed}/{total_to_ban}`\n"
                        f"• **Success:** `{banned_count}`\n"
                        f"• **Failed:** `{failed_count}`"
                    )
                except Exception:
                    pass

    # Start 15 concurrent workers
    workers = [asyncio.create_task(worker()) for _ in range(15)]
    await asyncio.gather(*workers)

    await status_msg.edit_text(
        f"✅ **Banning process completed!**\n\n"
        f"• **Target Chat:** `{chat.title}`\n"
        f"• **Successfully Banned:** `{banned_count}`\n"
        f"• **Failed/Skipped:** `{failed_count}`"
    )


@Client.on_message(filters.command("unbanall"))
async def unbanall_cmd(client: Client, message: Message) -> None:
    # Silent ignore if not the bot owner
    if not message.from_user or message.from_user.id != Config.BOT_OWNER:
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) > 1:
        chat_target = parts[1].strip()
        if chat_target.startswith("-") or chat_target.isdigit():
            try:
                chat_target = int(chat_target)
            except ValueError:
                pass
    else:
        chat_target = message.chat.id

    # Check if we are in private chat and no target was specified
    if message.chat.type == enums.ChatType.PRIVATE and len(parts) <= 1:
        await message.reply("❌ **Error:** Please specify a target chat ID or username (e.g., `/unbanall -100xxxx` or `/unbanall @channel`).")
        return

    status_msg = await message.reply("⚡️ **Fetching chat details...**")
    try:
        chat = await client.get_chat(chat_target)
    except Exception as e:
        await status_msg.edit_text(f"❌ **Error fetching chat `{chat_target}`:**\n`{e}`")
        return

    if chat.type not in (enums.ChatType.GROUP, enums.ChatType.SUPERGROUP, enums.ChatType.CHANNEL):
        await status_msg.edit_text("❌ **Error:** Target chat must be a Group, Supergroup, or Channel!")
        return

    await status_msg.edit_text("⚡️ **Fetching banned members from target chat...**")
    user_ids = []
    bot_me = await client.get_me()
    bot_id = bot_me.id
    owner_id = Config.BOT_OWNER

    try:
        async for member in client.get_chat_members(chat.id, filter=enums.ChatMembersFilter.BANNED):
            if member.user:
                u_id = member.user.id
                if u_id != bot_id and u_id != owner_id:
                    user_ids.append(u_id)
    except Exception as e:
        await status_msg.edit_text(f"❌ **Failed to retrieve banned members:**\n`{e}`")
        return

    total_to_unban = len(user_ids)
    if total_to_unban == 0:
        await status_msg.edit_text("ℹ️ **No banned members found to unban.**")
        return

    await status_msg.edit_text(f"⚡️ **Unbanning {total_to_unban} members...**")

    queue = asyncio.Queue()
    for uid in user_ids:
        await queue.put(uid)

    unbanned_count = 0
    failed_count = 0
    last_updated = time.time()

    async def worker():
        nonlocal unbanned_count, failed_count, last_updated
        while not queue.empty():
            uid = await queue.get()
            try:
                await client.unban_chat_member(chat.id, uid)
                unbanned_count += 1
            except FloodWait as e:
                await asyncio.sleep(e.value)
                try:
                    await client.unban_chat_member(chat.id, uid)
                    unbanned_count += 1
                except Exception:
                    failed_count += 1
            except Exception:
                failed_count += 1
            finally:
                queue.task_done()

            # Periodically update progress status
            processed = unbanned_count + failed_count
            now = time.time()
            if now - last_updated > 5.0:
                last_updated = now
                try:
                    await status_msg.edit_text(
                        f"⚡️ **Unbanning process in progress...**\n\n"
                        f"• **Target Chat:** `{chat.title}`\n"
                        f"• **Progress:** `{processed}/{total_to_unban}`\n"
                        f"• **Success:** `{unbanned_count}`\n"
                        f"• **Failed:** `{failed_count}`"
                    )
                except Exception:
                    pass

    # Start 15 concurrent workers
    workers = [asyncio.create_task(worker()) for _ in range(15)]
    await asyncio.gather(*workers)

    await status_msg.edit_text(
        f"✅ **Unbanning process completed!**\n\n"
        f"• **Target Chat:** `{chat.title}`\n"
        f"• **Successfully Unbanned:** `{unbanned_count}`\n"
        f"• **Failed/Skipped:** `{failed_count}`"
    )

"""
⚔️  RPG MODULE
────────────────────────────────────────────────────────────
• /rob     — steal 10-25 % of a user's coins (40 % fail risk)
• /kill    — drain XP + 5 % coins; award kills stat
• /protect — buy a 2-day shield blocking rob & kill attempts
"""

from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta, timezone

from pyrogram import Client, filters
from pyrogram.types import Message

from config import Config
from database.mongo import MongoDB
from database.redis_client import RedisClient
from utils.helpers import fmt_coins, fmt_time, get_or_register
from utils.decorators import alive_only

logger = logging.getLogger("Module.RPG")
UTC = timezone.utc

# Kill flavour texts
_KILL_MSGS = [
    "⚔️ **{a}** sliced through **{b}** like warm butter!",
    "💀 **{a}** obliterated **{b}** in a single devastating strike!",
    "🗡️ **{a}** delivered a fatal blow — **{b}** didn't stand a chance!",
    "☠️ **{b}** has fallen at the hands of **{a}**!",
    "🌪️ **{a}** unleashed a storm of fury on **{b}** — absolutely brutal!",
    "🔥 **{a}** set **{b}** ablaze and walked away without looking back!",
]


# ══════════════════════════════════════════════════════════════════════════════
# Shared protection check
# ══════════════════════════════════════════════════════════════════════════════

def _is_protected(user_doc: dict) -> bool:
    pt = user_doc.get("protect_until")
    if not pt:
        return False
    if isinstance(pt, str):
        pt = datetime.fromisoformat(pt)
    if pt.tzinfo is None:
        pt = pt.replace(tzinfo=UTC)
    return pt > datetime.now(UTC)


def _shield_remaining(user_doc: dict) -> str:
    pt = user_doc.get("protect_until")
    if not pt:
        return "0s"
    if isinstance(pt, str):
        pt = datetime.fromisoformat(pt)
    if pt.tzinfo is None:
        pt = pt.replace(tzinfo=UTC)
    remaining = pt - datetime.now(UTC)
    return fmt_time(max(0, int(remaining.total_seconds())))


# ══════════════════════════════════════════════════════════════════════════════
# /rob
# ══════════════════════════════════════════════════════════════════════════════

@Client.on_message(filters.group & filters.command("rob"))
@alive_only
async def rob_cmd(client: Client, message: Message) -> None:
    if not message.reply_to_message:
        await message.reply("🔫 **Reply to someone's message to rob them!**")
        return

    target  = message.reply_to_message.from_user
    robber  = message.from_user

    if target.is_bot or target.id == robber.id:
        await message.reply("❌ Invalid target!")
        return

    # Cooldown
    cd = await RedisClient.get_cd(robber.id, "rob")
    if cd:
        await message.reply(
            f"⏰ **Rob on cooldown!**  Try again in `{fmt_time(cd)}`"
        )
        return

    robber_doc = await get_or_register(robber)
    victim_doc = await get_or_register(target)

    # Shield check
    if _is_protected(victim_doc):
        await message.reply(
            f"🛡️ **{target.first_name}** is shielded!\n"
            f"Their protection expires in `{_shield_remaining(victim_doc)}`."
        )
        return

    if victim_doc["coins"] < Config.ROB_MIN_VICTIM:
        await message.reply(
            f"💸 **{target.first_name}** is broke — not worth robbing!"
        )
        return

    # Set cooldown before outcome (prevents spam on crash)
    await RedisClient.set_cd(robber.id, "rob", Config.ROB_COOLDOWN)

    # ── Outcome ───────────────────────────────────────────────────────────────
    if random.random() < Config.ROB_FAIL_CHANCE:
        # Caught!
        penalty = max(50, min(int(robber_doc["coins"] * Config.ROB_PENALTY), 5_000))
        await MongoDB.inc_user(robber.id, coins=-penalty)
        await MongoDB.inc_user(target.id, coins=penalty)
        await MongoDB.log_transaction(robber.id, target.id, penalty, "rob_fail")

        await message.reply(
            f"🚔 **BUSTED!** The robbery failed!\n\n"
            f"**{target.first_name}** caught **{robber.first_name}** red-handed!\n"
            f"Penalty paid: `💰 {penalty:,}`\n\n"
            f"⏰ Cooldown: `{fmt_time(Config.ROB_COOLDOWN)}`"
        )
    else:
        # Success
        pct    = random.uniform(Config.ROB_STEAL_MIN, Config.ROB_STEAL_MAX)
        stolen = max(50, int(victim_doc["coins"] * pct))
        await MongoDB.inc_user(target.id, coins=-stolen)
        await MongoDB.inc_user(robber.id, coins=stolen)
        await MongoDB.log_transaction(robber.id, target.id, stolen, "rob")

    # Beautiful & professional heist message
        await message.reply(
        f"💰 **HEIST SUCCESSFUL!** 🎉\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🕵️‍♂️ **Robber:** {robber.first_name}\n"
        f"🎯 **Target:** {target.first_name}\n"
        f"💸 **Loot:** `💰 {stolen:,} coins` ({pct*100:.1f}% stolen)\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏰ **Next Rob available in:** `{fmt_time(Config.ROB_COOLDOWN)}`"
        )


# ══════════════════════════════════════════════════════════════════════════════
# /kill
# ══════════════════════════════════════════════════════════════════════════════

@Client.on_message(filters.group & filters.command("kill"))
@alive_only
async def kill_cmd(client: Client, message: Message) -> None:
    if not message.reply_to_message:
        await message.reply("⚔️ **Reply to someone's message to attack them!**")
        return

    target = message.reply_to_message.from_user
    killer = message.from_user

    if target.is_bot or target.id == killer.id:
        await message.reply("❌ Invalid target!")
        return

    cd = await RedisClient.get_cd(killer.id, "kill")
    if cd:
        await message.reply(f"⏰ **Kill on cooldown!** Try again in `{fmt_time(cd)}`")
        return

    killer_doc = await get_or_register(killer)
    victim_doc = await get_or_register(target)

    if _is_protected(victim_doc):
        await message.reply(
            f"🛡️ **{target.first_name}**'s shield blocked your attack!"
        )
        return

    await RedisClient.set_cd(killer.id, "kill", Config.KILL_COOLDOWN)

    # Calculate loot
    xp_drain   = max(10, int(victim_doc.get("xp", 0)    * Config.KILL_XP_STEAL))
    coin_drain  = max( 0, int(victim_doc.get("coins", 0) * Config.KILL_COIN_STEAL))
    xp_gain    = xp_drain // 2

    # Put victim in DEAD state
    dead_until = (datetime.now(UTC) + timedelta(seconds=Config.DEATH_DURATION)).isoformat()
    await MongoDB.inc_user(target.id,  xp=-xp_drain,   coins=-coin_drain, deaths=1)
    await MongoDB.update_user(target.id, {"dead_until": dead_until})
    await MongoDB.inc_user(killer.id,  xp=xp_gain,     coins=coin_drain,  kills=1)
    await MongoDB.log_transaction(killer.id, target.id, coin_drain, "kill")

    msg = random.choice(_KILL_MSGS).format(a=killer.first_name, b=target.first_name)

    await message.reply(
        f"☠️ **FATAL STRIKE!** ☠️\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{msg}\n\n"
        f"💸 **Coins drained:** `{fmt_coins(coin_drain)}`\n"
        f"⭐ **XP drained:**   `{xp_drain}`\n"
        f"⏳ **{target.first_name} is DEAD for 24 hours!** (Or use `/heal`)\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"☠️ {target.first_name}'s deaths: `{victim_doc.get('deaths',0)+1}`\n"
        f"🎯 {killer.first_name}'s kills:  `{killer_doc.get('kills',0)+1}`\n\n"
        f"⏰ **Next Kill available in:** `{fmt_time(Config.KILL_COOLDOWN)}`"
    )


# ══════════════════════════════════════════════════════════════════════════════
# /protect
# ══════════════════════════════════════════════════════════════════════════════

@Client.on_message(filters.command("protect"))
@alive_only
async def protect_cmd(client: Client, message: Message) -> None:
    user = await get_or_register(message.from_user)
    uid  = message.from_user.id

    # Already shielded?
    if _is_protected(user):
        await message.reply(
            f"🛡️ **Shield Already Active!**\n\n"
            f"Your protection expires in `{_shield_remaining(user)}`."
        )
        return

    cost = Config.PROTECT_COST
    if user["coins"] < cost:
        await message.reply(
            f"❌ **Not enough coins!**\n"
            f"Shield costs `💰 {cost:,}` · You have `💰 {user['coins']:,}`."
        )
        return

    until = (datetime.now(UTC) + timedelta(seconds=Config.PROTECT_DURATION)).isoformat()
    await MongoDB.inc_user(uid, coins=-cost)
    await MongoDB.update_user(uid, {
        "protect_until": until,
        "notified_shield_6h": False,
        "notified_shield_1h": False,
        "notified_shield_30m": False
    })

    days = Config.PROTECT_DURATION // 86400
    await message.reply(
        f"🛡️ **Shield Activated!**\n\n"
        f"💰 Cost:     `-{cost:,} coins`\n"
        f"⏱️ Duration: `{days} day`\n"
        f"✅ Expires:  `{fmt_time(Config.PROTECT_DURATION)}`\n\n"
        f"_You are immune to /rob and /kill attacks!_"
    )


# ══════════════════════════════════════════════════════════════════════════════
# /heal
# ══════════════════════════════════════════════════════════════════════════════

@Client.on_message(filters.command("heal"))
async def heal_cmd(client: Client, message: Message) -> None:
    user = await get_or_register(message.from_user)
    uid = message.from_user.id

    # Check if dead
    dead_until = user.get("dead_until")
    is_dead = False
    if dead_until:
        if isinstance(dead_until, str):
            du = datetime.fromisoformat(dead_until)
        else:
            du = dead_until
        if du.tzinfo is None:
            du = du.replace(tzinfo=UTC)
        if du > datetime.now(UTC):
            is_dead = True

    if not is_dead:
        await message.reply("💖 **You are already perfectly healthy and full of life!**")
        return

    cost = 1000
    if user["coins"] < cost:
        await message.reply(
            f"❌ **Heal Failed!**\n\n"
            f"Instantly reviving costs `💰 {cost:,}` coins, but you only have `💰 {user['coins']:,}`!\n"
            f"Please wait out your revival time or earn coins from other players."
        )
        return

    await MongoDB.inc_user(uid, coins=-cost)
    await MongoDB.update_user(uid, {"dead_until": None})

    await message.reply(
        f"💖 **REVIVED!** 🎉\n\n"
        f"Deducted: `💰 {cost:,} coins`\n"
        f"Your health has been fully restored! You can now participate in all games and activities again! ✨"
    )

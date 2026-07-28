"""
🎮  GAMES MODULE
────────────────────────────────────────────────────────────
• /rocket <bet> [cashout_mult]  — animated multiplier crash game
• /scrabble                     — group word-unscramble race
• /game                         — interactive info / help hub
"""

from __future__ import annotations

import asyncio
import logging
import math
import random
import time

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
from utils.helpers import fmt_coins, get_or_register
from utils.keyboards import back_to_game_menu, game_main_menu

logger = logging.getLogger("Module.Games")


# ══════════════════════════════════════════════════════════════════════════════
# Scrabble word list
# ══════════════════════════════════════════════════════════════════════════════

SCRABBLE_WORDS = [
    "anime","waifu","gacha","ninja","sword","magic","demon","angel","power",
    "brave","quest","ghost","flame","storm","blade","frost","dragon","knight",
    "witch","rogue","shield","arrow","chaos","dream","spirit","curse","lunar",
    "solar","prism","ember","venom","grail","forge","astral","cipher","mirage",
    "oracle","specter","zenith","bastion","chroma","eclipse","fable","herald",
    "ignis","jester","karma","legacy","mystic","nova","phantom","quill","realm",
    "shard","titan","umbra","valor","wraith","xenos","yokai","zephyr",
]


def _scramble(word: str) -> str:
    chars = list(word)
    for _ in range(20):
        random.shuffle(chars)
        if "".join(chars) != word:
            return "".join(chars)
    return "".join(reversed(chars))


# ══════════════════════════════════════════════════════════════════════════════
# /scrabble
# ══════════════════════════════════════════════════════════════════════════════

@Client.on_message(filters.group & filters.command("scrabble"))
async def scrabble_cmd(client: Client, message: Message) -> None:
    chat_id = message.chat.id
    existing = await RedisClient.get_scrabble(chat_id)
    if existing:
        await message.reply(
            f"🔤 A scrabble game is already running!\n"
            f"Scrambled word: **`{existing['scrambled'].upper()}`**"
        )
        return

    word      = random.choice(SCRABBLE_WORDS)
    scrambled = _scramble(word)
    reward    = random.randint(Config.SCRABBLE_MIN_REWARD, Config.SCRABBLE_MAX_REWARD)

    await RedisClient.set_scrabble(chat_id, {
        "word":     word,
        "scrambled": scrambled,
        "reward":   reward,
    })

    await message.reply(
        f"🔤 **SCRABBLE TIME!**\n\n"
        f"Unscramble this word:\n"
        f"```\n{scrambled.upper()}\n```\n"
        f"🏆 Reward: `💰 {reward}` + `⭐ 20 XP`\n"
        f"⏰ You have `{Config.SCRABBLE_TIMEOUT}` seconds!"
    )

    asyncio.create_task(_scrabble_expire(client, chat_id, word))


async def _scrabble_expire(client: Client, chat_id: int, word: str) -> None:
    await asyncio.sleep(Config.SCRABBLE_TIMEOUT + 3)
    game = await RedisClient.get_scrabble(chat_id)
    if game and game.get("word") == word:
        await RedisClient.del_scrabble(chat_id)
        try:
            await client.send_message(
                chat_id,
                f"⏰ **Time's up!** Nobody solved it.\n"
                f"The word was: **`{word.upper()}`**"
            )
        except Exception:
            pass


@Client.on_message(filters.group & filters.text & ~filters.via_bot, group=5)
async def scrabble_check(client: Client, message: Message) -> None:
    """Check all group text messages against active scrabble game."""
    if not message.text or message.text.startswith("/"):
        return

    chat_id = message.chat.id
    game    = await RedisClient.get_scrabble(chat_id)
    if not game:
        return

    if message.text.strip().lower() == game["word"].lower():
        await RedisClient.del_scrabble(chat_id)
        await get_or_register(message.from_user)
        await MongoDB.inc_user(message.from_user.id,
                               coins=game["reward"], xp=20)
        await message.reply(
            f"🎉 **CORRECT!** → **`{game['word'].upper()}`**\n\n"
            f"🏆 **{message.from_user.first_name}** wins!\n"
            f"  `+💰 {game['reward']:,}` coins · `+⭐ 20` XP"
        )


# ══════════════════════════════════════════════════════════════════════════════
# /rocket
# ══════════════════════════════════════════════════════════════════════════════

def _crash_point() -> float:
    """House-edge exponential: ~55 % chance < 2×, ~25 % chance 2-5×, tail ∞."""
    r = random.random()
    if r < 0.01:          # guaranteed low
        return round(random.uniform(1.01, 1.09), 2)
    val = 0.99 / (1.0 - r)
    return round(min(val, 1000.0), 2)


ROCKET_STAGES = [
    (1.0, 2.0,   "🟢 SAFE",    0.8),
    (2.0, 5.0,   "🟡 RISKY",   0.6),
    (5.0, 20.0,  "🟠 DANGER",  0.5),
    (20.0, 9999, "🔴 EXTREME", 0.4),
]

CASHOUT_KB = lambda uid, bet: InlineKeyboardMarkup([[
    InlineKeyboardButton("💸 CASH OUT!", callback_data=f"rocket_co:{uid}:{bet}")
]])


@Client.on_message(filters.command("rocket"))
async def rocket_cmd(client: Client, message: Message) -> None:
    parts = message.text.split()

    if len(parts) < 2:
        await message.reply(
            "🚀 **ROCKET GAME**\n\n"
            "**Usage:**\n"
            "`/rocket <bet>` — manual cashout\n"
            "`/rocket <bet> <mult>` — auto-cashout (e.g. `/rocket 1000 2.5`)\n\n"
            f"Min: `💰 {Config.ROCKET_MIN_BET:,}` · "
            f"Max: `💰 {Config.ROCKET_MAX_BET:,}`\n\n"
            "_The multiplier grows — cash out before the rocket explodes!_"
        )
        return

    try:
        bet = int(parts[1].replace(",", ""))
    except ValueError:
        await message.reply("❌ Invalid bet amount.")
        return

    if not (Config.ROCKET_MIN_BET <= bet <= Config.ROCKET_MAX_BET):
        await message.reply(
            f"❌ Bet must be between "
            f"`💰 {Config.ROCKET_MIN_BET:,}` and `💰 {Config.ROCKET_MAX_BET:,}`."
        )
        return

    user = await get_or_register(message.from_user)
    if user["coins"] < bet:
        await message.reply(f"❌ You only have `💰 {user['coins']:,}` coins.")
        return

    # Check no active game
    if await RedisClient.get_rocket(message.from_user.id):
        await message.reply("⚠️ You already have a rocket in flight!")
        return

    # Parse optional auto-cashout
    auto_co = None
    if len(parts) >= 3:
        try:
            auto_co = float(parts[2])
            if auto_co < 1.10:
                await message.reply("❌ Auto-cashout must be ≥ 1.10×.")
                return
        except ValueError:
            pass

    # Deduct bet immediately
    await MongoDB.inc_user(message.from_user.id, coins=-bet)
    crash = _crash_point()

    # ── Auto-cashout resolution (instant) ────────────────────────────────────
    if auto_co is not None:
        if auto_co <= crash:
            win   = int(bet * auto_co)
            profit = win - bet
            await MongoDB.inc_user(message.from_user.id, coins=win)
            await message.reply(
                f"🚀 **ROCKET** — Auto-cashout at `{auto_co}x`\n\n"
                f"✅ Cashed out safely!\n"
                f"💰 `{bet:,}` → `{win:,}` (`+{profit:,}`)\n"
                f"💥 Rocket crashed at `{crash}x`"
            )
        else:
            await message.reply(
                f"🚀 **ROCKET** — Auto-cashout at `{auto_co}x`\n\n"
                f"💥 CRASHED at `{crash}x` — before your target!\n"
                f"💸 Lost `{bet:,}` coins."
            )
        return

    # ── Interactive game ─────────────────────────────────────────────────────
    uid = message.from_user.id
    await RedisClient.set_rocket(uid, {
        "bet": bet, "crash": crash,
        "start": time.time(), "cashed": False
    })

    sent = await message.reply(
        f"🚀 **ROCKET LAUNCHED!**\n\n"
        f"💰 Bet: `{bet:,} coins`\n"
        f"📈 Multiplier: `1.00×`\n\n"
        f"💥 _Press CASH OUT before it explodes!_",
        reply_markup=CASHOUT_KB(uid, bet)
    )

    asyncio.create_task(_rocket_ticker(client, uid, bet, crash, sent))


async def _rocket_ticker(client, uid, bet, crash, sent_msg) -> None:
    mult = 1.0
    step = 0.08

    while mult < crash:
        await asyncio.sleep(0.9)
        mult = round(mult + step, 2)
        step = round(step * 1.07, 4)  # accelerate

        state = await RedisClient.get_rocket(uid)
        if not state or state.get("cashed"):
            return

        if mult >= crash:
            break

        # Find stage label
        stage_lbl = "🟢 SAFE"
        for lo, hi, lbl, _ in ROCKET_STAGES:
            if lo <= mult < hi:
                stage_lbl = lbl
                break

        bar_len = min(int(mult * 2), 20)
        bar     = "▓" * bar_len + "░" * max(0, 20 - bar_len)
        proj    = int(bet * mult)

        try:
            await sent_msg.edit_text(
                f"🚀 **ROCKET IN FLIGHT!**  {stage_lbl}\n\n"
                f"`[{bar}]`\n"
                f"💰 Bet: `{bet:,}` · 📈 `{mult:.2f}×`\n"
                f"💵 If cashed now: `+{proj - bet:,}`\n\n"
                f"💥 _CRASH could happen any moment!_",
                reply_markup=CASHOUT_KB(uid, bet)
            )
        except Exception:
            pass

    # Crashed!
    await RedisClient.del_rocket(uid)
    try:
        await sent_msg.edit_text(
            f"💥 **CRASHED at `{crash}×`!**\n\n"
            f"Too slow! You lost `💰 {bet:,}` coins.\n"
            f"Better luck next time! 🚀"
        )
    except Exception:
        pass


@Client.on_callback_query(filters.regex(r"^rocket_co:(\d+):(\d+)$"))
async def rocket_cashout_cb(client: Client, cb: CallbackQuery) -> None:
    _, uid_s, bet_s = cb.data.split(":")
    uid = int(uid_s)
    bet = int(bet_s)

    if cb.from_user.id != uid:
        await cb.answer("Not your rocket!", show_alert=True)
        return

    state = await RedisClient.get_rocket(uid)
    if not state:
        await cb.answer("💥 Already crashed!", show_alert=True)
        return
    if state.get("cashed"):
        await cb.answer("Already cashed out!", show_alert=True)
        return

    elapsed = time.time() - state["start"]
    # Re-derive approx multiplier from elapsed time
    mult = 1.0
    step = 0.08
    sim_t = 0.0
    while sim_t < elapsed and mult < state["crash"]:
        mult  = round(mult + step, 2)
        step  = round(step * 1.07, 4)
        sim_t += 0.9
    mult = round(min(mult, state["crash"]), 2)

    state["cashed"] = True
    await RedisClient.set_rocket(uid, state)

    win    = int(bet * mult)
    profit = win - bet
    await MongoDB.inc_user(uid, coins=win)

    await cb.answer(f"✅ Cashed at {mult:.2f}× → +{profit:,} coins!", show_alert=True)
    try:
        await cb.message.edit_text(
            f"✅ **CASHED OUT at `{mult:.2f}×`!**\n\n"
            f"💰 `{bet:,}` → `{win:,}` (`+{profit:,}`)\n"
            f"🚀 Rocket crashed at `{state['crash']}×`"
        )
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# /game  — info hub
# ══════════════════════════════════════════════════════════════════════════════

GAME_INFO: dict[str, str] = {
    "rocket": (
        "🚀 **ROCKET GAME**\n\n"
        "**Command:** `/rocket <bet> [mult]`\n\n"
        "The rocket launches and its multiplier climbs.\n"
        "Cash out before it explodes!\n\n"
        "• `/rocket 1000`       — manual cashout button\n"
        "• `/rocket 1000 2.5`   — auto-cashout at 2.5×\n\n"
        f"Min: `💰 {Config.ROCKET_MIN_BET:,}` · Max: `💰 {Config.ROCKET_MAX_BET:,}`"
    ),
    "scrabble": (
        "🔤 **SCRABBLE GAME**\n\n"
        "**Command:** `/scrabble`\n\n"
        "A scrambled word appears — type the correct word first!\n\n"
        f"🏆 Reward: `💰 {Config.SCRABBLE_MIN_REWARD}–{Config.SCRABBLE_MAX_REWARD}` + `⭐ 20 XP`\n"
        f"⏰ Time limit: `{Config.SCRABBLE_TIMEOUT}s`\n\n"
        "_One game per group at a time._"
    ),
    "economy": (
        "💰 **ECONOMY GUIDE**\n\n"
        "• `/bal` — Your wallet card (PIL stat card)\n"
        "• `/daily` — Claim daily reward + streak bonus\n"
        "• `/pay <amt>` — Send coins (reply to user)\n"
        "• `/gift <amt>` or `/gift waifu <#>` — Gift items\n"
        "• `/top` — Global rich leaderboard\n\n"
        f"**Starter coins:** `💰 {Config.STARTER_COINS:,}`\n"
        f"**Daily reward:** `💰 {Config.DAILY_COINS:,}` + `💎 {Config.DAILY_GEMS}`\n"
        f"**Streak bonus:** +`{Config.DAILY_STREAK_BONUS}` coins/day"
    ),
    "rpg": (
        "⚔️ **RPG GUIDE**\n\n"
        "• `/rob` — Steal 10-25 % coins (reply to user)\n"
        "• `/kill` — Drain XP + 5 % coins (reply to user)\n"
        "• `/protect` — Buy a 2-day shield\n\n"
        f"⚠️ Rob fail chance: `{int(Config.ROB_FAIL_CHANCE*100)}%` — you pay a penalty!\n"
        f"🛡️ Shield cost: `💰 {Config.PROTECT_COST:,}` · Duration: 2 days\n"
        f"⏰ Rob CD: `1h` · Kill CD: `2h`"
    ),
    "gacha": (
        "🌸 **GACHA GUIDE**\n\n"
        "Characters auto-spawn every **100 group messages**.\n"
        "Use `/grasp` or `/claim` to catch!\n\n"
        "**Rarities & Weights:**\n"
        "⬜ Common `(50%)`  ·  🟦 Rare `(30%)`\n"
        "🟪 Epic `(15%)`   ·  🟨 Legendary `(4%)`\n"
        "🌈 Velora `(1%)`\n\n"
        "• `/harem` — View your collection (paginated)\n"
        f"• `/explore` — Instant discover (`💰 {Config.EXPLORE_COST:,}` coins)\n"
        "• `/marry <#>` — Set a waifu from your harem\n"
        "• `/propose` — Propose to another user"
    ),
    "commands": (
        "📖 **ALL COMMANDS**\n\n"
        "**🌸 Gacha**\n"
        "`/grasp` `/claim` · `/harem` · `/explore`\n"
        "`/marry <#>` · `/propose`\n\n"
        "**💰 Economy**\n"
        "`/bal` · `/daily` · `/pay <amt>` · `/gift`\n"
        "`/top` · `/leaderboard`\n\n"
        "**⚔️ RPG**\n"
        "`/rob` · `/kill` · `/protect`\n\n"
        "**🎮 Games**\n"
        "`/rocket <bet> [mult]` · `/scrabble` · `/game`\n\n"
        "**⚙️ Admin**\n"
        "`/setgroup <key> <value>`\n"
        "`/start` · `/help`"
    ),
}


@Client.on_message(filters.command(["game", "games", "help"]))
async def game_menu_cmd(client: Client, message: Message) -> None:
    await message.reply(
        "🎮 **ZEXIS GAME CENTER**\n\nSelect a topic below:",
        reply_markup=game_main_menu()
    )


@Client.on_callback_query(filters.regex(r"^ginfo:(\w+)$"))
async def ginfo_cb(client: Client, cb: CallbackQuery) -> None:
    key = cb.data.split(":")[1]

    if key == "main":
        await cb.message.edit_text(
            "🎮 **ZEXIS GAME CENTER**\n\nSelect a topic below:",
            reply_markup=game_main_menu()
        )
    elif key in GAME_INFO:
        await cb.message.edit_text(
            GAME_INFO[key],
            reply_markup=back_to_game_menu()
        )
    else:
        await cb.answer("Unknown section.", show_alert=True)
        return

    await cb.answer()

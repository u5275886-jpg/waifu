"""
Handler decorators.
Usage:
    @Client.on_message(filters.command("rob"))
    @group_only
    async def rob_handler(client, message): ...
"""

from __future__ import annotations

import functools
import logging

from pyrogram.types import Message

from database.redis_client import RedisClient
from utils.helpers import fmt_time

logger = logging.getLogger("Utils.Decorators")


# ── group_only ────────────────────────────────────────────────────────────────

def group_only(func):
    @functools.wraps(func)
    async def wrapper(client, message: Message, *a, **kw):
        if message.chat.type.value == "private":
            await message.reply("❌ This command only works inside groups!")
            return
        return await func(client, message, *a, **kw)
    return wrapper


# ── owner_only ────────────────────────────────────────────────────────────────

def owner_only(func):
    from config import Config

    @functools.wraps(func)
    async def wrapper(client, message: Message, *a, **kw):
        if message.from_user.id != Config.BOT_OWNER:
            await message.reply("❌ Owner-only command.")
            return
        return await func(client, message, *a, **kw)
    return wrapper


# ── cooldown ──────────────────────────────────────────────────────────────────

def cooldown(seconds: int, key: str | None = None):
    """
    Apply a per-user cooldown.
    key defaults to the function name.

    Example:
        @cooldown(3600, "rob")
        async def rob_handler(...): ...
    """
    def decorator(func):
        action = key or func.__name__

        @functools.wraps(func)
        async def wrapper(client, message: Message, *a, **kw):
            uid = message.from_user.id
            rem = await RedisClient.get_cd(uid, action)
            if rem:
                await message.reply(
                    f"⏰ **Cooldown active!**\n"
                    f"Try */{action}* again in `{fmt_time(rem)}`."
                )
                return
            # Set cooldown BEFORE executing so a crash doesn't reset it
            await RedisClient.set_cd(uid, action, seconds)
            return await func(client, message, *a, **kw)

        return wrapper
    return decorator


# ── registered (auto-register user) ──────────────────────────────────────────

def registered(func):
    @functools.wraps(func)
    async def wrapper(client, message: Message, *a, **kw):
        from utils.helpers import get_or_register
        await get_or_register(message.from_user)
        return await func(client, message, *a, **kw)
    return wrapper

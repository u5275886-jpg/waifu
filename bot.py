#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║          ZEXIS WAIFU BOT — Advanced Multi-Tenant             ║
║   Gacha · Dual Economy · RPG Combat · Mini-Games · Admin     ║
╚══════════════════════════════════════════════════════════════╝
"""

import asyncio
import logging
import sys
from pyrogram import Client, idle
from config import Config
from database.mongo import MongoDB
from database.redis_client import RedisClient

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(name)-22s │ %(levelname)-8s │ %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("zexis.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("ZexisBot")


# ── Pyrogram Client ────────────────────────────────────────────────────────────
app = Client(
    name="ZexisWaifuBot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
    plugins={"root": "modules"},   # Auto-discover all handlers in /modules/
    sleep_threshold=30,
    max_concurrent_transmissions=8,
)


# ── Lifecycle ──────────────────────────────────────────────────────────────────
async def startup() -> None:
    logger.info("🔄  Connecting to MongoDB …")
    await MongoDB.connect()
    logger.info("✅  MongoDB ready")

    logger.info("🔄  Connecting to Redis …")
    await RedisClient.connect()
    logger.info("✅  Redis ready")


async def shutdown() -> None:
    logger.info("🔴  Shutting down services …")
    await MongoDB.disconnect()
    await RedisClient.disconnect()
    logger.info("👋  Goodbye!")


async def protection_notifier_loop(client: Client) -> None:
    """
    Background task that periodically checks users' protection shield status.
    Informs user when their shield is expiring in:
    - <= 6 hours
    - <= 1 hour
    - <= 30 minutes
    """
    from datetime import datetime, timezone
    UTC = timezone.utc
    logger.info("🛡️ Protection notifier loop started.")
    while True:
        try:
            await asyncio.sleep(60)  # Check every minute
            now = datetime.now(UTC)
            # Find users who have protect_until in the future
            cursor = MongoDB.users.find({"protect_until": {"$ne": None}})
            async for user in cursor:
                pt_raw = user.get("protect_until")
                if not pt_raw:
                    continue
                if isinstance(pt_raw, str):
                    pt = datetime.fromisoformat(pt_raw)
                else:
                    pt = pt_raw
                if pt.tzinfo is None:
                    pt = pt.replace(tzinfo=UTC)

                if pt <= now:
                    # Shield has already expired, clean up protect_until
                    await MongoDB.update_user(user["user_id"], {"protect_until": None})
                    try:
                        await client.send_message(
                            user["user_id"],
                            f"💔 **Your Protection Shield has fully expired!**\n\n"
                            f"You are now vulnerable to `/rob` and `/kill` attacks. "
                            f"Buy a new shield using `/protect` immediately! 🛡️"
                        )
                    except Exception:
                        pass
                    continue

                remaining = (pt - now).total_seconds()
                uid = user["user_id"]

                # Check <= 30 minutes (1800s)
                if remaining <= 1800:
                    if not user.get("notified_shield_30m"):
                        await MongoDB.update_user(uid, {"notified_shield_30m": True})
                        try:
                            await client.send_message(
                                uid,
                                f"⚠️ **CRITICAL WARNING!**\n\n"
                                f"Your Protection Shield is about to expire in less than **30 minutes**! "
                                f"Hurry up and purchase a new one with `/protect` to stay safe! 🛡️"
                            )
                        except Exception:
                            pass
                # Check <= 1 hour (3600s)
                elif remaining <= 3600:
                    if not user.get("notified_shield_1h"):
                        await MongoDB.update_user(uid, {"notified_shield_1h": True})
                        try:
                            await client.send_message(
                                uid,
                                f"⚠️ **Shield Expiry Alert!**\n\n"
                                f"Your Protection Shield is expiring in less than **1 hour**! "
                                f"Make sure you have enough coins to run `/protect`! 🛡️"
                            )
                        except Exception:
                            pass
                # Check <= 6 hours (21600s)
                elif remaining <= 21600:
                    if not user.get("notified_shield_6h"):
                        await MongoDB.update_user(uid, {"notified_shield_6h": True})
                        try:
                            await client.send_message(
                                uid,
                                f"ℹ️ **Shield Expiry Reminder!**\n\n"
                                f"Your Protection Shield has less than **6 hours** remaining. "
                                f"Plan ahead and buy a shield using `/protect` to prevent losses! 🛡️"
                            )
                        except Exception:
                            pass
        except Exception as e:
            logger.error(f"Error in protection notifier loop: {e}", exc_info=True)


async def main() -> None:
    await startup()

    async with app:
        # Start background task
        asyncio.create_task(protection_notifier_loop(app))
        me = await app.get_me()
        banner = f"""
╔══════════════════════════════════════════════════╗
║         🌸  ZEXIS WAIFU BOT  ONLINE 🌸          ║
║                                                  ║
║   Bot      : @{me.username:<33}║
║   User ID  : {me.id:<35}║
║   Version  : 2.0.0 (Pyrogram {__import__('pyrogram').__version__:<14})║
╚══════════════════════════════════════════════════╝"""
        print(banner)
        logger.info(f"@{me.username} is live!")
        await idle()

    await shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted — exiting cleanly.")

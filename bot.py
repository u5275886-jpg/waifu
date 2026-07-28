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


async def main() -> None:
    await startup()

    async with app:
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

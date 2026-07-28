"""
MongoDB Async Driver (motor) — collection helpers & indexes.
All DB interaction routes through this class so nothing else imports motor directly.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from config import Config

logger = logging.getLogger("DB.Mongo")


class MongoDB:
    client: AsyncIOMotorClient | None = None
    db: AsyncIOMotorDatabase | None = None

    # ── Collection references ──────────────────────────────────────────────────
    users        = None
    groups       = None
    characters   = None
    marriages    = None
    transactions = None

    # ══════════════════════════════════════════════════════════════════════════
    # Lifecycle
    # ══════════════════════════════════════════════════════════════════════════

    @classmethod
    async def connect(cls) -> None:
        cls.client = AsyncIOMotorClient(
            Config.MONGO_URI,
            serverSelectionTimeoutMS=5000,
        )
        cls.db = cls.client[Config.DB_NAME]

        cls.users        = cls.db.users
        cls.groups       = cls.db.groups
        cls.characters   = cls.db.characters
        cls.marriages    = cls.db.marriages
        cls.transactions = cls.db.transactions

        await cls._create_indexes()
        logger.info("Collections ready: users · groups · characters · marriages · transactions")

    @classmethod
    async def disconnect(cls) -> None:
        if cls.client:
            cls.client.close()

    @classmethod
    async def _create_indexes(cls) -> None:
        await cls.users.create_index("user_id",  unique=True)
        await cls.users.create_index([("coins", -1)])
        await cls.users.create_index([("xp",    -1)])
        await cls.groups.create_index("chat_id", unique=True)
        await cls.characters.create_index("char_id", unique=True)
        await cls.characters.create_index("rarity")

    # ══════════════════════════════════════════════════════════════════════════
    # User Operations
    # ══════════════════════════════════════════════════════════════════════════

    @classmethod
    async def get_user(cls, user_id: int) -> dict | None:
        return await cls.users.find_one({"user_id": user_id})

    @classmethod
    async def register_user(cls, user_id: int, first_name: str,
                            username: str | None = None) -> dict:
        user: dict[str, Any] = {
            "user_id":      user_id,
            "first_name":   first_name,
            "username":     username,
            "coins":        Config.STARTER_COINS,
            "gems":         Config.STARTER_GEMS,
            "xp":           0,
            "level":        1,
            "kills":        0,
            "deaths":       0,
            "daily_streak": 0,
            "last_daily":   None,
            "characters":   [],          # embedded character docs
            "married_to":   None,        # user_id if married to a user
            "married_waifu": None,       # char_id if married to a waifu
            "protect_until": None,
            "created_at":   datetime.utcnow(),
        }
        await cls.users.insert_one(user)
        return user

    @classmethod
    async def update_user(cls, user_id: int, fields: dict) -> None:
        await cls.users.update_one({"user_id": user_id}, {"$set": fields})

    @classmethod
    async def inc_user(cls, user_id: int, **fields) -> None:
        """Increment one or more numeric fields atomically."""
        await cls.users.update_one({"user_id": user_id}, {"$inc": fields})

    @classmethod
    async def push_character(cls, user_id: int, char_entry: dict) -> None:
        await cls.users.update_one(
            {"user_id": user_id},
            {"$push": {"characters": char_entry}},
        )

    @classmethod
    async def pull_character(cls, user_id: int, char_id: str) -> None:
        await cls.users.update_one(
            {"user_id": user_id},
            {"$pull": {"characters": {"char_id": char_id}}},
        )

    # ── Leaderboard helpers ───────────────────────────────────────────────────

    @classmethod
    async def top_by_coins(cls, limit: int = 10) -> list[dict]:
        cursor = cls.users.find({}).sort("coins", -1).limit(limit)
        return await cursor.to_list(length=limit)

    @classmethod
    async def top_by_xp(cls, limit: int = 10) -> list[dict]:
        cursor = cls.users.find({}).sort("xp", -1).limit(limit)
        return await cursor.to_list(length=limit)

    @classmethod
    async def get_rank(cls, user_id: int) -> int:
        user = await cls.get_user(user_id)
        if not user:
            return 0
        ahead = await cls.users.count_documents({"coins": {"$gt": user["coins"]}})
        return ahead + 1

    # ══════════════════════════════════════════════════════════════════════════
    # Group Operations
    # ══════════════════════════════════════════════════════════════════════════

    @classmethod
    async def get_group(cls, chat_id: int) -> dict | None:
        return await cls.groups.find_one({"chat_id": chat_id})

    @classmethod
    async def register_group(cls, chat_id: int, title: str) -> dict:
        group: dict[str, Any] = {
            "chat_id": chat_id,
            "title":   title,
            "settings": {
                "spawn_enabled":   True,
                "nsfw_filter":     True,
                "toxicity_filter": False,
                "custom_prefix":   "/",
            },
            "total_spawns": 0,
            "total_claims": 0,
            "created_at":   datetime.utcnow(),
        }
        await cls.groups.insert_one(group)
        return group

    @classmethod
    async def update_group(cls, chat_id: int, fields: dict) -> None:
        await cls.groups.update_one({"chat_id": chat_id}, {"$set": fields})

    @classmethod
    async def ensure_group(cls, chat_id: int, title: str) -> dict:
        """Get or create a group document."""
        group = await cls.get_group(chat_id)
        return group if group else await cls.register_group(chat_id, title)

    # ══════════════════════════════════════════════════════════════════════════
    # Marriage Operations
    # ══════════════════════════════════════════════════════════════════════════

    @classmethod
    async def get_marriage(cls, user_id: int) -> dict | None:
        return await cls.marriages.find_one({
            "$or": [{"user1_id": user_id}, {"user2_id": user_id}]
        })

    @classmethod
    async def create_marriage(cls, u1: int, u2: int) -> None:
        await cls.marriages.insert_one({
            "user1_id":   u1,
            "user2_id":   u2,
            "created_at": datetime.utcnow(),
        })

    @classmethod
    async def delete_marriage(cls, user_id: int) -> None:
        await cls.marriages.delete_one({
            "$or": [{"user1_id": user_id}, {"user2_id": user_id}]
        })

    # ══════════════════════════════════════════════════════════════════════════
    # Transaction Log (optional analytics)
    # ══════════════════════════════════════════════════════════════════════════

    @classmethod
    async def log_transaction(cls, from_id: int, to_id: int,
                              amount: int, kind: str) -> None:
        await cls.transactions.insert_one({
            "from":   from_id,
            "to":     to_id,
            "amount": amount,
            "kind":   kind,      # "pay" | "gift" | "rob" | "kill" | "daily"
            "ts":     datetime.utcnow(),
        })

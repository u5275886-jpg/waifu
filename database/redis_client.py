"""
Redis async client (redis-py ≥ 4.2).
Handles:
  • per-group message counters (spawn trigger)
  • active spawn state
  • per-user cooldowns (rob / kill)
  • in-flight game state (scrabble, rocket)
"""

from __future__ import annotations

import json
import logging
from typing import Any

import redis.asyncio as redis
from config import Config

logger = logging.getLogger("DB.Redis")


class RedisClient:
    client: redis.Redis | None = None

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    @classmethod
    async def connect(cls) -> None:
        cls.client = redis.from_url(
            Config.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
        await cls.client.ping()
        logger.info(f"Connected → {Config.REDIS_URL}")

    @classmethod
    async def disconnect(cls) -> None:
        if cls.client:
            await cls.client.aclose()

    # ── Helpers ────────────────────────────────────────────────────────────────

    @classmethod
    def _k(cls, *parts) -> str:
        return ":".join(str(p) for p in parts)

    @classmethod
    async def _set_json(cls, key: str, data: Any, ttl: int) -> None:
        await cls.client.setex(key, ttl, json.dumps(data))

    @classmethod
    async def _get_json(cls, key: str) -> Any | None:
        raw = await cls.client.get(key)
        return json.loads(raw) if raw else None

    # ══════════════════════════════════════════════════════════════════════════
    # Message Counter (per group)
    # ══════════════════════════════════════════════════════════════════════════

    @classmethod
    async def incr_msg(cls, chat_id: int) -> int:
        key = cls._k("chat", chat_id, "msgcount")
        return await cls.client.incr(key)

    @classmethod
    async def reset_msg(cls, chat_id: int) -> None:
        await cls.client.set(cls._k("chat", chat_id, "msgcount"), 0)

    @classmethod
    async def get_msg(cls, chat_id: int) -> int:
        v = await cls.client.get(cls._k("chat", chat_id, "msgcount"))
        return int(v) if v else 0

    # ══════════════════════════════════════════════════════════════════════════
    # Active Spawn (per group)
    # ══════════════════════════════════════════════════════════════════════════

    @classmethod
    async def set_spawn(cls, chat_id: int, char: dict, msg_id: int) -> None:
        key = cls._k("chat", chat_id, "spawn")
        await cls._set_json(key, {"character": char, "message_id": msg_id},
                            Config.SPAWN_TIMEOUT)

    @classmethod
    async def get_spawn(cls, chat_id: int) -> dict | None:
        return await cls._get_json(cls._k("chat", chat_id, "spawn"))

    @classmethod
    async def del_spawn(cls, chat_id: int) -> None:
        await cls.client.delete(cls._k("chat", chat_id, "spawn"))

    # ══════════════════════════════════════════════════════════════════════════
    # Cooldowns (per user × action)
    # ══════════════════════════════════════════════════════════════════════════

    @classmethod
    async def set_cd(cls, user_id: int, action: str, seconds: int) -> None:
        await cls.client.setex(cls._k("cd", user_id, action), seconds, "1")

    @classmethod
    async def get_cd(cls, user_id: int, action: str) -> int:
        """Returns remaining seconds, or 0 if no cooldown."""
        ttl = await cls.client.ttl(cls._k("cd", user_id, action))
        return max(ttl, 0)

    # ══════════════════════════════════════════════════════════════════════════
    # Scrabble (per group)
    # ══════════════════════════════════════════════════════════════════════════

    @classmethod
    async def set_scrabble(cls, chat_id: int, data: dict) -> None:
        await cls._set_json(cls._k("chat", chat_id, "scrabble"),
                            data, Config.SCRABBLE_TIMEOUT + 5)

    @classmethod
    async def get_scrabble(cls, chat_id: int) -> dict | None:
        return await cls._get_json(cls._k("chat", chat_id, "scrabble"))

    @classmethod
    async def del_scrabble(cls, chat_id: int) -> None:
        await cls.client.delete(cls._k("chat", chat_id, "scrabble"))

    # ══════════════════════════════════════════════════════════════════════════
    # Rocket Game (per user)
    # ══════════════════════════════════════════════════════════════════════════

    @classmethod
    async def set_rocket(cls, user_id: int, data: dict) -> None:
        await cls._set_json(cls._k("rocket", user_id), data, 300)

    @classmethod
    async def get_rocket(cls, user_id: int) -> dict | None:
        return await cls._get_json(cls._k("rocket", user_id))

    @classmethod
    async def del_rocket(cls, user_id: int) -> None:
        await cls.client.delete(cls._k("rocket", user_id))

    # ══════════════════════════════════════════════════════════════════════════
    # Propose Locks (prevent double proposals)
    # ══════════════════════════════════════════════════════════════════════════

    @classmethod
    async def set_proposal(cls, proposer_id: int, target_id: int) -> None:
        await cls.client.setex(cls._k("proposal", proposer_id), 120, str(target_id))

    @classmethod
    async def get_proposal(cls, proposer_id: int) -> str | None:
        return await cls.client.get(cls._k("proposal", proposer_id))

    @classmethod
    async def del_proposal(cls, proposer_id: int) -> None:
        await cls.client.delete(cls._k("proposal", proposer_id))

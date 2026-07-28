import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # ── Core Credentials ───────────────────────────────────────────────────────
    API_ID: int        = int(os.environ.get("API_ID", 0))
    API_HASH: str      = os.environ.get("API_HASH", "")
    BOT_TOKEN: str     = os.environ.get("BOT_TOKEN", "")
    BOT_OWNER: int     = int(os.environ.get("BOT_OWNER", 0))

    # ── Database ───────────────────────────────────────────────────────────────
    MONGO_URI: str = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
    DB_NAME: str   = os.environ.get("DB_NAME", "zexisbot")
    REDIS_URL: str = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

    # ── Gacha / Spawn ──────────────────────────────────────────────────────────
    SPAWN_AFTER: int   = int(os.environ.get("SPAWN_AFTER", 100))  # messages
    SPAWN_TIMEOUT: int = int(os.environ.get("SPAWN_TIMEOUT", 300))  # seconds
    EXPLORE_COST: int  = 500   # coins per /explore

    # ── Economy ────────────────────────────────────────────────────────────────
    STARTER_COINS: int       = 300
    STARTER_GEMS: int        = 1
    DAILY_COINS: int         = 1000
    DAILY_GEMS: int          = 5
    DAILY_XP: int            = 50
    DAILY_STREAK_BONUS: int  = 100   # extra coins per streak day
    DAILY_STREAK_7_BONUS: int  = 500
    DAILY_STREAK_30_BONUS: int = 2000

    # ── RPG ────────────────────────────────────────────────────────────────────
    ROB_COOLDOWN: int      = 3600    # 1 h
    ROB_FAIL_CHANCE: float = 0.40    # 40 % fail
    ROB_STEAL_MIN: float   = 0.10    # steal ≥ 10 %
    ROB_STEAL_MAX: float   = 0.25    # steal ≤ 25 %
    ROB_PENALTY: float     = 0.10    # lose 10 % on fail
    ROB_MIN_VICTIM: int    = 100     # victim must have this many coins

    KILL_COOLDOWN: int    = 7200    # 2 h
    KILL_XP_STEAL: float  = 0.15   # drain 15 % XP
    KILL_COIN_STEAL: float = 0.05  # drain 5 % coins

    PROTECT_COST: int     = 500
    PROTECT_DURATION: int = 172800  # 2 days

    # ── Rocket Game ────────────────────────────────────────────────────────────
    ROCKET_MIN_BET: int = 100
    ROCKET_MAX_BET: int = 50_000

    # ── Scrabble ───────────────────────────────────────────────────────────────
    SCRABBLE_TIMEOUT: int    = 60    # seconds
    SCRABBLE_MIN_REWARD: int = 150
    SCRABBLE_MAX_REWARD: int = 600

    # ── Rarity Weights (must sum to 100) ───────────────────────────────────────
    RARITY_WEIGHTS: dict = {
        "Common":    50,
        "Rare":      30,
        "Epic":      15,
        "Legendary":  4,
        "Velora":     1,
    }

    # ── Rarity Visuals ─────────────────────────────────────────────────────────
    RARITY_EMOJI: dict = {
        "Common":    "⬜",
        "Rare":      "🟦",
        "Epic":      "🟪",
        "Legendary": "🟨",
        "Velora":    "🌈",
    }

    RARITY_COLOR: dict = {          # RGB tuples for PIL
        "Common":    (180, 180, 180),
        "Rare":      (30, 144, 255),
        "Epic":      (147,   0, 211),
        "Legendary": (255, 215,   0),
        "Velora":    (255, 105, 180),
    }

    # ── Price Ranges per Rarity ────────────────────────────────────────────────
    RARITY_PRICE_RANGE: dict = {
        "Common":    (100,   500),
        "Rare":      (500,  2000),
        "Epic":     (2000,  8000),
        "Legendary":(8000, 20000),
        "Velora":  (20000,100000),
    }

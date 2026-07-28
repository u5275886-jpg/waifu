# 🌸 Zexis Waifu Bot

> **Advanced multi-tenant Telegram bot** combining Anime Waifu Gacha, dual Economy, RPG Combat, and Mini-Games — built with Pyrogram, MongoDB, and Redis.

---

## ✨ Feature Overview

| Module | Commands | Highlights |
|---|---|---|
| 🌸 **Gacha** | `/grasp` `/claim` `/harem` `/explore` `/marry` `/propose` | Auto-spawn every 100 msgs · 5 rarities · PIL character cards |
| 💰 **Economy** | `/bal` `/daily` `/pay` `/gift` `/top` | PIL stat card · dual currency · streak rewards |
| ⚔️ **RPG** | `/rob` `/kill` `/protect` | Cooldowns · 40 % fail risk · 2-day shield |
| 🎮 **Games** | `/rocket` `/scrabble` `/game` | Animated multiplier · word race · info hub |
| ⚙️ **Admin** | `/setgroup` `/botstats` | Top-5 richest gated · rich welcome card |

---

## 🗂️ Project Structure

```
zexisbot/
├── bot.py                  # Entry point — client init, startup/shutdown
├── config.py               # All tunables in one class
├── requirements.txt
├── .env.example            # Template — copy to .env
│
├── database/
│   ├── mongo.py            # Motor async CRUD — users, groups, marriages
│   └── redis_client.py     # Message counters, cooldowns, game state
│
├── modules/                # Auto-discovered by Pyrogram plugin system
│   ├── gacha.py            # Spawn, claim, harem, explore, marry, propose
│   ├── economy.py          # Bal, daily, pay, gift, leaderboard
│   ├── rpg.py              # Rob, kill, protect
│   ├── games.py            # Rocket, scrabble, game hub
│   └── admin.py            # Setgroup, welcome, start, botstats
│
├── utils/
│   ├── helpers.py          # get_or_register, fmt_coins, pick_character …
│   ├── image_gen.py        # PIL stat card + character card generators
│   ├── keyboards.py        # All InlineKeyboardMarkup builders
│   └── decorators.py       # @cooldown, @group_only, @owner_only
│
├── data/
│   └── characters.json     # 60-character pool (add more freely)
│
└── assets/
    └── fonts/              # Optional: drop NotoSans-Regular.ttf here
```

---

## 🚀 Installation

### 1 — Prerequisites

```bash
# Ubuntu 22.04 / 24.04
sudo apt update && sudo apt install -y python3.12 python3.12-venv \
    python3-pip redis-server mongodb-org git

# Start services
sudo systemctl enable --now redis mongod
```

### 2 — Clone & virtual environment

```bash
git clone https://github.com/youruser/zexisbot.git
cd zexisbot

python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3 — Configure

```bash
cp .env.example .env
nano .env          # Fill in API_ID, API_HASH, BOT_TOKEN, BOT_OWNER
```

| Key | Where to get it |
|---|---|
| `API_ID` / `API_HASH` | [my.telegram.org](https://my.telegram.org) → API development tools |
| `BOT_TOKEN` | [@BotFather](https://t.me/BotFather) → `/newbot` |
| `BOT_OWNER` | [@userinfobot](https://t.me/userinfobot) |

### 4 — (Optional) Custom fonts for PIL

```bash
# Download Noto Sans for crisp stat cards
wget -q https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSans/NotoSans-Regular.ttf \
    -O assets/fonts/NotoSans-Regular.ttf
wget -q https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSans/NotoSans-Bold.ttf \
    -O assets/fonts/NotoSans-Bold.ttf
```

### 5 — Add character images

Edit `data/characters.json` and fill in the `image_url` fields.
Good free sources:

- **nekos.best API** — `https://nekos.best/api/v2/waifu` (random anime images)
- **Safebooru CDN** — direct image links for specific characters
- **Your own CDN / S3 bucket** — most reliable for production

### 6 — Run

```bash
python bot.py
```

---

## ☁️ Production Deployment (systemd)

```ini
# /etc/systemd/system/zexisbot.service
[Unit]
Description=Zexis Waifu Bot
After=network.target mongod.service redis.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/zexisbot
ExecStart=/home/ubuntu/zexisbot/venv/bin/python bot.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now zexisbot
sudo journalctl -u zexisbot -f          # live logs
```

---

## 🐳 Docker (alternative)

```dockerfile
# Dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "bot.py"]
```

```yaml
# docker-compose.yml
version: "3.9"
services:
  bot:
    build: .
    env_file: .env
    restart: unless-stopped
    depends_on: [mongo, redis]

  mongo:
    image: mongo:7
    volumes: [mongo_data:/data/db]

  redis:
    image: redis:7-alpine
    command: redis-server --save 60 1

volumes:
  mongo_data:
```

```bash
docker compose up -d
docker compose logs -f bot
```

---

## 📖 Commands Reference

### 🌸 Gacha
| Command | Description |
|---|---|
| `/grasp` or `/claim` | Claim the currently spawned character (group) |
| `/harem` | Paginated collection viewer with sort options |
| `/explore` | Pay 500 coins to discover a random character instantly |
| `/marry <number>` | Set character #N from your harem as your waifu |
| `/propose` | Reply to a user to send them a marriage proposal |

### 💰 Economy
| Command | Description |
|---|---|
| `/bal` | PIL stat card — coins, gems, rank, XP bar, kills, streak |
| `/daily` | Claim daily reward · streak bonuses at 7 and 30 days |
| `/pay <amount>` | Transfer coins to the replied user |
| `/gift <amount>` | Gift coins to the replied user |
| `/gift waifu <#>` | Transfer a character from your harem |
| `/top` | Global leaderboard · tabs: Richest / Top XP / Killers |

### ⚔️ RPG
| Command | Description |
|---|---|
| `/rob` | Steal 10-25 % of target's coins · 40 % fail chance · 1h CD |
| `/kill` | Drain 15 % XP + 5 % coins · award kill stat · 2h CD |
| `/protect` | Buy 48-hour shield for 500 coins — blocks rob & kill |

### 🎮 Games
| Command | Description |
|---|---|
| `/rocket <bet>` | Interactive animated multiplier — cash out before crash |
| `/rocket <bet> <mult>` | Auto-cashout at given multiplier (e.g. `/rocket 1000 2.5`) |
| `/scrabble` | Group word-unscramble race · first correct answer wins coins |
| `/game` | Interactive info hub for all games and mechanics |

### ⚙️ Admin
| Command | Access | Description |
|---|---|---|
| `/setgroup spawn on\|off` | Top-5 richest / owner | Toggle auto-spawn in group |
| `/setgroup nsfw on\|off` | Top-5 richest / owner | Toggle NSFW filter |
| `/setgroup toxicity on\|off` | Top-5 richest / owner | Toggle toxicity filter |
| `/setgroup prefix <char>` | Top-5 richest / owner | Change command prefix |
| `/botstats` | Owner only | Total users, groups, richest player |

---

## ⚙️ Configuration Tuning (`config.py`)

| Variable | Default | Description |
|---|---|---|
| `SPAWN_AFTER` | `100` | Messages before character spawns |
| `SPAWN_TIMEOUT` | `300` | Seconds before unclaimed spawn expires |
| `EXPLORE_COST` | `500` | Coins per `/explore` |
| `DAILY_COINS` | `2000` | Base daily reward |
| `DAILY_STREAK_BONUS` | `100` | Extra coins per streak day |
| `ROB_FAIL_CHANCE` | `0.40` | 40 % rob failure probability |
| `ROB_STEAL_MIN/MAX` | `0.10 / 0.25` | Steal range (10-25 %) |
| `ROB_PENALTY` | `0.10` | Penalty fraction on failure |
| `KILL_XP_STEAL` | `0.15` | XP drained on kill |
| `PROTECT_COST` | `500` | Shield cost in coins |
| `PROTECT_DURATION` | `172800` | Shield duration (2 days) |
| `ROCKET_MIN/MAX_BET` | `100 / 50000` | Rocket bet limits |
| `SCRABBLE_TIMEOUT` | `60` | Word game time limit |

### Rarity weights (must sum to 100)
```python
RARITY_WEIGHTS = {
    "Common":    50,   # ⬜
    "Rare":      30,   # 🟦
    "Epic":      15,   # 🟪
    "Legendary":  4,   # 🟨
    "Velora":     1,   # 🌈
}
```

---

## 🔧 Extending the Character Pool

Add entries to `data/characters.json`:

```json
{
  "char_id": "C061",
  "name": "Your Character",
  "anime": "Anime Name",
  "rarity": "Epic",
  "price": 5000,
  "image_url": "https://your-cdn.com/char.jpg",
  "abilities": ["Ability One", "Ability Two", "Ability Three"]
}
```

The bot loads and caches the file on first spawn. Restart to pick up new entries,
or clear the `_CHARACTER_CACHE` global in `utils/helpers.py`.

---

## 🏗️ Architecture Notes

```
Pyrogram (async)
    │
    ├── modules/       ← @Client.on_message handlers (auto-loaded via plugins=)
    │
    ├── Redis          ← Hot state: msg counters, active spawns, cooldowns, game state
    │                     All volatile — safe to flush; counters restart on restart
    │
    └── MongoDB        ← Cold state: users, groups, marriages, transaction log
                          motor (async) — no blocking ops anywhere
```

**Multi-tenant safe:** every Redis key and MongoDB query is scoped by `chat_id` or `user_id`.
The bot can run in thousands of groups simultaneously with zero cross-contamination.

---

## 📜 License

MIT — free to use, modify, and deploy.

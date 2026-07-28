"""
🤖 AI FEATURES MODULE
────────────────────────────────────────────────────────────
• /askwaifu <question> — Interactive personalized local AI chatbot
• /fortune             — Professional daily destiny reading with consistency
"""

from __future__ import annotations

import random
import logging
from datetime import datetime, timezone
from pyrogram import Client, filters
from pyrogram.types import Message

from database.mongo import MongoDB
from utils.helpers import get_or_register
from utils.decorators import alive_only

logger = logging.getLogger("Module.AI")

# Local AI Chatbot rules & response templates
WAIFU_RESPONSES = {
    "love": [
        "Kyaaa! Asking me about love? {name} thinks you're really sweet, but don't make me blush too much! 💓",
        "Hmph! It's not like {name} likes you or anything... Baka! But... maybe a little bit. 🤫",
        "My heart beats faster when you ask that. {name} is happy to be by your side! 💕",
    ],
    "money": [
        "Coins? You should go rob someone or play Rocket! {name} loves a rich partner! 💰",
        "Don't worry about being broke, {name} believes you'll hit the jackpot soon! 🍀",
        "Ehhh? Are you asking {name} for a loan? Go run `/daily` first! 💸",
    ],
    "rob": [
        "Robbing is risky! But if you must, {name} says: aim for the richest players in `/top`! 🕵️‍♂️",
        "Don't get caught! The police penalty is brutal. {name} doesn't want to visit you in jail! 🚔",
        "Sneaky sneaky! May the stealth be with you, partner! 🗡️",
    ],
    "kill": [
        "Hehe, feel like unleashing some chaos? {name} wants to see your name on the Top Killers board! ☠️",
        "Make sure they don't have a shield active! Check their profile first! 🛡️",
        "Ooh, savage! Strike fast and strike hard! ⚔️",
    ],
    "help": [
        "{name} is here to help! Ask me about love, coins, gaming or combat, and I'll guide you! 🌟",
        "Need some tips? Talk to me anytime! {name} always has your back! ✨",
    ],
    "default": [
        "Hmm, that's an interesting question! {name} thinks you should follow your heart! 🌸",
        "Eeeh? {name} was distracted looking at your beautiful stats card! Can you repeat that? 🤭",
        "As your waifu, {name} advises you to play some Rocket, get rich, and buy me pretty gifts! 💎",
        "That's a secret! But {name} might tell you if you invite me to more chats! 🤫",
        "Ara ara, you ask the most intriguing things! {name} is happy to chat with you! ✨",
    ]
}


@Client.on_message(filters.command("askwaifu"))
@alive_only
async def askwaifu_cmd(client: Client, message: Message) -> None:
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply(
            "🌸 **Usage:** `/askwaifu <your question>`\n"
            "Example: `/askwaifu do you love me?`"
        )
        return

    question = parts[1].lower()
    user = await get_or_register(message.from_user)

    # Determine which waifu is speaking
    waifu_name = "Kokoa-chan"
    waifu_anime = "Zexis AI Helper"

    # Check married waifu first
    m_waifu_id = user.get("married_waifu")
    chars = user.get("characters", [])
    if m_waifu_id and chars:
        matched = [c for c in chars if c.get("char_id") == m_waifu_id]
        if matched:
            waifu_name = matched[0]["name"]
            waifu_anime = matched[0].get("anime", "Unknown Anime")
    elif chars:
        # Pick a random character from harem
        random_char = random.choice(chars)
        waifu_name = random_char["name"]
        waifu_anime = random_char.get("anime", "Unknown Anime")

    # Select response template based on keywords
    response_list = WAIFU_RESPONSES["default"]
    for keyword, templates in WAIFU_RESPONSES.items():
        if keyword in question:
            response_list = templates
            break

    response_text = random.choice(response_list).format(name=waifu_name)

    await message.reply(
        f"💬 **AI WAIFU CHATBOT**\n"
        f"👤 **Speaker:** {waifu_name} _({waifu_anime})_\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🙋‍♂️ **You asked:** \"_{parts[1]}_\"\n\n"
        f"🔮 **Response:** {response_text}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )


# Fortune Teller templates
FORTUNE_TEXTS = [
    "A grand opportunity is coming your way in the games. Don't be afraid to take a risk!",
    "A shadow is lingering around. Be extremely careful when executing `/rob` today!",
    "Your romance luck is off the charts! It is the perfect day to `/propose` or marry a waifu!",
    "The stars indicate a minor setback. Avoid high-stakes Rocket games for a few hours.",
    "A legendary aura surrounds you. Chat actively — a rare waifu is sensing your energy!",
    "Someone is plotting against you. Make sure to buy a protective shield with `/protect`!",
    "An unexpected windfall of coins is predicted in your near future. Stay positive!",
    "Your combat skills are heightened. Today's `/kill` strikes will be incredibly precise!"
]


@Client.on_message(filters.command("fortune"))
@alive_only
async def fortune_cmd(client: Client, message: Message) -> None:
    user = await get_or_register(message.from_user)
    uid = message.from_user.id

    # Create consistent daily seed using user_id and current date (UTC)
    now_utc = datetime.now(timezone.utc)
    date_str = now_utc.strftime("%Y-%m-%d")
    seed_str = f"{uid}:{date_str}"

    # Use local Random object for consistent results
    local_rand = random.Random(seed_str)

    luck_score = local_rand.randint(5, 100)

    # Generate 1 to 5 stars for each category
    w_num = local_rand.randint(1, 5)
    wealth_stars = "🌟" * w_num + "☆" * (5 - w_num)

    r_num = local_rand.randint(1, 5)
    romance_stars = "🌟" * r_num + "☆" * (5 - r_num)

    k_num = local_rand.randint(1, 5)
    rpg_stars = "🌟" * k_num + "☆" * (5 - k_num)

    reading = local_rand.choice(FORTUNE_TEXTS)

    # Pick a random cute recommendation of the day
    recommendations = [
        "Play Rocket manual and cash out at exactly `2.0x`!",
        "Check `/top` and send a small `/gift` to a friend for good karma.",
        "Use `/explore` to discover a new waifu instantly.",
        "Activate `/protect` to lock in your safety.",
        "Show off your wallet with `/bal` in the group chat!"
    ]
    rec = local_rand.choice(recommendations)

    await message.reply(
        f"🔮 **DAILY FORTUNE TELLER** 🔮\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 **Destiny of:** {message.from_user.first_name}\n"
        f"📅 **Date:** `{date_str}`\n\n"
        f"📈 **Overall Luck Score:** `{luck_score}%`\n"
        f"💰 **Wealth Luck:**  `{wealth_stars}`\n"
        f"💞 **Romance Luck:** `{romance_stars}`\n"
        f"⚔️ **RPG Luck:**     `{rpg_stars}`\n\n"
        f"🔮 **Daily Reading:**\n"
        f"_{reading}_\n\n"
        f"💡 **Recommendation:**\n"
        f"*{rec}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )

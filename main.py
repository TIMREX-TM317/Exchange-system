import discord
from discord.ext import commands
import asyncio
import json
import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)


def load_config() -> dict:
    path = os.path.join(BASE_DIR, "config.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
COGS = ["cogs.exchange", "cogs.vouch", "cogs.moderation"]


@bot.event
async def on_ready():
    cfg = load_config()
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")

    # Sync slash commands
    guild = discord.Object(id=int(cfg["guild-id"]))
    bot.tree.copy_global_to(guild=guild)
    synced = await bot.tree.sync(guild=guild)
    print(f"   Synced {len(synced)} slash commands")

    await bot.change_presence(
        activity=discord.CustomActivity(name=cfg.get("bot-status", ".gg/Exchora"))
    )


async def main():
    cfg = load_config()
    token = cfg.get("token", "")
    if not token or token == "YOUR_BOT_TOKEN_HERE":
        print("❌ ERROR: Set your bot token in config.json!")
        return

    async with bot:
        # Load cogs first
        for cog in COGS:
            try:
                await bot.load_extension(cog)
                print(f"   ✅ Loaded: {cog}")
            except Exception as e:
                print(f"   ❌ Failed {cog}: {e}")

        # Register persistent views AFTER cogs are loaded
        # Import here so cogs are already in memory
        from cogs.exchange import ExchangePanelView, TicketControlView
        bot.add_view(ExchangePanelView())
        bot.add_view(TicketControlView())
        print("   ✅ Persistent views registered")

        await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())

import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
import time

from utils.database import add_vouch, get_vouches
from utils.config_loader import get_config


class VouchCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="vouch", description="Vouch for a user after a successful exchange")
    @app_commands.describe(user="User to vouch for", rating="Star rating 1–5", comment="Optional comment")
    @app_commands.choices(rating=[
        app_commands.Choice(name="⭐ 1 Star",          value=1),
        app_commands.Choice(name="⭐⭐ 2 Stars",        value=2),
        app_commands.Choice(name="⭐⭐⭐ 3 Stars",      value=3),
        app_commands.Choice(name="⭐⭐⭐⭐ 4 Stars",    value=4),
        app_commands.Choice(name="⭐⭐⭐⭐⭐ 5 Stars",  value=5),
    ])
    async def vouch(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        rating: int,
        comment: Optional[str] = "No comment provided.",
    ):
        if user.id == interaction.user.id:
            await interaction.response.send_message("❌ You cannot vouch for yourself!", ephemeral=True)
            return
        if user.bot:
            await interaction.response.send_message("❌ You cannot vouch for a bot!", ephemeral=True)
            return

        stars = "⭐" * rating + "☆" * (5 - rating)
        add_vouch({
            "from":      str(interaction.user.id),
            "target":    str(user.id),
            "rating":    rating,
            "comment":   comment,
            "timestamp": time.time(),
        })

        all_v = get_vouches(user.id)
        avg   = sum(v["rating"] for v in all_v) / len(all_v)

        emb = discord.Embed(title="✅ New Vouch", color=discord.Color.green(), timestamp=discord.utils.utcnow())
        emb.set_thumbnail(url=user.display_avatar.url)
        emb.add_field(name="👤 User",     value=user.mention,                               inline=True)
        emb.add_field(name="⭐ Rating",   value=stars,                                      inline=True)
        emb.add_field(name="📊 Stats",    value=f"{len(all_v)} vouches | Avg: {avg:.1f}/5", inline=True)
        emb.add_field(name="💬 Comment",  value=comment,                                    inline=False)
        emb.add_field(name="👋 From",     value=interaction.user.mention,                   inline=True)
        emb.set_footer(text="Exchora Exchange • .gg/Exchora")

        cfg = get_config()
        ch_id = cfg.get("vouch-channel-id")
        if ch_id:
            ch = self.bot.get_channel(int(ch_id))
            if ch:
                await ch.send(embed=emb)

        await interaction.response.send_message(f"✅ Successfully vouched for {user.mention}!", ephemeral=True)

    @app_commands.command(name="vouches", description="Show vouches for a user")
    @app_commands.describe(user="User to check (leave empty for yourself)")
    async def vouches(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        target  = user or interaction.user
        all_v   = get_vouches(target.id)

        if not all_v:
            await interaction.response.send_message(f"❌ {target.mention} has no vouches yet.", ephemeral=True)
            return

        avg       = sum(v["rating"] for v in all_v) / len(all_v)
        avg_stars = "⭐" * round(avg) + "☆" * (5 - round(avg))
        recent    = "\n".join(
            f"{'⭐' * v['rating']} — <@{v['from']}>: *{v['comment'][:80]}*"
            for v in all_v[-5:][::-1]
        )

        emb = discord.Embed(
            title=f"📋 Vouches for {target.display_name}",
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow(),
        )
        emb.set_thumbnail(url=target.display_avatar.url)
        emb.add_field(name="📊 Total",   value=str(len(all_v)),            inline=True)
        emb.add_field(name="⭐ Average", value=f"{avg:.1f}/5 {avg_stars}", inline=True)
        emb.add_field(name="\u200b",     value="\u200b",                   inline=True)
        emb.add_field(name="🕐 Recent",  value=recent or "None",           inline=False)
        emb.set_footer(text="Exchora Exchange • .gg/Exchora")
        await interaction.response.send_message(embed=emb)


async def setup(bot: commands.Bot):
    await bot.add_cog(VouchCog(bot))

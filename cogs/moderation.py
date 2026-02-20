import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional

from utils.database import add_blacklist, remove_blacklist, is_blacklisted, get_total
from utils.config_loader import get_config


def _has_perm(interaction: discord.Interaction, key: str) -> bool:
    cfg     = get_config()
    allowed = cfg.get(key, [])
    if interaction.user.id in allowed:
        return True
    return any(r.id in allowed for r in interaction.user.roles)


class ModerationCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /blacklist ───────────────────────────────────────────────

    blacklist_group = app_commands.Group(name="blacklist", description="Manage the blacklist")

    @blacklist_group.command(name="add", description="Blacklist a user")
    @app_commands.describe(user="User to blacklist", reason="Reason")
    async def bl_add(self, interaction: discord.Interaction, user: discord.Member, reason: Optional[str] = "No reason provided"):
        if not _has_perm(interaction, "blacklist"):
            await interaction.response.send_message("❌ No permission.", ephemeral=True)
            return

        add_blacklist(user.id)
        cfg    = get_config()
        bl_rid = cfg.get("blacklisted")
        if bl_rid:
            role = interaction.guild.get_role(int(bl_rid))
            if role:
                await user.add_roles(role)

        emb = discord.Embed(title="🚫 User Blacklisted", color=discord.Color.red(), timestamp=discord.utils.utcnow())
        emb.add_field(name="User",   value=user.mention,               inline=True)
        emb.add_field(name="Reason", value=reason,                     inline=True)
        emb.add_field(name="By",     value=interaction.user.mention,   inline=True)
        await interaction.response.send_message(embed=emb)

    @blacklist_group.command(name="remove", description="Remove a user from the blacklist")
    @app_commands.describe(user="User to unblacklist")
    async def bl_remove(self, interaction: discord.Interaction, user: discord.Member):
        if not _has_perm(interaction, "blacklist"):
            await interaction.response.send_message("❌ No permission.", ephemeral=True)
            return

        remove_blacklist(user.id)
        cfg    = get_config()
        bl_rid = cfg.get("blacklisted")
        if bl_rid:
            role = interaction.guild.get_role(int(bl_rid))
            if role and role in user.roles:
                await user.remove_roles(role)

        await interaction.response.send_message(f"✅ {user.mention} removed from blacklist.")

    @blacklist_group.command(name="check", description="Check if a user is blacklisted")
    @app_commands.describe(user="User to check")
    async def bl_check(self, interaction: discord.Interaction, user: discord.Member):
        bl = is_blacklisted(user.id)
        await interaction.response.send_message(
            f"{user.mention} is {'🚫 **blacklisted**' if bl else '✅ **not blacklisted**'}.",
            ephemeral=True,
        )

    # ── /role-give ───────────────────────────────────────────────

    @app_commands.command(name="role-give", description="Toggle a role on a user")
    @app_commands.describe(user="Target user", role="Role to toggle")
    async def role_give(self, interaction: discord.Interaction, user: discord.Member, role: discord.Role):
        if not _has_perm(interaction, "role-give"):
            await interaction.response.send_message("❌ No permission.", ephemeral=True)
            return

        if role in user.roles:
            await user.remove_roles(role)
            await interaction.response.send_message(f"✅ Removed **{role.name}** from {user.mention}.")
        else:
            await user.add_roles(role)
            await interaction.response.send_message(f"✅ Gave **{role.name}** to {user.mention}.")

    # ── /total ───────────────────────────────────────────────────

    @app_commands.command(name="total", description="Show total amount exchanged on this server")
    async def total_cmd(self, interaction: discord.Interaction):
        total = get_total()
        emb   = discord.Embed(
            title="💱 Total Exchanged",
            description=f"**€{total:,.2f}** has been exchanged on this server in total!",
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow(),
        )
        emb.set_footer(text="Exchora Exchange • .gg/Exchora")
        await interaction.response.send_message(embed=emb)


async def setup(bot: commands.Bot):
    await bot.add_cog(ModerationCog(bot))

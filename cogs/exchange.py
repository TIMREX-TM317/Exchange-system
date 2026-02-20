import discord
from discord.ext import commands
from discord import app_commands
import time
from typing import Optional

from utils.config_loader import get_config
from utils.database import (
    set_ticket, get_ticket, delete_ticket,
    add_to_total, get_total, is_blacklisted,
)
from utils.fees import calculate_fee
from utils.transcript import create_transcript

# ── Constants ──────────────────────────────────────────────────────────────────

PAYMENT_METHODS = [
    "PayPal", "Crypto", "CashApp", "Revolut", "Venmo",
    "Zelle", "Skrill", "Paysafe", "Amazon", "Apple Pay",
    "Wise", "Bank Transfer", "Wunschgutschein",
]
PAYPAL_TYPES = ["PayPal Balance", "Card"]
CRYPTO_COINS = ["LTC", "BTC", "Solana", "ETH", "Other"]
METHOD_EMOJI = {
    "PayPal": "💙", "Crypto": "🪙", "CashApp": "💚",
    "Revolut": "🔵", "Venmo": "💜", "Zelle": "💛",
    "Skrill": "🔴", "Paysafe": "🟠", "Amazon": "🟡",
    "Apple Pay": "🍎", "Wise": "🟢",
    "Bank Transfer": "🏦", "Wunschgutschein": "🎁",
}

# Per-user wizard state
PENDING: dict[int, dict] = {}


# ── Shared helpers ─────────────────────────────────────────────────────────────

async def update_total_voice(bot: commands.Bot):
    cfg = get_config()
    ch_id = cfg.get("total-exchanged-voice-id")
    if not ch_id:
        return
    channel = bot.get_channel(int(ch_id))
    if channel:
        try:
            await channel.edit(name=f"💱 Total: €{get_total():,.2f}")
        except Exception:
            pass


async def do_send_transcript(bot: commands.Bot, channel: discord.TextChannel, ticket_data: dict):
    cfg = get_config()
    try:
        filepath = await create_transcript(channel, ticket_data)
        status   = ticket_data.get("status", "unknown").capitalize()
        color    = discord.Color.green() if status.lower() == "completed" else discord.Color.red()

        log_emb = discord.Embed(
            title=f"📋 Transcript — #{channel.name}",
            description=f"**Status:** {status}",
            color=color,
            timestamp=discord.utils.utcnow(),
        )
        log_emb.set_footer(text="Exchora Exchange • .gg/Exchora")

        log_ch_id = cfg.get("exchange-logs-channel-id")
        if log_ch_id:
            log_ch = bot.get_channel(int(log_ch_id))
            if log_ch:
                await log_ch.send(embed=log_emb, file=discord.File(str(filepath), filename=filepath.name))

        uid = ticket_data.get("user_id")
        if uid:
            try:
                user = bot.get_user(int(uid)) or await bot.fetch_user(int(uid))
                dm_emb = discord.Embed(
                    title="📋 Your Exchange Ticket Transcript",
                    description=(
                        f"Your ticket **#{channel.name}** has been closed.\n"
                        f"**Status:** {status}\n\nThe full transcript is attached."
                    ),
                    color=color,
                    timestamp=discord.utils.utcnow(),
                )
                dm_emb.set_footer(text="Exchora Exchange • .gg/Exchora")
                await user.send(embed=dm_emb, file=discord.File(str(filepath), filename=filepath.name))
            except (discord.Forbidden, discord.NotFound):
                pass
    except Exception as e:
        print(f"[Transcript Error] {e}")


def _close_log_embed(ticket, closed_by, amt, reason):
    color  = discord.Color.green() if amt else discord.Color.red()
    status = "✅ Completed" if amt else "❌ Cancelled"
    send_s = ticket["send_method"] + (f" ({ticket['send_detail']})"    if ticket.get("send_detail")    else "")
    recv_s = ticket["receive_method"] + (f" ({ticket['receive_detail']})" if ticket.get("receive_detail") else "")

    emb = discord.Embed(title="🔒 Exchange Ticket Closed", color=color, timestamp=discord.utils.utcnow())
    emb.add_field(name="👤 User",     value=f"<@{ticket['user_id']}>", inline=True)
    emb.add_field(name="📤 Sent",     value=send_s,                   inline=True)
    emb.add_field(name="📥 Received", value=recv_s,                   inline=True)
    if amt:
        fd = calculate_fee(ticket["send_method"], ticket.get("send_detail"),
                           ticket["receive_method"], ticket.get("receive_detail"), amt)
        emb.add_field(name="💰 Amount Sent",             value=f"€{amt:.2f}",          inline=True)
        emb.add_field(name=f"🏷️ Fee ({fd['percent']}%)", value=f"€{fd['fee']:.2f}",    inline=True)
        emb.add_field(name="✅ Amount Received",          value=f"€{fd['receive']:.2f}", inline=True)
        if fd.get("note"):
            emb.add_field(name="ℹ️ Note", value=fd["note"], inline=False)
    else:
        emb.add_field(name="💰 Amount", value="Not completed", inline=True)
    emb.add_field(name="📋 Status",    value=status,            inline=True)
    emb.add_field(name="📝 Reason",    value=reason,            inline=True)
    emb.add_field(name="👮 Closed By", value=closed_by.mention, inline=True)
    emb.set_footer(text="Exchora Exchange • .gg/Exchora")
    return emb


async def _do_close(bot, channel, guild, ticket, closed_by, amt, reason):
    cfg = get_config()
    if amt:
        fd = calculate_fee(ticket["send_method"], ticket.get("send_detail"),
                           ticket["receive_method"], ticket.get("receive_detail"), amt)
        ticket.update(amount=amt, fee=fd["fee"], receive_amount=fd["receive"], fee_percent=fd["percent"])

    ticket["status"] = "completed" if amt else "cancelled"
    set_ticket(channel.id, ticket)

    await do_send_transcript(bot, channel, ticket)

    log_ch_id = cfg.get("exchange-logs-channel-id")
    if log_ch_id:
        log_ch = bot.get_channel(int(log_ch_id))
        if log_ch:
            await log_ch.send(embed=_close_log_embed(ticket, closed_by, amt, reason))

    if amt:
        add_to_total(amt)
        await update_total_voice(bot)

    cat_id = cfg.get("completed-exchanges-category-id") if amt else cfg.get("cancelled-exchanges-category-id")
    if cat_id:
        cat = guild.get_channel(int(cat_id))
        if cat:
            try:
                await channel.edit(category=cat)
            except Exception:
                pass

    uid = ticket.get("user_id")
    if uid:
        member = guild.get_member(int(uid))
        if member:
            try:
                await channel.set_permissions(member, view_channel=False)
            except Exception:
                pass

    delete_ticket(channel.id)
    s = f"✅ Completed (€{amt:.2f})" if amt else "❌ Cancelled"
    await channel.send(f"🔒 **Ticket closed.** Status: {s}")


# ── Wizard helpers ─────────────────────────────────────────────────────────────

def _send_select_view() -> tuple[discord.Embed, discord.ui.View]:
    """Step 1 — what are you sending?"""
    emb = discord.Embed(
        title="💱 Open Exchange — Step 1 of 3",
        description="**What payment method are you sending?**\nSelect from the dropdown below.",
        color=discord.Color.blurple(),
    )
    view = discord.ui.View(timeout=300)
    view.add_item(SendMethodSelect())
    return emb, view


async def _show_receive_select(interaction: discord.Interaction, uid: int):
    state  = PENDING.get(uid, {})
    s_meth = state.get("send_method", "?")
    s_det  = state.get("send_detail")
    send_s = s_meth + (f" ({s_det})" if s_det else "")

    emb = discord.Embed(
        title="💱 Step 2 — What do you want to receive?",
        description=f"✅ **Sending:** {send_s}\n\nSelect your receive method below.",
        color=discord.Color.blurple(),
    )
    view = discord.ui.View(timeout=300)
    view.add_item(ReceiveMethodSelect(exclude=s_meth))
    await interaction.response.edit_message(embed=emb, view=view)


async def _show_amount_modal(interaction: discord.Interaction, uid: int):
    await interaction.response.send_modal(AmountModal(uid))


# ── Selects ────────────────────────────────────────────────────────────────────

class SendMethodSelect(discord.ui.Select):
    def __init__(self):
        opts = [discord.SelectOption(label=m, value=m, emoji=METHOD_EMOJI.get(m, "💳"))
                for m in PAYMENT_METHODS]
        super().__init__(placeholder="What are you sending?", options=opts)

    async def callback(self, interaction: discord.Interaction):
        method = self.values[0]
        uid    = interaction.user.id
        PENDING[uid] = {"send_method": method}

        if method == "PayPal":
            emb = discord.Embed(title="💱 Step 1b — PayPal type",
                description="✅ **Sending:** PayPal\n\nAre you paying via **Card** or **PayPal Balance**?",
                color=discord.Color.blurple())
            v = discord.ui.View(timeout=300)
            v.add_item(PayPalTypeSelect(role="send"))
            await interaction.response.edit_message(embed=emb, view=v)

        elif method == "Crypto":
            emb = discord.Embed(title="💱 Step 1b — Crypto coin",
                description="✅ **Sending:** Crypto\n\nWhich cryptocurrency are you sending?",
                color=discord.Color.blurple())
            v = discord.ui.View(timeout=300)
            v.add_item(CryptoCoinSelect(role="send"))
            await interaction.response.edit_message(embed=emb, view=v)

        else:
            await _show_receive_select(interaction, uid)


class PayPalTypeSelect(discord.ui.Select):
    def __init__(self, role: str):
        self.role = role
        super().__init__(placeholder="Card or PayPal Balance?",
                         options=[discord.SelectOption(label=t, value=t) for t in PAYPAL_TYPES])

    async def callback(self, interaction: discord.Interaction):
        uid   = interaction.user.id
        state = PENDING.setdefault(uid, {})
        if self.role == "send":
            state["send_detail"] = self.values[0]
            await _show_receive_select(interaction, uid)
        else:
            state["receive_detail"] = self.values[0]
            await _show_amount_modal(interaction, uid)


class CryptoCoinSelect(discord.ui.Select):
    def __init__(self, role: str):
        self.role = role
        super().__init__(placeholder="Which cryptocurrency?",
                         options=[discord.SelectOption(label=c, value=c) for c in CRYPTO_COINS])

    async def callback(self, interaction: discord.Interaction):
        uid   = interaction.user.id
        state = PENDING.setdefault(uid, {})
        if self.role == "send":
            state["send_detail"] = self.values[0]
            await _show_receive_select(interaction, uid)
        else:
            state["receive_detail"] = self.values[0]
            await _show_amount_modal(interaction, uid)


class ReceiveMethodSelect(discord.ui.Select):
    def __init__(self, exclude: str):
        opts = [discord.SelectOption(label=m, value=m, emoji=METHOD_EMOJI.get(m, "💳"))
                for m in PAYMENT_METHODS if m != exclude]
        super().__init__(placeholder="What do you want to receive?", options=opts)

    async def callback(self, interaction: discord.Interaction):
        method = self.values[0]
        uid    = interaction.user.id
        state  = PENDING.setdefault(uid, {})
        state["receive_method"] = method
        send_s = state.get("send_method","?") + (f" ({state['send_detail']})" if state.get("send_detail") else "")

        if method == "PayPal":
            emb = discord.Embed(title="💱 Step 2b — PayPal type",
                description=f"✅ **Sending:** {send_s}\n✅ **Receiving:** PayPal\n\nVia **Card** or **PayPal Balance**?",
                color=discord.Color.blurple())
            v = discord.ui.View(timeout=300)
            v.add_item(PayPalTypeSelect(role="receive"))
            await interaction.response.edit_message(embed=emb, view=v)

        elif method == "Crypto":
            emb = discord.Embed(title="💱 Step 2b — Crypto coin",
                description=f"✅ **Sending:** {send_s}\n✅ **Receiving:** Crypto\n\nWhich coin do you want to receive?",
                color=discord.Color.blurple())
            v = discord.ui.View(timeout=300)
            v.add_item(CryptoCoinSelect(role="receive"))
            await interaction.response.edit_message(embed=emb, view=v)

        else:
            await _show_amount_modal(interaction, uid)


# ── Modals ─────────────────────────────────────────────────────────────────────

class AmountModal(discord.ui.Modal, title="Exchange Amount"):
    amount = discord.ui.TextInput(label="How much are you sending? (in €)",
                                  placeholder="e.g. 50.00", required=True, max_length=20)

    def __init__(self, uid: int):
        super().__init__()
        self.uid = uid

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.amount.value.replace("€","").replace("$","").replace(",",".").strip()
        try:
            amt = float(raw)
            assert amt > 0
        except Exception:
            await interaction.response.send_message("❌ Invalid amount.", ephemeral=True)
            return

        state = PENDING.get(self.uid, {})
        state["amount"] = amt
        fd = calculate_fee(state["send_method"], state.get("send_detail"),
                           state["receive_method"], state.get("receive_detail"), amt)
        state["fee_data"] = fd
        PENDING[self.uid]  = state

        send_s = state["send_method"] + (f" ({state['send_detail']})"    if state.get("send_detail")    else "")
        recv_s = state["receive_method"] + (f" ({state.get('receive_detail')})" if state.get("receive_detail") else "")

        emb = discord.Embed(title="💱 Confirm Your Exchange",
                            description="Please review and confirm:", color=discord.Color.blurple())
        emb.add_field(name="📤 You Send",    value=f"**{send_s}**",            inline=True)
        emb.add_field(name="📥 You Receive", value=f"**{recv_s}**",            inline=True)
        emb.add_field(name="\u200b",         value="\u200b",                   inline=True)
        emb.add_field(name="💰 Amount",      value=f"**€{amt:.2f}**",          inline=True)
        emb.add_field(name=f"🏷️ Fee ({fd['percent']}%)", value=f"**€{fd['fee']:.2f}**", inline=True)
        emb.add_field(name="✅ They Receive", value=f"**€{fd['receive']:.2f}**", inline=True)
        if fd.get("note"):
            emb.add_field(name="ℹ️ Note", value=fd["note"], inline=False)
        emb.set_footer(text="Fees calculated on amount you send · Exchora Exchange")
        await interaction.response.send_message(embed=emb, view=ConfirmTicketView(self.uid), ephemeral=True)


class CloseTicketModal(discord.ui.Modal, title="Close Exchange Ticket"):
    amount = discord.ui.TextInput(label="Amount sent (blank = cancelled)",
                                  placeholder="e.g. 50.00", required=False, max_length=20)
    reason = discord.ui.TextInput(label="Reason", placeholder="Completed / User left / etc.",
                                  required=False, max_length=200, default="No reason provided")

    async def on_submit(self, interaction: discord.Interaction):
        ticket = get_ticket(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message("❌ Not a ticket channel.", ephemeral=True)
            return

        raw = (self.amount.value or "").replace("€","").replace("$","").replace(",",".").strip()
        amt = None
        if raw:
            try:
                amt = float(raw)
                if amt <= 0: amt = None
            except ValueError:
                pass

        await interaction.response.send_message("🔒 Closing ticket and generating transcript…")
        await _do_close(interaction.client, interaction.channel, interaction.guild,
                        ticket, interaction.user, amt, self.reason.value or "No reason provided")


# ── Views ──────────────────────────────────────────────────────────────────────

class ExchangePanelView(discord.ui.View):
    """Persistent — timeout=None, stable custom_id."""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Open Exchange Ticket", style=discord.ButtonStyle.primary,
                       emoji="💱", custom_id="btn_open_exchange")
    async def open_exchange(self, interaction: discord.Interaction, button: discord.ui.Button):
        if is_blacklisted(interaction.user.id):
            await interaction.response.send_message(
                "🚫 You are blacklisted and cannot open exchange tickets.", ephemeral=True)
            return

        # Immediately show Step 1 — no intermediate message
        PENDING[interaction.user.id] = {}
        emb, view = _send_select_view()
        await interaction.response.send_message(embed=emb, view=view, ephemeral=True)


class ConfirmTicketView(discord.ui.View):
    def __init__(self, uid: int):
        super().__init__(timeout=120)
        self.uid = uid

    @discord.ui.button(label="Confirm & Open Ticket", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = PENDING.pop(self.uid, None)
        if not state:
            await interaction.response.send_message("❌ Session expired. Please start over.", ephemeral=True)
            return

        await interaction.response.edit_message(content="⏳ Creating your ticket…", embed=None, view=None)

        guild  = interaction.guild
        cfg    = get_config()
        s_meth = state["send_method"]
        r_meth = state["receive_method"]
        s_det  = state.get("send_detail")
        r_det  = state.get("receive_detail")
        amount = state.get("amount")
        fd     = state.get("fee_data", {})

        cat_id = cfg.get(f"{s_meth}-Category") or cfg.get("claimed-exchanges-category-id")

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user:   discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        }
        for rid in cfg.get("ids-to-have-full-access-in-tickets", []):
            r = guild.get_role(int(rid))
            if r:
                overwrites[r] = discord.PermissionOverwrite(view_channel=True, send_messages=True,
                                                             read_message_history=True, manage_messages=True)
        for rid in cfg.get("exchangers", []):
            r = guild.get_role(int(rid))
            if r:
                overwrites[r] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

        safe_name = interaction.user.name[:15].lower().replace(" ", "-")
        ch_name   = f"exchange-{safe_name}-{str(interaction.user.id)[-4:]}"
        category  = guild.get_channel(int(cat_id)) if cat_id else None

        try:
            channel = await guild.create_text_channel(name=ch_name, overwrites=overwrites, category=category)
        except Exception as e:
            await interaction.edit_original_response(content=f"❌ Failed to create channel: {e}")
            return

        send_s = s_meth + (f" ({s_det})" if s_det else "")
        recv_s = r_meth + (f" ({r_det})" if r_det else "")

        ticket_data = {
            "user_id": interaction.user.id, "channel_id": channel.id,
            "send_method": s_meth, "send_detail": s_det,
            "receive_method": r_meth, "receive_detail": r_det,
            "amount": amount, "fee": fd.get("fee"),
            "receive_amount": fd.get("receive"), "fee_percent": fd.get("percent"),
            "claimed": False, "claimed_by": None,
            "status": "open", "created_at": time.time(),
        }
        set_ticket(channel.id, ticket_data)

        emb = discord.Embed(title="💱 Exchange Ticket",
                            description=f"Welcome {interaction.user.mention}! An exchanger will assist you shortly.",
                            color=discord.Color.blurple(), timestamp=discord.utils.utcnow())
        emb.add_field(name="📤 Sending",   value=f"**{send_s}**", inline=True)
        emb.add_field(name="📥 Receiving", value=f"**{recv_s}**", inline=True)
        emb.add_field(name="\u200b",       value="\u200b",        inline=True)
        if amount:
            emb.add_field(name="💰 Amount Sent",              value=f"**€{amount:.2f}**",           inline=True)
            emb.add_field(name=f"🏷️ Fee ({fd.get('percent',0)}%)", value=f"**€{fd.get('fee',0):.2f}**", inline=True)
            emb.add_field(name="✅ They Receive",              value=f"**€{fd.get('receive',0):.2f}**", inline=True)
        if fd.get("note"):
            emb.add_field(name="ℹ️ Note", value=fd["note"], inline=False)
        emb.set_footer(text=f"Opened by {interaction.user} · Exchora Exchange")

        await channel.send(content=interaction.user.mention, embed=emb, view=TicketControlView())

        ping_id = cfg.get(f"{s_meth}-Ping")
        if ping_id and int(ping_id) != 0:
            pr = guild.get_role(int(ping_id))
            if pr:
                try:
                    pm = await channel.send(pr.mention)
                    await pm.delete(delay=5)
                except Exception:
                    pass

        await interaction.edit_original_response(content=f"✅ Ticket created: {channel.mention}")

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        PENDING.pop(interaction.user.id, None)
        await interaction.response.edit_message(content="❌ Cancelled.", embed=None, view=None)


class TicketControlView(discord.ui.View):
    """Persistent — timeout=None, stable custom_ids."""
    def __init__(self):
        super().__init__(timeout=None)

    def _is_staff(self, i):
        cfg = get_config()
        a = cfg.get("ids-to-have-full-access-in-tickets", [])
        return i.user.id in a or any(r.id in a for r in i.user.roles)

    def _is_exchanger(self, i):
        cfg = get_config()
        e = cfg.get("exchangers", [])
        return i.user.id in e or any(r.id in e for r in i.user.roles) or self._is_staff(i)

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.primary,
                       emoji="✋", custom_id="btn_ticket_claim")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        ticket = get_ticket(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message("❌ Not a ticket channel.", ephemeral=True)
            return
        if not self._is_exchanger(interaction):
            await interaction.response.send_message("❌ Only exchangers can claim tickets.", ephemeral=True)
            return
        if ticket.get("claimed"):
            await interaction.response.send_message(f"❌ Already claimed by <@{ticket['claimed_by']}>.", ephemeral=True)
            return

        ticket["claimed"]    = True
        ticket["claimed_by"] = interaction.user.id
        set_ticket(interaction.channel.id, ticket)
        try:
            await interaction.channel.edit(name=f"claimed-{interaction.channel.name}"[:100])
        except Exception:
            pass

        emb = discord.Embed(
            description=f"✋ **Ticket claimed by {interaction.user.mention}!**\nThey will assist you shortly.",
            color=discord.Color.green())
        await interaction.response.send_message(embed=emb)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger,
                       emoji="🔒", custom_id="btn_ticket_close")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        ticket = get_ticket(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message("❌ Not a ticket channel.", ephemeral=True)
            return
        if interaction.user.id != ticket.get("user_id") and not self._is_staff(interaction):
            await interaction.response.send_message("❌ No permission to close this ticket.", ephemeral=True)
            return
        await interaction.response.send_modal(CloseTicketModal())

    @discord.ui.button(label="Request MM", style=discord.ButtonStyle.secondary,
                       emoji="🛡️", custom_id="btn_ticket_mm")
    async def request_mm(self, interaction: discord.Interaction, button: discord.ui.Button):
        cfg       = get_config()
        mm_rol_id = cfg.get("middleman-role-id")
        if mm_rol_id:
            mm_role = interaction.guild.get_role(int(mm_rol_id))
            if mm_role:
                try:
                    await interaction.channel.set_permissions(
                        mm_role, view_channel=True, send_messages=True, read_message_history=True)
                except Exception:
                    pass
        emb = discord.Embed(
            description=f"🛡️ **Middleman requested by {interaction.user.mention}!**\n<@&{mm_rol_id}> please assist here.",
            color=discord.Color.yellow())
        await interaction.response.send_message(embed=emb)


# ── Cog ────────────────────────────────────────────────────────────────────────

class ExchangeCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="setup-exchange", description="Post the exchange panel in this channel")
    @app_commands.default_permissions(administrator=True)
    async def setup_exchange(self, interaction: discord.Interaction):
        emb = discord.Embed(
            title="💱 Exchora Exchange System",
            description=(
                "**Welcome to the Exchange System!**\n\n"
                "Click the button below to open an exchange ticket.\n"
                "You will be guided step by step.\n\n"
                "**Supported Methods:**\n"
                "> PayPal • Crypto • CashApp • Revolut • Venmo\n"
                "> Zelle • Skrill • Paysafe • Amazon • Apple Pay\n"
                "> Wise • Bank Transfer • Wunschgutschein\n\n"
                "⚠️ Always follow our rules and stay safe!"
            ),
            color=discord.Color.blurple(),
        )
        if interaction.guild.icon:
            emb.set_thumbnail(url=interaction.guild.icon.url)
        emb.set_footer(text="Exchora Exchange • .gg/Exchora")
        await interaction.channel.send(embed=emb, view=ExchangePanelView())
        await interaction.response.send_message("✅ Exchange panel posted!", ephemeral=True)

    @app_commands.command(name="close", description="Close the current exchange ticket")
    @app_commands.describe(amount="Final amount in € (omit if cancelled)", reason="Reason for closing")
    async def close_cmd(self, interaction: discord.Interaction,
                        amount: Optional[str] = None, reason: Optional[str] = None):
        ticket = get_ticket(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message("❌ Not a ticket channel.", ephemeral=True)
            return
        cfg = get_config()
        can_close = (interaction.user.id == ticket.get("user_id") or
                     interaction.user.id in cfg.get("ids-to-have-full-access-in-tickets", []) or
                     any(r.id in cfg.get("ids-to-have-full-access-in-tickets", []) for r in interaction.user.roles))
        if not can_close:
            await interaction.response.send_message("❌ No permission.", ephemeral=True)
            return

        amt = None
        if amount:
            try:
                amt = float(amount.replace("€","").replace("$","").strip())
                if amt <= 0: amt = None
            except ValueError:
                pass

        await interaction.response.send_message("🔒 Closing ticket and generating transcript…")
        await _do_close(self.bot, interaction.channel, interaction.guild,
                        ticket, interaction.user, amt, reason or "No reason provided")

    @app_commands.command(name="fees", description="Show all exchange fees")
    async def fees_cmd(self, interaction: discord.Interaction):
        emb = discord.Embed(title="💰 All Exchange Fees",
                            description="Fees are always calculated on the amount **you send**.",
                            color=discord.Color.blurple())
        rows = [
            ("💙 PayPal Balance → Anything", "Under €10: **10%** | €10–99: **8%** | €100+: **7%**"),
            ("💙 PayPal Card → Anything",    "**15%**"),
            ("🪙 Crypto → Other Methods",    "**0%**"),
            ("🪙 Crypto → Crypto",           "**3%**"),
            ("💚 CashApp → Anything",        "**10%** (min. $3, USD only)"),
            ("🔵 Revolut → Anything",        "**10%**"),
            ("💜 Venmo → Anything",          "**10%**"),
            ("💛 Zelle → Anything",          "**10%**"),
            ("🟢 Wise → Anything",           "**10%**"),
            ("🏦 Bank Transfer → Anything",  "**10%**"),
            ("🔴 Skrill → Anything",         "**10%**"),
            ("🟠 Paysafe → Anything",        "Under €50: **25%** | €50–99: **20%** | €100+: **17%**"),
            ("🟡 Amazon → Anything",         "**35%**"),
            ("🍎 Apple Pay → Anything",      "**25%**"),
            ("🎁 Wunschgutschein → Anything","**45%**"),
        ]
        for name, val in rows:
            emb.add_field(name=name, value=val, inline=False)
        emb.set_footer(text="Exchora Exchange • .gg/Exchora")
        await interaction.response.send_message(embed=emb, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ExchangeCog(bot))

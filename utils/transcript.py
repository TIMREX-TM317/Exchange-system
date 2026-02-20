import discord
import re
from datetime import datetime
from pathlib import Path

TRANSCRIPT_DIR = Path(__file__).parent.parent / "transcripts"
TRANSCRIPT_DIR.mkdir(exist_ok=True)


async def create_transcript(channel: discord.TextChannel, ticket_data: dict) -> Path:
    messages = []
    async for msg in channel.history(limit=5000, oldest_first=True):
        messages.append(msg)

    filename = f"transcript-{channel.name}-{channel.id}.html"
    filepath = TRANSCRIPT_DIR / filename

    send_method  = ticket_data.get("send_method", "?")
    recv_method  = ticket_data.get("receive_method", "?")
    send_detail  = ticket_data.get("send_detail") or ""
    recv_detail  = ticket_data.get("receive_detail") or ""
    amount       = ticket_data.get("amount")
    fee          = ticket_data.get("fee")
    recv_amount  = ticket_data.get("receive_amount")
    percent      = ticket_data.get("fee_percent")
    status       = ticket_data.get("status", "unknown").capitalize()
    user_id      = ticket_data.get("user_id", "?")
    created_ts   = ticket_data.get("created_at", 0)
    created_at   = datetime.utcfromtimestamp(created_ts).strftime("%Y-%m-%d %H:%M UTC")
    closed_at    = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    send_str = send_method + (f" ({send_detail})" if send_detail else "")
    recv_str = recv_method + (f" ({recv_detail})"  if recv_detail  else "")

    status_color = (
        "#57f287" if status.lower() == "completed" else
        "#ed4245" if status.lower() == "cancelled"  else
        "#fee75c"
    )

    # ── Build message HTML ────────────────────────────────────────
    html_messages = ""
    for msg in messages:
        if not msg.content and not msg.embeds and not msg.attachments:
            continue

        avatar_url  = str(msg.author.display_avatar.url) if msg.author.display_avatar else ""
        ts          = msg.created_at.strftime("%H:%M")
        date_str    = msg.created_at.strftime("%Y-%m-%d")
        is_bot      = msg.author.bot
        name_color  = "#7289da" if is_bot else "#ffffff"
        bg_color    = "#36393f" if is_bot else "#2f3136"

        content_html = ""

        if msg.content:
            safe = (
                msg.content
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            )
            safe = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', safe)
            safe = re.sub(r'\*(.+?)\*',     r'<em>\1</em>',         safe)
            safe = re.sub(r'`(.+?)`',       r'<code>\1</code>',     safe)
            safe = safe.replace("\n", "<br>")
            safe = re.sub(r'&lt;@!?(\d+)&gt;',    r'<span class="mention">@user</span>', safe)
            safe = re.sub(r'&lt;@&amp;(\d+)&gt;', r'<span class="mention">@role</span>', safe)
            content_html += f'<div class="msg-content">{safe}</div>'

        for emb in msg.embeds:
            col = f"#{emb.colour.value:06x}" if emb.colour and emb.colour.value else "#5865f2"
            eh  = f'<div class="embed" style="border-left:4px solid {col};">'
            if emb.title:
                eh += f'<div class="emb-title">{emb.title}</div>'
            if emb.description:
                d2 = (
                    emb.description
                    .replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
                )
                d2 = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', d2)
                d2 = d2.replace("\n", "<br>")
                eh += f'<div class="emb-desc">{d2}</div>'
            for fld in emb.fields:
                fn = fld.name.replace("<","&lt;").replace(">","&gt;")
                fv = (
                    fld.value
                    .replace("<","&lt;").replace(">","&gt;")
                )
                fv = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', fv)
                fv = fv.replace("\n","<br>")
                eh += f'<div class="emb-field"><span class="fn">{fn}</span><span class="fv">{fv}</span></div>'
            eh += '</div>'
            content_html += eh

        for att in msg.attachments:
            if any(att.filename.lower().endswith(e) for e in ['.png','.jpg','.jpeg','.gif','.webp']):
                content_html += f'<img src="{att.url}" style="max-width:400px;max-height:300px;border-radius:4px;margin-top:4px;display:block;">'
            else:
                content_html += f'<div>📎 <a href="{att.url}" style="color:#00aff4;">{att.filename}</a></div>'

        bot_badge = "<span class='bot-tag'>BOT</span>" if is_bot else ""
        html_messages += f"""
<div class="msg-group" style="background:{bg_color}">
  <img class="avatar" src="{avatar_url}" onerror="this.src='https://cdn.discordapp.com/embed/avatars/0.png'" alt="">
  <div class="msg-body">
    <div class="msg-header">
      <span class="author" style="color:{name_color}">{msg.author.display_name}</span>
      {bot_badge}
      <span class="ts" title="{date_str}">{ts}</span>
    </div>
    {content_html}
  </div>
</div>"""

    # ── Conditional info rows ─────────────────────────────────────
    amount_row  = f'<div class="info-item"><span class="lbl">Amount Sent</span><span class="val">€{amount:.2f}</span></div>' if amount else ""
    fee_row     = f'<div class="info-item"><span class="lbl">Fee ({percent}%)</span><span class="val">€{fee:.2f}</span></div>' if fee is not None else ""
    recv_row    = f'<div class="info-item"><span class="lbl">Amount Received</span><span class="val">€{recv_amount:.2f}</span></div>' if recv_amount is not None else ""
    no_msg      = '<p style="color:#72767d;text-align:center;padding:30px">No messages found.</p>' if not html_messages else html_messages

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Transcript — {channel.name}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#1e1f22;color:#dcddde;font-family:'Segoe UI',Arial,sans-serif;font-size:14px}}
.header{{background:#2b2d31;padding:20px 28px;border-bottom:2px solid #111214}}
.header h1{{font-size:20px;font-weight:700;color:#fff}}
.header p{{font-size:12px;color:#949ba4;margin-top:3px}}
.info-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;background:#2b2d31;margin:14px 18px;padding:14px;border-radius:8px;border-left:4px solid #5865f2}}
.info-item{{display:flex;flex-direction:column;gap:2px}}
.lbl{{font-size:10px;font-weight:700;color:#949ba4;text-transform:uppercase;letter-spacing:.5px}}
.val{{font-size:13px;color:#fff;font-weight:500}}
.status-badge{{display:inline-block;padding:2px 10px;border-radius:10px;font-size:11px;font-weight:700;background:{status_color};color:#000}}
.messages{{padding:8px 18px}}
.msg-group{{display:flex;gap:12px;padding:7px 10px;border-radius:6px;margin-bottom:1px}}
.msg-group:hover{{background:#35373c!important}}
.avatar{{width:38px;height:38px;border-radius:50%;flex-shrink:0;object-fit:cover}}
.msg-body{{flex:1;min-width:0}}
.msg-header{{display:flex;align-items:center;gap:7px;margin-bottom:2px}}
.author{{font-weight:600;font-size:14px}}
.bot-tag{{background:#5865f2;color:#fff;font-size:9px;font-weight:700;padding:1px 5px;border-radius:3px;text-transform:uppercase}}
.ts{{font-size:11px;color:#72767d}}
.msg-content{{color:#dcddde;line-height:1.5;word-break:break-word}}
.mention{{background:rgba(88,101,242,.3);color:#c9cdfb;border-radius:3px;padding:0 2px}}
code{{background:#2b2d31;padding:1px 5px;border-radius:3px;font-family:monospace;font-size:13px;color:#f2f3f5}}
.embed{{background:#2b2d31;border-radius:4px;padding:10px 14px;margin-top:5px;max-width:520px}}
.emb-title{{font-weight:700;font-size:14px;color:#fff;margin-bottom:5px}}
.emb-desc{{color:#dcddde;line-height:1.5;font-size:13px;margin-bottom:4px}}
.emb-field{{margin-top:5px}}
.fn{{display:block;font-weight:700;font-size:12px;color:#fff;margin-bottom:1px}}
.fv{{display:block;font-size:12px;color:#dcddde;line-height:1.4}}
.footer{{text-align:center;padding:18px;color:#72767d;font-size:11px;border-top:1px solid #35373c;margin-top:16px}}
</style>
</head>
<body>
<div class="header">
  <h1>💱 Exchora — Ticket Transcript</h1>
  <p>#{channel.name} &nbsp;·&nbsp; Exported {closed_at}</p>
</div>
<div class="info-grid">
  <div class="info-item"><span class="lbl">Status</span><span class="val"><span class="status-badge">{status}</span></span></div>
  <div class="info-item"><span class="lbl">User ID</span><span class="val">{user_id}</span></div>
  <div class="info-item"><span class="lbl">Sending</span><span class="val">{send_str}</span></div>
  <div class="info-item"><span class="lbl">Receiving</span><span class="val">{recv_str}</span></div>
  {amount_row}{fee_row}{recv_row}
  <div class="info-item"><span class="lbl">Opened</span><span class="val">{created_at}</span></div>
  <div class="info-item"><span class="lbl">Closed</span><span class="val">{closed_at}</span></div>
</div>
<div class="messages">{no_msg}</div>
<div class="footer">Exchora Exchange System &nbsp;·&nbsp; .gg/Exchora &nbsp;·&nbsp; {closed_at}</div>
</body>
</html>"""

    filepath.write_text(html, encoding="utf-8")
    return filepath

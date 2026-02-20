# 💱 Exchora Exchange Bot

## Setup (3 steps)

### 1. Install Python 3.10+
https://python.org

### 2. Install dependencies
Open a terminal/CMD in this folder and run:
```
pip install -r requirements.txt
```

### 3. Add your token
Open `config.json` and replace `YOUR_BOT_TOKEN_HERE` with your bot token.
Get it from: https://discord.com/developers/applications → your app → Bot → Reset Token

### 4. Start the bot
```
python main.py
```

### 5. Post the exchange panel
Run `/setup-exchange` in the channel where you want the panel.

---

## Commands

| Command | Description |
|---|---|
| `/setup-exchange` | Post the exchange panel (Admin) |
| `/close [amount] [reason]` | Close a ticket |
| `/fees` | Show all exchange fees |
| `/vouch @user [stars] [comment]` | Leave a vouch |
| `/vouches [@user]` | View vouches |
| `/total` | Total exchanged |
| `/blacklist add/remove/check @user` | Manage blacklist |
| `/role-give @user @role` | Toggle a role |

---

## Fee Table

| Method | Fee |
|---|---|
| PayPal Balance | <€10: 10% · €10–99: 8% · €100+: 7% |
| PayPal Card | 15% |
| Crypto → Other | 0% |
| Crypto → Crypto | 3% |
| CashApp | 10% (min. $3) |
| Revolut / Venmo / Zelle / Wise / Bank Transfer / Skrill | 10% |
| Paysafe | <€50: 25% · €50–99: 20% · €100+: 17% |
| Amazon | 35% |
| Apple Pay | 25% |
| Wunschgutschein | 45% |

Fees are always calculated on what the **user sends**.

---

## Folder Structure
```
exchora/
├── main.py
├── config.json          ← put your token here
├── requirements.txt
├── cogs/
│   ├── __init__.py
│   ├── exchange.py
│   ├── vouch.py
│   └── moderation.py
├── utils/
│   ├── __init__.py
│   ├── config_loader.py
│   ├── database.py
│   ├── fees.py
│   └── transcript.py
├── data/                ← auto-created
└── transcripts/         ← auto-created
```

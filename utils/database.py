import json
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent.parent / "data" / "database.json"


def _load() -> dict:
    if not DB_PATH.exists():
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        data = {"tickets": {}, "vouches": [], "total_exchanged": 0.0, "blacklist": []}
        _save(data)
        return data
    with open(DB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict):
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ── Tickets ───────────────────────────────────────────────────

def set_ticket(channel_id: int, data: dict):
    db = _load()
    db["tickets"][str(channel_id)] = data
    _save(db)


def get_ticket(channel_id: int) -> Optional[dict]:
    db = _load()
    return db["tickets"].get(str(channel_id))


def delete_ticket(channel_id: int):
    db = _load()
    db["tickets"].pop(str(channel_id), None)
    _save(db)


# ── Vouches ───────────────────────────────────────────────────

def add_vouch(vouch: dict) -> int:
    db = _load()
    db["vouches"].append(vouch)
    _save(db)
    return len(db["vouches"])


def get_vouches(user_id: int) -> list:
    db = _load()
    return [v for v in db["vouches"] if v.get("target") == str(user_id)]


# ── Total ─────────────────────────────────────────────────────

def add_to_total(amount: float) -> float:
    db = _load()
    db["total_exchanged"] = round(db.get("total_exchanged", 0.0) + amount, 2)
    _save(db)
    return db["total_exchanged"]


def get_total() -> float:
    return _load().get("total_exchanged", 0.0)


# ── Blacklist ─────────────────────────────────────────────────

def is_blacklisted(user_id: int) -> bool:
    return str(user_id) in _load().get("blacklist", [])


def add_blacklist(user_id: int):
    db = _load()
    if str(user_id) not in db.get("blacklist", []):
        db.setdefault("blacklist", []).append(str(user_id))
    _save(db)


def remove_blacklist(user_id: int):
    db = _load()
    db["blacklist"] = [x for x in db.get("blacklist", []) if x != str(user_id)]
    _save(db)

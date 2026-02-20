import json
import os
from pathlib import Path

_config = None


def get_config() -> dict:
    global _config
    if _config is None:
        path = Path(__file__).parent.parent / "config.json"
        with open(path, "r", encoding="utf-8") as f:
            _config = json.load(f)
    return _config

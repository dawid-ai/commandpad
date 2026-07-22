# src/tokens.py
from datetime import date
from typing import Optional


def expand_tokens(text: str, today: Optional[date] = None) -> str:
    today = today or date.today()
    return text.replace("{today}", today.isoformat())

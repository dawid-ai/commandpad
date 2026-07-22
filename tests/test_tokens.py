from datetime import date
from src.tokens import expand_tokens


def test_today_token():
    assert expand_tokens("01-Daily/{today}", today=date(2026, 7, 22)) == "01-Daily/2026-07-22"


def test_no_token_unchanged():
    assert expand_tokens("ctrl+c", today=date(2026, 7, 22)) == "ctrl+c"


def test_multiple_tokens():
    assert expand_tokens("{today}-{today}", today=date(2026, 1, 2)) == "2026-01-02-2026-01-02"

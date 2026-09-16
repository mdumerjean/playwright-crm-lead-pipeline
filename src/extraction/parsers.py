"""Pure parsing helpers for turning raw scraped strings into typed values.

Kept dependency-free (no Playwright, no I/O) so they can be unit tested
directly against strings without a browser.
"""
from __future__ import annotations

import re
from typing import Optional

_CURRENCY_SYMBOLS = {
    "£": "GBP",
    "$": "USD",
    "€": "EUR",
}

_RATING_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
}

_AVAILABILITY_QTY_RE = re.compile(r"\((\d+)\s+available\)", re.IGNORECASE)


def parse_price(price_text: Optional[str]) -> tuple[Optional[float], Optional[str]]:
    """"£51.77" -> (51.77, "GBP"). Returns (None, None) if unparsable."""
    if not price_text:
        return None, None
    text = price_text.strip()
    currency = None
    for symbol, code in _CURRENCY_SYMBOLS.items():
        if symbol in text:
            currency = code
            text = text.replace(symbol, "")
            break
    text = re.sub(r"[^0-9.]", "", text)
    if not text:
        return None, currency
    try:
        return round(float(text), 2), currency
    except ValueError:
        return None, currency


def parse_availability(availability_text: Optional[str]) -> tuple[bool, Optional[int]]:
    """"In stock (19 available)" -> (True, 19). "Out of stock" -> (False, None)."""
    if not availability_text:
        return False, None
    text = availability_text.strip()
    in_stock = "in stock" in text.lower()
    match = _AVAILABILITY_QTY_RE.search(text)
    quantity = int(match.group(1)) if match else None
    return in_stock, quantity


def parse_rating(rating_text: Optional[str]) -> Optional[int]:
    """CSS class word like "Three" (from `class="star-rating Three"`) -> 3."""
    if not rating_text:
        return None
    return _RATING_WORDS.get(rating_text.strip().lower())


def parse_category_from_breadcrumb(breadcrumb_text: Optional[str]) -> Optional[str]:
    """"Home > Books > Travel > It's Only the Himalayas" -> "Travel"."""
    if not breadcrumb_text:
        return None
    parts = [p.strip() for p in breadcrumb_text.split(">") if p.strip()]
    if len(parts) >= 3:
        return parts[-2]
    return None


def clean_text(value: Optional[str]) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()

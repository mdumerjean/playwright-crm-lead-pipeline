"""Normalization, validation and deduplication.

Deliberately has zero Playwright/HTTP imports: it operates on `RawLead` in,
`Lead` (or a rejection) out, so it can be fully unit tested against plain
data and reused if the browser layer is ever swapped for a different
source.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.extraction.parsers import clean_text, parse_availability, parse_price, parse_rating
from src.models.lead import Lead, RawLead, ValidationStatus


@dataclass
class ValidationResult:
    lead: Lead | None
    status: ValidationStatus
    errors: list[str]


def normalize_and_validate(raw: RawLead) -> ValidationResult:
    """Clean + type-check a `RawLead`. Never raises: bad input becomes a REJECTED result."""
    errors: list[str] = []

    title = clean_text(raw.title)
    if not title:
        errors.append("missing_title")

    upc = clean_text(raw.upc)
    if not upc:
        errors.append("missing_upc")

    category = clean_text(raw.category) or "Uncategorized"

    price_amount, price_currency = parse_price(raw.price_text)
    if price_amount is None:
        errors.append("unparsable_price")
    elif price_amount <= 0:
        errors.append("non_positive_price")

    in_stock, stock_quantity = parse_availability(raw.availability_text)

    rating = parse_rating(raw.rating_text)

    description = clean_text(raw.description)

    if errors:
        return ValidationResult(lead=None, status=ValidationStatus.REJECTED, errors=errors)

    lead = Lead(
        source=raw.source,
        source_url=raw.source_url,
        title=title,
        price_amount=price_amount,
        price_currency=price_currency or "GBP",
        in_stock=in_stock,
        stock_quantity=stock_quantity,
        rating=rating,
        category=category,
        upc=upc,
        description=description,
        scraped_at=raw.scraped_at,
        validation_status=ValidationStatus.VALID,
        validation_errors=[],
    )
    return ValidationResult(lead=lead, status=ValidationStatus.VALID, errors=[])


class Deduplicator:
    """Tracks seen dedupe keys (UPC) across a run to reject repeat records."""

    def __init__(self) -> None:
        self._seen_keys: set[str] = set()

    def is_duplicate(self, lead: Lead) -> bool:
        return lead.dedupe_key in self._seen_keys

    def remember(self, lead: Lead) -> None:
        self._seen_keys.add(lead.dedupe_key)

    def __len__(self) -> int:
        return len(self._seen_keys)

"""Typed record models used throughout the pipeline.

`RawLead` mirrors exactly what the browser layer scraped off the page
(strings, unparsed). `Lead` is the normalized, validated record that
downstream layers (JSON export, CRM sync) actually consume. Keeping them
separate is what lets `src/browser` stay ignorant of validation rules and
`src/validation` stay ignorant of Playwright.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class ValidationStatus(str, Enum):
    VALID = "valid"
    REJECTED = "rejected"
    DUPLICATE = "duplicate"


@dataclass
class RawLead:
    """Unprocessed strings scraped directly from the DOM. No parsing/validation."""

    source: str
    source_url: str
    title: Optional[str]
    price_text: Optional[str]
    availability_text: Optional[str]
    rating_text: Optional[str]
    category: Optional[str]
    upc: Optional[str]
    description: Optional[str]
    scraped_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class Lead:
    """Normalized, CRM-ready record produced by the validation layer."""

    source: str
    source_url: str
    title: str
    price_amount: float
    price_currency: str
    in_stock: bool
    stock_quantity: Optional[int]
    rating: Optional[int]
    category: str
    upc: str
    description: str
    scraped_at: str
    validation_status: ValidationStatus = ValidationStatus.VALID
    validation_errors: list[str] = field(default_factory=list)

    @property
    def dedupe_key(self) -> str:
        return self.upc.strip().lower()

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "source_url": self.source_url,
            "title": self.title,
            "price_amount": self.price_amount,
            "price_currency": self.price_currency,
            "in_stock": self.in_stock,
            "stock_quantity": self.stock_quantity,
            "rating": self.rating,
            "category": self.category,
            "upc": self.upc,
            "description": self.description,
            "scraped_at": self.scraped_at,
            "validation_status": self.validation_status.value,
            "validation_errors": self.validation_errors,
        }

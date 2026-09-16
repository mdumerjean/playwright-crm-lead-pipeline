"""Central runtime configuration, loaded from environment variables.

Keeping every tunable value here means the scraping target, CRM endpoint,
and reliability knobs can all be changed via `.env` without touching
application logic.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return int(value)


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return float(value)


@dataclass(frozen=True)
class ScraperSettings:
    """Controls what the Playwright bot crawls."""

    base_url: str = field(default_factory=lambda: os.getenv("SOURCE_BASE_URL", "https://books.toscrape.com"))
    target_category_slug: str = field(
        default_factory=lambda: os.getenv("TARGET_CATEGORY_SLUG", "catalogue/category/books/mystery_3/index.html")
    )
    max_pages: int = field(default_factory=lambda: _env_int("MAX_PAGES", 2))
    max_records: int = field(default_factory=lambda: _env_int("MAX_RECORDS", 25))
    headless: bool = field(default_factory=lambda: _env_bool("HEADLESS", True))
    navigation_timeout_ms: int = field(default_factory=lambda: _env_int("NAVIGATION_TIMEOUT_MS", 15000))
    fetch_product_detail: bool = field(default_factory=lambda: _env_bool("FETCH_PRODUCT_DETAIL", True))


@dataclass(frozen=True)
class CRMSettings:
    """Controls the GoHighLevel-style CRM sync client."""

    mode: str = field(default_factory=lambda: os.getenv("CRM_MODE", "mock").strip().lower())
    api_base_url: str = field(default_factory=lambda: os.getenv("CRM_API_BASE_URL", "https://services.leadconnectorhq.com"))
    api_token: str = field(default_factory=lambda: os.getenv("CRM_API_TOKEN", ""))
    location_id: str = field(default_factory=lambda: os.getenv("CRM_LOCATION_ID", ""))
    retry_attempts: int = field(default_factory=lambda: _env_int("CRM_RETRY_ATTEMPTS", 3))
    retry_backoff_seconds: float = field(default_factory=lambda: _env_float("CRM_RETRY_BACKOFF_SECONDS", 0.5))
    request_timeout_seconds: float = field(default_factory=lambda: _env_float("CRM_REQUEST_TIMEOUT_SECONDS", 10.0))
    mock_transient_failure_rate: float = field(
        default_factory=lambda: _env_float("CRM_MOCK_FAILURE_RATE", 0.2)
    )

    @property
    def is_live(self) -> bool:
        return self.mode == "live"


@dataclass(frozen=True)
class PathSettings:
    output_dir: Path = field(default_factory=lambda: PROJECT_ROOT / os.getenv("OUTPUT_DIR", "output"))
    screenshot_dir: Path = field(default_factory=lambda: PROJECT_ROOT / os.getenv("SCREENSHOT_DIR", "screenshots"))
    log_dir: Path = field(default_factory=lambda: PROJECT_ROOT / os.getenv("LOG_DIR", "output/logs"))

    def ensure(self) -> None:
        for directory in (self.output_dir, self.screenshot_dir, self.log_dir):
            directory.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class Settings:
    scraper: ScraperSettings = field(default_factory=ScraperSettings)
    crm: CRMSettings = field(default_factory=CRMSettings)
    paths: PathSettings = field(default_factory=PathSettings)
    screenshots_enabled: bool = field(default_factory=lambda: _env_bool("SCREENSHOTS_ENABLED", True))


def load_settings() -> Settings:
    settings = Settings()
    settings.paths.ensure()
    return settings

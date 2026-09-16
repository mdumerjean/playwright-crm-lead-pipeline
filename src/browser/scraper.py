"""Playwright automation for books.toscrape.com.

books.toscrape.com is a public sandbox explicitly built (by Zyte/Scrapinghub)
for practicing web scraping -- its own banner states "This is a demo website
for web scraping purposes." No login, CAPTCHA, or rate limiting is in play,
and there is no robots.txt restricting crawling.

Design notes on selectors:
- Listing pages use `.product_pod` article cards; title/price/availability
  are read from there, which avoids an extra page load per book for the
  three fields common enough to filter/sort on.
- The UPC (a stable unique id) and full description only exist on the
  product detail page, so `fetch_product_detail=True` follows each card's
  link. This doubles page loads but demonstrates multi-page navigation and
  gives a real dedupe key instead of a fragile title-based one.
- `page.wait_for_selector` / `wait_for_load_state("networkidle")` are used
  instead of fixed `sleep()` calls so the bot waits exactly as long as the
  page needs and no longer.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator, Optional
from urllib.parse import urljoin

from playwright.async_api import Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeoutError, async_playwright

from src.config.settings import ScraperSettings
from src.logging.logger import Stage, log_stage
from src.models.lead import RawLead


@dataclass
class ScrapeStats:
    pages_visited: int = 0
    cards_discovered: int = 0
    detail_fetch_failures: int = 0


@dataclass
class _CardSnapshot:
    """Fields readable straight off a `.product_pod` listing card, no navigation needed."""

    detail_url: str
    title: Optional[str]
    price_text: Optional[str]
    availability_text: Optional[str]
    rating_text: Optional[str]


class BookScraper:
    """Drives Chromium through books.toscrape.com and yields `RawLead` records."""

    def __init__(
        self,
        settings: ScraperSettings,
        logger: logging.Logger,
        screenshot_dir: Optional[Path] = None,
        screenshots_enabled: bool = True,
    ) -> None:
        self._settings = settings
        self._logger = logger
        self._screenshot_dir = screenshot_dir
        self._screenshots_enabled = screenshots_enabled and screenshot_dir is not None
        self.stats = ScrapeStats()

        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None

    async def __aenter__(self) -> "BookScraper":
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self._settings.headless)
        self._context = await self._browser.new_context(
            user_agent="Mozilla/5.0 (compatible; PortfolioLeadBot/1.0; +https://example.invalid/bot)"
        )
        self._context.set_default_navigation_timeout(self._settings.navigation_timeout_ms)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def _screenshot(self, page: Page, name: str) -> None:
        if not self._screenshots_enabled:
            return
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = self._screenshot_dir / f"{timestamp}_{name}.png"
        await page.screenshot(path=str(path), full_page=False)
        log_stage(self._logger, Stage.SCREENSHOT_SAVED, f"path={path.name}")

    async def iter_leads(self) -> AsyncIterator[RawLead]:
        """Navigate the target category, paginating and yielding one `RawLead` per book found."""
        assert self._context is not None, "BookScraper must be used as an async context manager"
        page = await self._context.new_page()

        start_url = urljoin(self._settings.base_url + "/", self._settings.target_category_slug)
        current_url = start_url
        yielded = 0

        try:
            for page_index in range(1, self._settings.max_pages + 1):
                if yielded >= self._settings.max_records:
                    break

                try:
                    await page.goto(current_url, wait_until="domcontentloaded")
                    await page.wait_for_selector(".product_pod, .alert", timeout=self._settings.navigation_timeout_ms)
                except PlaywrightTimeoutError:
                    self._logger.warning(
                        "Navigation timed out loading %s; stopping pagination.",
                        current_url,
                        extra={"stage": Stage.RECORD_EXTRACTION_FAILED},
                    )
                    break

                self.stats.pages_visited += 1
                log_stage(self._logger, Stage.PAGE_LOADED, f"url={current_url} page={page_index}")

                if page_index == 1:
                    await self._screenshot(page, "listing_page1")

                cards = page.locator(".product_pod")
                card_count = await cards.count()
                self.stats.cards_discovered += card_count
                log_stage(self._logger, Stage.RECORD_DISCOVERED, f"cards_on_page={card_count}")

                # Capture everything we need from the listing cards -- including the detail
                # link -- while `page` is still on the listing page. `_extract_detail` below
                # navigates `page` away to each product's own URL, so both the card snapshot
                # and the "next page" link must be resolved before that happens.
                card_snapshots: list[_CardSnapshot] = []
                for i in range(card_count):
                    card = cards.nth(i)
                    link_locator = card.locator("h3 a")
                    href = await link_locator.get_attribute("href")
                    if not href:
                        continue
                    title_attr = await link_locator.get_attribute("title")
                    price_text = await card.locator(".price_color").inner_text()
                    availability_text = await card.locator(".availability").inner_text()
                    rating_class = await card.locator(".star-rating").get_attribute("class")
                    card_snapshots.append(
                        _CardSnapshot(
                            detail_url=urljoin(current_url, href),
                            title=title_attr,
                            price_text=price_text,
                            availability_text=availability_text,
                            rating_text=(rating_class or "").replace("star-rating", "").strip() or None,
                        )
                    )

                next_href = await self._get_next_page_href(page)

                for snapshot in card_snapshots:
                    if yielded >= self._settings.max_records:
                        break
                    if self._settings.fetch_product_detail:
                        lead = await self._extract_detail(page, snapshot.detail_url)
                    else:
                        lead = self._extract_from_snapshot(snapshot)
                    if lead is not None:
                        yielded += 1
                        yield lead

                if not next_href:
                    break
                current_url = urljoin(current_url, next_href)
        finally:
            await page.close()

    async def _get_next_page_href(self, page: Page) -> Optional[str]:
        next_link = page.locator("li.next a")
        if await next_link.count() == 0:
            return None
        return await next_link.get_attribute("href")

    def _extract_from_snapshot(self, snapshot: "_CardSnapshot") -> Optional[RawLead]:
        """Listing-only mode: build a `RawLead` straight from the card, no detail page load.

        Cards don't expose a UPC, so the trailing `<slug>_<id>` segment of the detail URL
        (e.g. "sharp-objects_997") is used as the dedupe key instead -- it's stable and
        unique per product on this site, same as the real UPC would be.
        """
        if not snapshot.title:
            self.stats.detail_fetch_failures += 1
            self._logger.warning(
                "Listing card missing title for %s; skipping.",
                snapshot.detail_url,
                extra={"stage": Stage.RECORD_EXTRACTION_FAILED},
            )
            return None

        slug = snapshot.detail_url.rstrip("/").rsplit("/", 2)[-2]
        log_stage(self._logger, Stage.RECORD_EXTRACTED, f"title={snapshot.title!r} upc={slug} (listing-only)")

        return RawLead(
            source="books.toscrape.com",
            source_url=snapshot.detail_url,
            title=snapshot.title,
            price_text=snapshot.price_text,
            availability_text=snapshot.availability_text,
            rating_text=snapshot.rating_text,
            category=None,
            upc=slug,
            description=None,
        )

    async def _extract_detail(self, page: Page, detail_url: str) -> Optional[RawLead]:
        try:
            await page.goto(detail_url, wait_until="domcontentloaded")
            await page.wait_for_selector(".product_main", timeout=self._settings.navigation_timeout_ms)
        except PlaywrightTimeoutError:
            self.stats.detail_fetch_failures += 1
            self._logger.warning(
                "Timed out loading product detail page %s", detail_url, extra={"stage": Stage.RECORD_EXTRACTION_FAILED}
            )
            return None

        try:
            title = await page.locator(".product_main h1").inner_text()
        except Exception:
            title = None

        try:
            price_text = await page.locator(".product_main .price_color").first.inner_text()
        except Exception:
            price_text = None

        try:
            availability_text = await page.locator(".product_main .availability").inner_text()
        except Exception:
            availability_text = None

        rating_text = None
        try:
            rating_class = await page.locator(".product_main .star-rating").get_attribute("class")
            if rating_class:
                rating_text = rating_class.replace("star-rating", "").strip()
        except Exception:
            pass

        category = None
        try:
            breadcrumb_links = page.locator(".breadcrumb li a")
            if await breadcrumb_links.count() > 0:
                category = await breadcrumb_links.last.inner_text()
        except Exception:
            pass

        upc = None
        try:
            upc = await page.locator("table.table.table-striped tr:has(th:text-is('UPC')) td").inner_text()
        except Exception:
            pass

        description = None
        try:
            desc_locator = page.locator("#product_description ~ p")
            if await desc_locator.count() > 0:
                description = await desc_locator.first.inner_text()
        except Exception:
            pass

        if not title or not upc:
            self.stats.detail_fetch_failures += 1
            self._logger.warning(
                "Missing required fields (title/upc) on %s; skipping.",
                detail_url,
                extra={"stage": Stage.RECORD_EXTRACTION_FAILED},
            )
            return None

        log_stage(self._logger, Stage.RECORD_EXTRACTED, f"title={title!r} upc={upc}")

        return RawLead(
            source="books.toscrape.com",
            source_url=detail_url,
            title=title,
            price_text=price_text,
            availability_text=availability_text,
            rating_text=rating_text,
            category=category,
            upc=upc,
            description=description,
        )

"""End-to-end orchestration: scrape -> validate -> dedupe -> export -> CRM sync.

This is the only module that knows about every layer; each layer module
stays independently testable and swappable (see README "Architecture").
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from src.browser.scraper import BookScraper
from src.config.settings import Settings
from src.integrations.crm_client import CRMClient
from src.logging.logger import Stage, configure_logging, log_stage
from src.models.crm_payload import build_crm_payload
from src.models.lead import Lead, ValidationStatus
from src.validation.validators import Deduplicator, normalize_and_validate


@dataclass
class RunSummary:
    run_id: str
    started_at: str
    finished_at: str = ""
    duration_seconds: float = 0.0
    records_discovered: int = 0
    records_extracted: int = 0
    records_rejected: int = 0
    duplicates_skipped: int = 0
    crm_sync_successes: int = 0
    crm_sync_failures: int = 0
    output_file: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


async def run_pipeline(settings: Settings) -> RunSummary:
    logger = configure_logging(settings.paths.log_dir)
    run_id = datetime.now(timezone.utc).strftime("run_%Y%m%dT%H%M%SZ")
    started = time.monotonic()
    summary = RunSummary(run_id=run_id, started_at=datetime.now(timezone.utc).isoformat())

    log_stage(
        logger,
        Stage.BOT_STARTED,
        f"run_id={run_id} target={settings.scraper.base_url} "
        f"category_slug={settings.scraper.target_category_slug} crm_mode={settings.crm.mode}",
    )

    deduplicator = Deduplicator()
    crm_client = CRMClient(settings.crm, logger)
    valid_leads: list[Lead] = []
    rejected_records: list[dict] = []

    async with BookScraper(
        settings.scraper,
        logger,
        screenshot_dir=settings.paths.screenshot_dir,
        screenshots_enabled=settings.screenshots_enabled,
    ) as scraper:
        async for raw_lead in scraper.iter_leads():
            result = normalize_and_validate(raw_lead)

            if result.status == ValidationStatus.REJECTED:
                summary.records_rejected += 1
                rejected_records.append(
                    {"source_url": raw_lead.source_url, "title": raw_lead.title, "errors": result.errors}
                )
                log_stage(
                    logger,
                    Stage.RECORD_REJECTED,
                    f"url={raw_lead.source_url} errors={result.errors}",
                    level=logging.WARNING,
                )
                continue

            lead = result.lead
            assert lead is not None

            if deduplicator.is_duplicate(lead):
                summary.duplicates_skipped += 1
                log_stage(logger, Stage.DUPLICATE_SKIPPED, f"upc={lead.upc} title={lead.title!r}")
                continue

            deduplicator.remember(lead)
            log_stage(logger, Stage.RECORD_VALIDATED, f"upc={lead.upc} title={lead.title!r}")
            summary.records_extracted += 1
            valid_leads.append(lead)

        summary.records_discovered = scraper.stats.cards_discovered

    output_records = []
    for lead in valid_leads:
        payload = build_crm_payload(lead, location_id=settings.crm.location_id)
        sync_result = await crm_client.sync_contact(payload)

        if sync_result.success:
            summary.crm_sync_successes += 1
        else:
            summary.crm_sync_failures += 1

        output_records.append(
            {
                "extraction_timestamp": lead.scraped_at,
                "source": lead.source,
                "record": lead.to_dict(),
                "crm_sync": {
                    "attempted": True,
                    "success": sync_result.success,
                    "attempts": sync_result.attempts,
                    "status_code": sync_result.status_code,
                    "detail": sync_result.detail,
                    "mode": settings.crm.mode,
                },
            }
        )

    finished = time.monotonic()
    summary.duration_seconds = round(finished - started, 3)
    summary.finished_at = datetime.now(timezone.utc).isoformat()

    output_path = settings.paths.output_dir / f"{run_id}.json"
    summary.output_file = str(output_path)
    _write_output(output_path, run_id, settings, output_records, rejected_records, summary)

    log_stage(
        logger,
        Stage.BOT_COMPLETED,
        (
            f"discovered={summary.records_discovered} extracted={summary.records_extracted} "
            f"rejected={summary.records_rejected} duplicates={summary.duplicates_skipped} "
            f"crm_success={summary.crm_sync_successes} crm_failure={summary.crm_sync_failures} "
            f"duration_s={summary.duration_seconds} output={output_path.name}"
        ),
    )

    return summary


def _write_output(
    output_path: Path,
    run_id: str,
    settings: Settings,
    output_records: list[dict],
    rejected_records: list[dict],
    summary: RunSummary,
) -> None:
    document = {
        "run_id": run_id,
        "extraction_timestamp": datetime.now(timezone.utc).isoformat(),
        "source": settings.scraper.base_url,
        "crm_mode": settings.crm.mode,
        "summary": summary.to_dict(),
        "records": output_records,
        "rejected_records": rejected_records,
    }
    output_path.write_text(json.dumps(document, indent=2), encoding="utf-8")

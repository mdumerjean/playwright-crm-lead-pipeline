"""Entry point: run the full scrape -> validate -> CRM sync pipeline.

Usage:
    python main.py
"""
from __future__ import annotations

import asyncio

from src.config.settings import load_settings
from src.pipeline import run_pipeline


def print_summary(summary) -> None:
    print()
    print("=" * 60)
    print("RUN SUMMARY")
    print("=" * 60)
    print(f"Run ID:                 {summary.run_id}")
    print(f"Records discovered:     {summary.records_discovered}")
    print(f"Records extracted:      {summary.records_extracted}")
    print(f"Records rejected:       {summary.records_rejected}")
    print(f"Duplicates skipped:     {summary.duplicates_skipped}")
    print(f"CRM sync successes:     {summary.crm_sync_successes}")
    print(f"CRM sync failures:      {summary.crm_sync_failures}")
    print(f"Total execution time:   {summary.duration_seconds}s")
    print(f"Output file:            {summary.output_file}")
    print("=" * 60)


async def main() -> None:
    settings = load_settings()
    summary = await run_pipeline(settings)
    print_summary(summary)


if __name__ == "__main__":
    asyncio.run(main())

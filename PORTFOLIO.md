# Portfolio Summary: AI-Assisted Browser Automation → CRM Sync

## Problem

Businesses that rely on web portals for lead or catalog data usually need
the same pipeline built around them: reliably pull structured records out
of a site that has no API, clean and validate that data, avoid pushing
duplicates, and land it in a CRM — with clear visibility into what
succeeded, what failed, and why.

## Solution

A working Python + Playwright automation that navigates a public site,
paginates through category listings, follows each record to its detail
page, and extracts structured fields (title, price, stock status, rating,
category, description, and a stable unique ID). Extracted records pass
through a dedicated validation/normalization layer that trims and
type-checks fields, rejects malformed records (with reasons), and
deduplicates by unique ID. Valid records are written to timestamped,
structured JSON and synchronized to a CRM API client modeled on
GoHighLevel's contacts endpoint, with retry-with-backoff on transient
failures and per-record success/failure logging. A concise run summary
(discovered / extracted / rejected / duplicates / CRM successes / CRM
failures / duration) is printed at the end of every run.

**Evidence:** a real Playwright screenshot ([docs/demo-screenshot.png](docs/demo-screenshot.png))
and the full structured JSON output ([docs/sample-output.json](docs/sample-output.json))
from an actual successful run are included in the repository, along with
a full `pytest` suite.

## Architecture

```
Web Portal (Playwright)
   → Data Extraction (typed RawLead records)
   → Validation & Normalization (typed Lead records, rejections tracked)
   → Deduplication (by stable unique ID)
   → Structured JSON output (output/run_*.json)
   → CRM API Client (GoHighLevel-style, mock or live, retry/backoff)
   → Structured logs + run summary (output/logs/run.log)
```

Each stage is an independently testable module with no leakage between
concerns: the browser layer never touches validation rules, the validation
layer never touches Playwright or HTTP, and the CRM client never touches
scraping logic. Swapping the source site, the extraction selectors, or the
CRM endpoint touches only the corresponding module.

## Key capabilities

- Real async Playwright automation: intelligent waits (no fixed sleeps),
  multi-page pagination, category filtering, and multi-page-per-record
  navigation (listing → detail page).
- Typed extraction models (`RawLead` → `Lead`) instead of loose dicts.
- A standalone validation/normalization/deduplication layer with its own
  unit tests, independent of the browser and the CRM.
- A GoHighLevel-style CRM client with a safe default mock mode (no
  credentials required to run the full demo) and a fully implemented live
  mode gated behind environment variables.
- Retry-with-exponential-backoff on transient CRM failures, fail-fast on
  non-retryable ones, and per-attempt structured logging.
- One bad record, one failed sync, or one navigation timeout never aborts
  the run — every stage isolates its own failures.
- 35 automated tests covering parsing, validation, deduplication, CRM
  payload mapping, and both CRM client modes (mock and live, with the live
  HTTP layer mocked).

## Reliability considerations

- Navigation timeouts, missing/malformed DOM elements, invalid records,
  duplicate records, and CRM HTTP failures are all handled explicitly and
  logged with a distinct stage tag, rather than allowed to crash the run
  or fail silently.
- The retry path for CRM sync was verified to actually trigger (not just
  written and untested) — mock mode has a configurable simulated failure
  rate specifically so the backoff/retry logic is exercised on real runs.
- A deliberately-broken source URL (nonexistent category) was run through
  the full pipeline during development and completed cleanly with a zero
  summary instead of crashing, confirming the error-handling path works
  against the live site, not just in unit tests.

## Technologies

Python 3.9 (`asyncio`), Playwright (async API), httpx, python-dotenv,
pytest + pytest-asyncio, standard library structured logging.

## What could be changed for a production client

- Swap the mapped "book → contact" payload for the client's real
  lead/contact field mapping (name, email, phone, company) — the mapping
  function is isolated to a single file (`src/models/crm_payload.py`).
- Point `CRM_MODE=live` at the client's real GoHighLevel (or other CRM)
  credentials, supplied via environment variables / secrets manager —
  never hardcoded.
- Replace the source-site selectors in `src/browser/scraper.py` with the
  client's actual portal's selectors; the rest of the pipeline is
  unaffected.
- Add persistent (cross-run) deduplication, e.g. against the CRM's own
  lookup API or a local database, instead of per-run-only dedup.
- Add scheduled/CI execution (e.g. GitHub Actions cron) for recurring
  syncs, plus alerting on elevated failure rates.

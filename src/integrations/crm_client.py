"""GoHighLevel-style CRM API client.

Two modes, selected by `CRM_MODE` in the environment:

- "mock" (default): no network calls at all. Simulates latency and an
  occasional transient failure so the retry path is exercised honestly,
  without requiring real GoHighLevel credentials for this portfolio demo.
- "live": POSTs to `CRM_API_BASE_URL` with a bearer token from
  `CRM_API_TOKEN`, read only from the environment -- never hardcoded,
  never logged.

Both modes share the same retry/backoff and logging behavior so swapping
modes doesn't change the pipeline's error-handling guarantees.
"""
from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass
from typing import Optional

import httpx

from src.config.settings import CRMSettings
from src.logging.logger import Stage, log_stage
from src.models.crm_payload import CRMContactPayload


@dataclass
class CRMSyncResult:
    success: bool
    status_code: Optional[int]
    attempts: int
    detail: str


class TransientCRMError(Exception):
    """Raised for retryable failures (e.g. simulated 503 / network blip)."""


class CRMClient:
    def __init__(self, settings: CRMSettings, logger: logging.Logger, rng: Optional[random.Random] = None) -> None:
        self._settings = settings
        self._logger = logger
        self._rng = rng or random.Random()

    async def sync_contact(self, payload: CRMContactPayload) -> CRMSyncResult:
        """Push one contact payload with retry-on-transient-failure. Never raises."""
        log_stage(
            self._logger,
            Stage.CRM_SYNC_ATTEMPTED,
            f"name={payload.name!r} mode={self._settings.mode}",
        )

        attempt = 0
        last_error = ""
        while attempt < self._settings.retry_attempts:
            attempt += 1
            try:
                status_code = await self._send(payload)
                log_stage(
                    self._logger,
                    Stage.CRM_SYNC_SUCCESS,
                    f"name={payload.name!r} attempt={attempt} status={status_code}",
                )
                return CRMSyncResult(success=True, status_code=status_code, attempts=attempt, detail="ok")
            except TransientCRMError as exc:
                last_error = str(exc)
                if attempt < self._settings.retry_attempts:
                    backoff = self._settings.retry_backoff_seconds * (2 ** (attempt - 1))
                    log_stage(
                        self._logger,
                        Stage.CRM_SYNC_RETRY,
                        f"name={payload.name!r} attempt={attempt} reason={last_error} backoff={backoff:.2f}s",
                        level=logging.WARNING,
                    )
                    await asyncio.sleep(backoff)
            except httpx.HTTPStatusError as exc:
                last_error = f"http_{exc.response.status_code}"
                log_stage(
                    self._logger,
                    Stage.CRM_SYNC_FAILURE,
                    f"name={payload.name!r} attempt={attempt} reason={last_error} (non-retryable)",
                    level=logging.ERROR,
                )
                return CRMSyncResult(
                    success=False, status_code=exc.response.status_code, attempts=attempt, detail=last_error
                )
            except Exception as exc:  # unexpected -- still don't crash the whole run
                last_error = f"unexpected:{exc}"
                log_stage(
                    self._logger,
                    Stage.CRM_SYNC_FAILURE,
                    f"name={payload.name!r} attempt={attempt} reason={last_error}",
                    level=logging.ERROR,
                )
                return CRMSyncResult(success=False, status_code=None, attempts=attempt, detail=last_error)

        log_stage(
            self._logger,
            Stage.CRM_SYNC_FAILURE,
            f"name={payload.name!r} attempts={attempt} reason={last_error} (exhausted retries)",
            level=logging.ERROR,
        )
        return CRMSyncResult(success=False, status_code=None, attempts=attempt, detail=last_error)

    async def _send(self, payload: CRMContactPayload) -> int:
        if self._settings.is_live:
            return await self._send_live(payload)
        return await self._send_mock(payload)

    async def _send_live(self, payload: CRMContactPayload) -> int:
        headers = {
            "Authorization": f"Bearer {self._settings.api_token}",
            "Content-Type": "application/json",
            "Version": "2021-07-28",
        }
        async with httpx.AsyncClient(timeout=self._settings.request_timeout_seconds) as client:
            try:
                response = await client.post(
                    f"{self._settings.api_base_url}/contacts/",
                    json=payload.to_api_dict(),
                    headers=headers,
                )
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout) as exc:
                raise TransientCRMError(f"network:{exc.__class__.__name__}") from exc

            if response.status_code in (429, 500, 502, 503, 504):
                raise TransientCRMError(f"http_{response.status_code}")
            response.raise_for_status()
            return response.status_code

    async def _send_mock(self, payload: CRMContactPayload) -> int:
        """Simulate a realistic CRM round trip without any network access."""
        await asyncio.sleep(0.05)
        if self._rng.random() < self._settings.mock_transient_failure_rate:
            raise TransientCRMError("simulated_503")
        return 201

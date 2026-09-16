import random

import httpx
import pytest

from src.config.settings import CRMSettings
from src.integrations.crm_client import CRMClient
from src.models.crm_payload import CRMContactPayload
from src.models.lead import Lead, ValidationStatus
from tests.helpers import make_test_logger


def make_payload() -> CRMContactPayload:
    return CRMContactPayload(
        name="It's Only the Himalayas",
        company_name="Travel Catalog",
        source="books.toscrape.com",
        tags=["travel", "in-stock", "rating-2"],
        custom_fields={"upc": "a22124811bfa8350", "price_amount": 45.17},
    )


@pytest.mark.asyncio
async def test_mock_sync_succeeds_when_failure_rate_zero():
    settings = CRMSettings(mode="mock", mock_transient_failure_rate=0.0, retry_attempts=3, retry_backoff_seconds=0.0)
    client = CRMClient(settings, make_test_logger())

    result = await client.sync_contact(make_payload())

    assert result.success is True
    assert result.status_code == 201
    assert result.attempts == 1


@pytest.mark.asyncio
async def test_mock_sync_retries_then_succeeds():
    # rng sequence: first two calls fail the < failure_rate check, third succeeds.
    rng = random.Random()
    rng.random = iter([0.01, 0.01, 0.99]).__next__  # type: ignore[method-assign]
    settings = CRMSettings(mode="mock", mock_transient_failure_rate=0.5, retry_attempts=3, retry_backoff_seconds=0.0)
    client = CRMClient(settings, make_test_logger(), rng=rng)

    result = await client.sync_contact(make_payload())

    assert result.success is True
    assert result.attempts == 3


@pytest.mark.asyncio
async def test_mock_sync_fails_after_exhausting_retries():
    settings = CRMSettings(mode="mock", mock_transient_failure_rate=1.0, retry_attempts=3, retry_backoff_seconds=0.0)
    client = CRMClient(settings, make_test_logger())

    result = await client.sync_contact(make_payload())

    assert result.success is False
    assert result.attempts == 3
    assert "simulated_503" in result.detail


@pytest.mark.asyncio
async def test_live_sync_success(monkeypatch):
    settings = CRMSettings(
        mode="live",
        api_base_url="https://fake-crm.example.invalid",
        api_token="fake-token",
        retry_attempts=2,
        retry_backoff_seconds=0.0,
    )
    client = CRMClient(settings, make_test_logger())

    class FakeResponse:
        status_code = 201

        def raise_for_status(self):
            return None

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json, headers):
            assert headers["Authorization"] == "Bearer fake-token"
            assert "Bearer " in headers["Authorization"]
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    result = await client.sync_contact(make_payload())

    assert result.success is True
    assert result.status_code == 201


@pytest.mark.asyncio
async def test_live_sync_retries_on_503_then_succeeds(monkeypatch):
    settings = CRMSettings(
        mode="live",
        api_base_url="https://fake-crm.example.invalid",
        api_token="fake-token",
        retry_attempts=2,
        retry_backoff_seconds=0.0,
    )
    client = CRMClient(settings, make_test_logger())

    calls = {"count": 0}

    class FakeResponse503:
        status_code = 503

    class FakeResponse201:
        status_code = 201

        def raise_for_status(self):
            return None

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json, headers):
            calls["count"] += 1
            if calls["count"] == 1:
                return FakeResponse503()
            return FakeResponse201()

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    result = await client.sync_contact(make_payload())

    assert result.success is True
    assert calls["count"] == 2


@pytest.mark.asyncio
async def test_live_sync_non_retryable_http_error_fails_fast(monkeypatch):
    settings = CRMSettings(
        mode="live",
        api_base_url="https://fake-crm.example.invalid",
        api_token="fake-token",
        retry_attempts=3,
        retry_backoff_seconds=0.0,
    )
    client = CRMClient(settings, make_test_logger())

    class FakeResponse400:
        status_code = 400

        def raise_for_status(self):
            request = httpx.Request("POST", "https://fake-crm.example.invalid/contacts/")
            response = httpx.Response(400, request=request)
            raise httpx.HTTPStatusError("Bad Request", request=request, response=response)

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json, headers):
            return FakeResponse400()

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    result = await client.sync_contact(make_payload())

    assert result.success is False
    assert result.attempts == 1  # non-retryable, should not consume all retry_attempts
    assert result.status_code == 400

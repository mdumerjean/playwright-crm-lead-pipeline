from src.models.lead import RawLead, ValidationStatus
from src.validation.validators import Deduplicator, normalize_and_validate


def make_raw_lead(**overrides) -> RawLead:
    defaults = dict(
        source="books.toscrape.com",
        source_url="https://books.toscrape.com/catalogue/example_1/index.html",
        title="  It's Only the Himalayas  ",
        price_text="£45.17",
        availability_text="In stock (19 available)",
        rating_text="Two",
        category="Travel",
        upc="a22124811bfa8350",
        description="Some description.",
    )
    defaults.update(overrides)
    return RawLead(**defaults)


def test_valid_record_passes_and_normalizes():
    result = normalize_and_validate(make_raw_lead())
    assert result.status == ValidationStatus.VALID
    assert result.lead is not None
    assert result.lead.title == "It's Only the Himalayas"
    assert result.lead.price_amount == 45.17
    assert result.lead.price_currency == "GBP"
    assert result.lead.in_stock is True
    assert result.lead.stock_quantity == 19
    assert result.lead.rating == 2
    assert result.errors == []


def test_missing_title_is_rejected():
    result = normalize_and_validate(make_raw_lead(title=""))
    assert result.status == ValidationStatus.REJECTED
    assert result.lead is None
    assert "missing_title" in result.errors


def test_missing_upc_is_rejected():
    result = normalize_and_validate(make_raw_lead(upc=None))
    assert result.status == ValidationStatus.REJECTED
    assert "missing_upc" in result.errors


def test_unparsable_price_is_rejected():
    result = normalize_and_validate(make_raw_lead(price_text="not-a-price"))
    assert result.status == ValidationStatus.REJECTED
    assert "unparsable_price" in result.errors


def test_zero_price_is_rejected():
    result = normalize_and_validate(make_raw_lead(price_text="£0.00"))
    assert result.status == ValidationStatus.REJECTED
    assert "non_positive_price" in result.errors


def test_missing_category_defaults_to_uncategorized():
    result = normalize_and_validate(make_raw_lead(category=None))
    assert result.status == ValidationStatus.VALID
    assert result.lead.category == "Uncategorized"


def test_out_of_stock_record_still_valid():
    result = normalize_and_validate(make_raw_lead(availability_text="Out of stock"))
    assert result.status == ValidationStatus.VALID
    assert result.lead.in_stock is False
    assert result.lead.stock_quantity is None


def test_multiple_errors_are_all_reported():
    result = normalize_and_validate(make_raw_lead(title="", upc="", price_text=None))
    assert result.status == ValidationStatus.REJECTED
    assert set(result.errors) == {"missing_title", "missing_upc", "unparsable_price"}


def test_deduplicator_flags_repeated_upc():
    dedup = Deduplicator()
    first = normalize_and_validate(make_raw_lead(upc="ABC123")).lead
    second = normalize_and_validate(make_raw_lead(upc="ABC123", title="Different Title")).lead

    assert not dedup.is_duplicate(first)
    dedup.remember(first)
    assert dedup.is_duplicate(second)


def test_deduplicator_is_case_insensitive_on_upc():
    dedup = Deduplicator()
    first = normalize_and_validate(make_raw_lead(upc="abc123")).lead
    second = normalize_and_validate(make_raw_lead(upc="ABC123")).lead

    dedup.remember(first)
    assert dedup.is_duplicate(second)


def test_deduplicator_allows_distinct_records():
    dedup = Deduplicator()
    first = normalize_and_validate(make_raw_lead(upc="AAA111")).lead
    second = normalize_and_validate(make_raw_lead(upc="BBB222")).lead

    dedup.remember(first)
    assert not dedup.is_duplicate(second)
    assert len(dedup) == 1

from src.models.crm_payload import build_crm_payload
from src.models.lead import Lead, ValidationStatus


def make_lead(**overrides) -> Lead:
    defaults = dict(
        source="books.toscrape.com",
        source_url="https://books.toscrape.com/catalogue/example_1/index.html",
        title="It's Only the Himalayas",
        price_amount=45.17,
        price_currency="GBP",
        in_stock=True,
        stock_quantity=19,
        rating=2,
        category="Travel",
        upc="a22124811bfa8350",
        description="Some description.",
        scraped_at="2026-01-01T00:00:00+00:00",
        validation_status=ValidationStatus.VALID,
        validation_errors=[],
    )
    defaults.update(overrides)
    return Lead(**defaults)


def test_build_crm_payload_maps_core_fields():
    lead = make_lead()
    payload = build_crm_payload(lead, location_id="loc_123")

    assert payload.name == "It's Only the Himalayas"
    assert payload.company_name == "Travel Catalog"
    assert payload.source == "books.toscrape.com"
    assert "travel" in payload.tags
    assert "in-stock" in payload.tags
    assert "rating-2" in payload.tags
    assert payload.custom_fields["upc"] == "a22124811bfa8350"
    assert payload.location_id == "loc_123"


def test_build_crm_payload_out_of_stock_tag():
    lead = make_lead(in_stock=False, stock_quantity=None)
    payload = build_crm_payload(lead)
    assert "out-of-stock" in payload.tags


def test_to_api_dict_shape():
    lead = make_lead()
    payload = build_crm_payload(lead, location_id="loc_123")
    api_dict = payload.to_api_dict()

    assert api_dict["name"] == lead.title
    assert api_dict["locationId"] == "loc_123"
    assert isinstance(api_dict["customFields"], list)
    assert {"key": "upc", "field_value": "a22124811bfa8350"} in api_dict["customFields"]


def test_to_api_dict_omits_location_id_when_empty():
    lead = make_lead()
    payload = build_crm_payload(lead)
    api_dict = payload.to_api_dict()
    assert "locationId" not in api_dict

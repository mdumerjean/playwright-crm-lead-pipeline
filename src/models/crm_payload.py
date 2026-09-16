"""GoHighLevel-shaped outbound payload.

The `/contacts/` endpoint on GoHighLevel's API accepts roughly this shape
(name, source, tags, customFields, locationId). The demo source site has
no real people in it, so a `Lead` (a scraped product/catalog record) is
mapped onto the contact schema as a stand-in "company lead" -- this keeps
the integration honest to a real CRM contract without scraping or
fabricating anyone's personal information. See README "Known limitations".
"""
from __future__ import annotations

from dataclasses import dataclass, field

from src.models.lead import Lead


@dataclass
class CRMContactPayload:
    name: str
    company_name: str
    source: str
    tags: list[str]
    custom_fields: dict
    location_id: str = ""

    def to_api_dict(self) -> dict:
        """Shape matching GoHighLevel's contacts API request body."""
        payload = {
            "name": self.name,
            "companyName": self.company_name,
            "source": self.source,
            "tags": self.tags,
            "customFields": [
                {"key": key, "field_value": value} for key, value in self.custom_fields.items()
            ],
        }
        if self.location_id:
            payload["locationId"] = self.location_id
        return payload


def build_crm_payload(lead: Lead, location_id: str = "") -> CRMContactPayload:
    """Map a validated catalog `Lead` onto a GoHighLevel-style contact payload."""
    stock_tag = "in-stock" if lead.in_stock else "out-of-stock"
    tags = [lead.category.lower().replace(" ", "-"), stock_tag]
    if lead.rating is not None:
        tags.append(f"rating-{lead.rating}")

    return CRMContactPayload(
        name=lead.title,
        company_name=f"{lead.category} Catalog",
        source=lead.source,
        tags=tags,
        custom_fields={
            "upc": lead.upc,
            "price_amount": lead.price_amount,
            "price_currency": lead.price_currency,
            "stock_quantity": lead.stock_quantity,
            "source_url": lead.source_url,
        },
        location_id=location_id,
    )

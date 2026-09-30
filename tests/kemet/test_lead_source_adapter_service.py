from types import SimpleNamespace

from app.services.lead_source_adapter_service import LeadSourceAdapterService


def test_google_sheet_rows_map_to_canonical_fields(monkeypatch):
    calls = {}

    def read_range(org, spreadsheet, range_name, token):
        calls["read"] = (org, spreadsheet, range_name, token)
        return {"range": range_name, "values": [
            ["Company", "E-mail", "Mobile", "Description", "Value"],
            [" Acme Egypt ", " SALES@ACME.EG ", "+20 100-200", "Interested in automation", "1500"],
        ]}

    monkeypatch.setattr(
        "app.services.lead_source_adapter_service.google_sheets_connector_service.read_range",
        read_range,
    )
    monkeypatch.setattr(
        "app.services.lead_source_adapter_service.google_sheets_connector_service.access_token",
        lambda *args, **kwargs: "opaque-token",
    )

    captured = {}
    monkeypatch.setattr(
        "app.services.lead_source_adapter_service.lead_discovery_service.ingest_many",
        lambda **kwargs: captured.update(kwargs) or {"success": True, "created": 1, "duplicates": 0},
    )

    result = LeadSourceAdapterService.ingest_google_sheets(
        tenant_id=7, user_id=11, spreadsheet_id="A" * 20, range_name="Leads!A:E"
    )

    assert result["adapter"] == "google_sheets"
    assert calls["read"][0:3] == (7, "A" * 20, "Leads!A:E")
    record = captured["records"][0]
    assert record["company_name"] == " Acme Egypt "
    assert record["email"] == " SALES@ACME.EG "
    assert record["phone"] == "+20 100-200"
    assert record["estimated_value"] == "1500"
    assert record["provenance"]["method"] == "official_connector_read_range"
    assert record["provenance"]["row"] == 2


def test_generic_adapter_preserves_source_boundary(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "app.services.lead_source_adapter_service.lead_discovery_service.ingest_many",
        lambda **kwargs: captured.update(kwargs) or {"success": True},
    )

    result = LeadSourceAdapterService.ingest_records(
        tenant_id=9,
        source="crm",
        records=[{"company_name": "Example", "email": "x@example.com"}],
    )

    assert result["adapter"] == "generic_permitted_source"
    assert captured["tenant_id"] == 9
    assert captured["source"] == "crm"

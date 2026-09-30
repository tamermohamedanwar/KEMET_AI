from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from app.services.google_sheets_connector_service import google_sheets_connector_service
from app.services.lead_discovery_service import lead_discovery_service


class LeadSourceAdapterService:
    """Read-only source adapters feeding the governed lead discovery boundary."""

    VERSION = "1.0"

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _headers(rows: list[list[Any]]) -> tuple[list[str], list[list[Any]]]:
        if not rows:
            return [], []
        headers = [str(value or "").strip().lower() for value in rows[0]]
        return headers, rows[1:]

    @classmethod
    def _map_row(cls, headers: list[str], row: list[Any]) -> dict[str, Any]:
        data = {headers[i]: row[i] for i in range(min(len(headers), len(row))) if headers[i]}
        aliases = {
            "company": "company_name", "companyname": "company_name",
            "business": "company_name", "e-mail": "email",
            "mobile": "phone", "telephone": "phone",
            "notes": "message", "description": "message",
            "value": "estimated_value", "estimatedvalue": "estimated_value",
        }
        normalized = dict(data)
        for source, target in aliases.items():
            if source in data and target not in normalized:
                normalized[target] = data[source]
        return normalized

    @classmethod
    def ingest_google_sheets(cls, *, tenant_id: int, user_id: int,
                             spreadsheet_id: str, range_name: str,
                             max_records: int = 1000) -> dict[str, Any]:
        token = google_sheets_connector_service.access_token(int(tenant_id), int(user_id), write=False)
        payload = google_sheets_connector_service.read_range(
            int(tenant_id), spreadsheet_id, range_name, token
        )
        values = payload.get("values") or []
        headers, rows = cls._headers(values)
        if not headers:
            return {"success": True, "source": "google_sheets", "created": 0,
                    "duplicates": 0, "rows_read": 0, "items": []}
        records = []
        for row_number, row in enumerate(rows[:max_records], start=2):
            record = cls._map_row(headers, row)
            record["provenance"] = {
                "source": "google_sheets",
                "method": "official_connector_read_range",
                "spreadsheet_id": spreadsheet_id,
                "range": range_name,
                "row": row_number,
                "fetched_at": cls._now(),
                "source_payload": {"range": payload.get("range", range_name)},
            }
            records.append(record)
        result = lead_discovery_service.ingest_many(
            tenant_id=int(tenant_id), records=records, source="google_sheets"
        )
        result.update({"adapter": "google_sheets", "adapter_version": cls.VERSION,
                       "rows_read": len(rows), "external_execution": False})
        return result

    @classmethod
    def ingest_records(cls, *, tenant_id: int, source: str,
                       records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
        materialized = [dict(record) for record in records]
        result = lead_discovery_service.ingest_many(
            tenant_id=int(tenant_id), records=materialized, source=source
        )
        result.update({"adapter": "generic_permitted_source", "adapter_version": cls.VERSION})
        return result


lead_source_adapter_service = LeadSourceAdapterService()

from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from app.services.document_ingestion import ingest_saved_file

FIELDS = (
    "document_id", "document_type", "document_date", "invoice_number",
    "supplier_name", "customer_name", "currency", "subtotal", "tax",
    "total", "payment_status", "line_items", "source_file", "source_page",
    "source_hash", "extraction_status", "validation_status", "review_status",
    "confidence",
)
REQUIRED = ("document_date", "invoice_number", "supplier_name", "total")
CRITICAL_FIELDS = ("total", "invoice_number", "document_date", "currency")
MONEY_FIELDS = ("subtotal", "tax", "total")


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _money(value: Any) -> str:
    text = _clean(value).replace(",", "")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    return match.group(0) if match else ""


def _field(text: str, *labels: str) -> tuple[str, int | None]:
    lines = text.splitlines()
    for label in labels:
        pattern = re.compile(rf"^\s*{re.escape(label)}\s*[:#-]\s*(.+?)\s*$", re.I)
        for number, line in enumerate(lines, 1):
            match = pattern.match(line)
            if match:
                return _clean(match.group(1)), number
    return "", None


def _normalize_date(value: str) -> str:
    value = _clean(value)
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%m-%d-%Y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    return value


def _field_confidence(value: str, source_line: int | None) -> float:
    if not value:
        return 0.0
    return 0.95 if source_line is not None else 0.70


def extract_invoice_fields(text: str, source_file: str, source_hash: str = "") -> dict[str, Any]:
    source = Path(source_file).name
    values: dict[str, str] = {}
    lines: dict[str, int | None] = {}
    labels = {
        "document_date": ("Date", "Invoice Date"),
        "invoice_number": ("Invoice Number", "Invoice No", "Number"),
        "supplier_name": ("Supplier", "Vendor"),
        "customer_name": ("Customer", "Bill To"),
        "currency": ("Currency",),
        "subtotal": ("Subtotal",),
        "tax": ("Tax", "VAT"),
        "total": ("Total", "Amount Due"),
        "payment_status": ("Payment Status", "Status"),
    }
    for field, field_labels in labels.items():
        value, line = _field(text, *field_labels)
        values[field] = value
        lines[field] = line

    values["document_date"] = _normalize_date(values["document_date"])
    for field in MONEY_FIELDS:
        values[field] = _money(values[field])

    # Deterministically capture repeated labeled invoice line items.
    source_lines = text.splitlines()
    item_re = re.compile(r"^\s*(Item|Description|Product|Service)\s*[:#-]\s*(.+?)\s*$", re.I)
    qty_re = re.compile(r"^\s*(Quantity|Qty)\s*[:#-]\s*(.+?)\s*$", re.I)
    price_re = re.compile(r"^\s*(Unit Price|Price)\s*[:#-]\s*(.+?)\s*$", re.I)
    line_items: list[dict[str, str]] = []
    pending_item = ""
    pending_qty = ""
    pending_price = ""
    for line in source_lines:
        match = item_re.match(line)
        if match:
            if pending_item:
                line_items.append({"description": pending_item, "quantity": _money(pending_qty), "unit_price": _money(pending_price)})
            pending_item, pending_qty, pending_price = _clean(match.group(2)), "", ""
            continue
        match = qty_re.match(line)
        if match and pending_item:
            pending_qty = _clean(match.group(2))
            continue
        match = price_re.match(line)
        if match and pending_item:
            pending_price = _clean(match.group(2))
    if pending_item:
        line_items.append({"description": pending_item, "quantity": _money(pending_qty), "unit_price": _money(pending_price)})
    if line_items:
        values["line_items"] = json.dumps(line_items, ensure_ascii=False)

    currency_match = re.search(r"(?i)(EGP|USD|EUR|GBP|SAR|AED|KWD|QAR|JOD|BHD|OMR|\\$|€|£)", text)
    if not values["currency"] and currency_match:
        token = currency_match.group(1).upper()
        symbol_map = {"$": "USD", "€": "EUR", "£": "GBP"}
        values["currency"] = symbol_map.get(token, token)
        lines["currency"] = next((n for n, line in enumerate(text.splitlines(), 1) if re.search(rf"(?i){re.escape(token)}", line)), None)

    confidence_map = {
        field: round(_field_confidence(values[field], lines[field]), 2)
        for field in labels
    }
    populated = [v for v in confidence_map.values() if v > 0]
    overall = round(sum(populated) / len(populated), 2) if populated else 0.0
    return {
        "document_id": source_hash[:16] if source_hash else hashlib.sha256(source.encode()).hexdigest()[:16],
        "document_type": "invoice",
        **values,
        "line_items": values.get("line_items", ""),
        "source_file": source,
        "source_page": "1",
        "source_hash": source_hash,
        "extraction_status": "EXTRACTED" if values["invoice_number"] or values["total"] else "FAILED",
        "validation_status": "NEEDS_REVIEW",
        "review_status": "PENDING",
        "confidence": overall,
        "field_confidence": confidence_map,
        "field_sources": {field: {"source_file": source, "source_line": lines[field]} for field in labels if lines[field]},
    }


def _critical_confidence(record: dict[str, Any]) -> bool:
    confidence = record.get("field_confidence", {})
    return all(float(confidence.get(field, 0.0)) >= 0.80 for field in CRITICAL_FIELDS if field in record)


def validate_record(record: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    for field in REQUIRED:
        if not _clean(record.get(field)):
            errors.append(f"missing:{field}")
    for field in MONEY_FIELDS:
        value = _clean(record.get(field))
        if value and not re.fullmatch(r"-?\d+(?:\.\d+)?", value):
            errors.append(f"invalid_number:{field}")

    subtotal = record.get("subtotal")
    tax = record.get("tax")
    total = record.get("total")
    if subtotal and tax and total:
        try:
            if abs(float(subtotal) + float(tax) - float(total)) > 0.02:
                errors.append("total_mismatch")
        except ValueError:
            errors.append("invalid_arithmetic_inputs")

    line_items_raw = record.get("line_items")
    if subtotal and line_items_raw:
        try:
            line_items = json.loads(line_items_raw)
            line_sum = sum(float(item.get("quantity", 0)) * float(item.get("unit_price", 0)) for item in line_items)
            if abs(line_sum - float(subtotal)) > 0.02:
                errors.append("line_items_subtotal_mismatch")
        except (TypeError, ValueError, json.JSONDecodeError):
            errors.append("invalid_line_items_arithmetic")

    if not _critical_confidence(record):
        errors.append("low_critical_field_confidence")

    status = "VALID" if not errors else "NEEDS_REVIEW"
    result = dict(record)
    result["validation_status"] = status
    result["review_status"] = "NOT_REQUIRED" if status == "VALID" else "PENDING"
    return {"record": result, "errors": errors}



def build_quality_scorecard(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary", {})
    extracted = int(summary.get("records_extracted", 0) or 0)
    valid = int(summary.get("valid_records", 0) or 0)
    review = int(summary.get("needs_review", 0) or 0)
    duplicates = int(summary.get("duplicates_detected", 0) or 0)
    failures = int(summary.get("processing_errors", 0) or 0)
    checks = extracted or 1
    completeness = round(max(0.0, 1.0 - (review / checks)) * 100, 1)
    validation = round((valid / checks) * 100, 1)
    exceptions = len(payload.get("errors", []))
    integrity = round(max(0.0, 1.0 - ((duplicates + failures + exceptions) / max(1, extracted))) * 100, 1)
    overall = round((completeness * 0.35) + (validation * 0.40) + (integrity * 0.25), 1)
    return {
        "overall_quality_score": overall,
        "dimensions": {"completeness_pct": completeness, "validation_pass_pct": validation, "integrity_pct": integrity},
        "interpretation": "Ready for delivery" if overall >= 95 and review == 0 and failures == 0 else "Review required" if review or failures else "Quality checks completed",
        "method": "deterministic pipeline metrics; confidence is heuristic and not model accuracy",
    }

def build_exception_center(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for item in payload.get("errors", []):
        rows.append({
            "source_file": item.get("source_file", ""),
            "severity": "HIGH" if any(str(e).startswith(("missing:", "total_mismatch")) for e in item.get("errors", [])) else "MEDIUM",
            "issues": list(item.get("errors", [])),
            "action": "Human review required",
        })
    for item in payload.get("failures", []):
        rows.append({"source_file": item.get("source_file", ""), "severity": "CRITICAL", "issues": [item.get("error", "processing_error")], "action": "Re-upload or inspect source file"})
    return rows

def build_delivery_manifest(payload: dict[str, Any], client_rules: dict[str, Any] | None = None) -> dict[str, Any]:
    rules = client_rules or {}
    return {
        "product": "Kemet Document Intelligence",
        "delivery_version": "V3",
        "status": "REVIEW_REQUIRED" if payload.get("summary", {}).get("needs_review", 0) or payload.get("failures") else "READY",
        "input": {"files_received": payload.get("summary", {}).get("files_received", 0), "sha256_evidence_count": len(payload.get("evidence", {}).get("input_sha256", []))},
        "coverage": {"document_types_supported_in_this_run": sorted({r.get("document_type", "") for r in payload.get("records", []) if r.get("document_type")}), "records_extracted": payload.get("summary", {}).get("records_extracted", 0)},
        "quality": build_quality_scorecard(payload),
        "exceptions": build_exception_center(payload),
        "rules": rules,
        "human_review_authoritative": True,
        "honesty": "No 100% accuracy claim; confidence is heuristic unless a validated provider/model contract is explicitly attached.",
    }

def export_delivery_package(payload: dict[str, Any], directory: str, client_rules: dict[str, Any] | None = None) -> dict[str, str]:
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    export_csv(payload.get("records", []), str(target / "clean.csv"))
    export_xlsx(payload.get("records", []), str(target / "clean.xlsx"))
    export_json(payload, str(target / "validation_report.json"))
    export_json(build_delivery_manifest(payload, client_rules), str(target / "delivery_manifest.json"))
    return {name: str(target / name) for name in ("clean.csv", "clean.xlsx", "validation_report.json", "delivery_manifest.json")}

def process_records(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    cleaned: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    seen_hashes: set[str] = set()
    seen_business_keys: set[tuple[str, str]] = set()
    duplicates = 0
    input_count = 0
    for raw in records:
        input_count += 1
        record = dict(raw)
        for key in FIELDS:
            record.setdefault(key, "")
        source_hash = _clean(record.get("source_hash"))
        business_key = (_clean(record.get("supplier_name")).lower(), _clean(record.get("invoice_number")).lower())
        duplicate_reason = None
        if source_hash and source_hash in seen_hashes:
            duplicate_reason = "duplicate_source_hash"
        elif all(business_key) and business_key in seen_business_keys:
            duplicate_reason = "duplicate_invoice_supplier"
        if duplicate_reason:
            duplicates += 1
            errors.append({"source_file": record.get("source_file"), "errors": [duplicate_reason]})
            continue
        if source_hash:
            seen_hashes.add(source_hash)
        if all(business_key):
            seen_business_keys.add(business_key)
        checked = validate_record(record)
        cleaned.append(checked["record"])
        if checked["errors"]:
            errors.append({"source_file": record.get("source_file"), "errors": checked["errors"]})
    return {
        "records": cleaned,
        "errors": errors,
        "summary": {
            "files_received": input_count,
            "records_extracted": len(cleaned),
            "valid_records": sum(r["validation_status"] == "VALID" for r in cleaned),
            "needs_review": sum(r["validation_status"] == "NEEDS_REVIEW" for r in cleaned),
            "duplicates_detected": duplicates,
            "validation_failures": sum(bool(e.get("errors")) for e in errors),
        },
    }


def export_csv(records: list[dict[str, Any]], path: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    export_fields = list(FIELDS)
    with target.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=export_fields)
        writer.writeheader()
        for record in records:
            writer.writerow({field: record.get(field, "") for field in export_fields})


def export_xlsx(records: list[dict[str, Any]], path: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    data = workbook.active
    data.title = "Data"
    data.append(list(FIELDS))
    for record in records:
        data.append([record.get(field, "") for field in FIELDS])
    header_fill = PatternFill("solid", fgColor="17324D")
    header_font = Font(color="FFFFFF", bold=True)
    thin = Side(style="thin", color="D9E2EC")
    for cell in data[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = Border(bottom=thin)
    data.freeze_panes = "A2"
    data.auto_filter.ref = data.dimensions
    for col_idx, name in enumerate(FIELDS, 1):
        data.column_dimensions[get_column_letter(col_idx)].width = min(34, max(12, len(name) + 2))
    review = workbook.create_sheet("Review")
    review.append(["Source File", "Validation Status", "Review Status", "Confidence", "Action"])
    for record in records:
        if record.get("validation_status") != "VALID":
            review.append([record.get("source_file", ""), record.get("validation_status", ""), record.get("review_status", ""), record.get("confidence", ""), "Human review required"])
    summary = workbook.create_sheet("Summary")
    summary.append(["Metric", "Value"])
    summary.append(["records", len(records)])
    summary.append(["valid", sum(r.get("validation_status") == "VALID" for r in records)])
    summary.append(["needs_review", sum(r.get("validation_status") == "NEEDS_REVIEW" for r in records)])
    summary.append(["quality_note", "Confidence is heuristic; human review is authoritative."])
    for cell in summary[1]:
        cell.fill = header_fill
        cell.font = header_font
    summary.column_dimensions["A"].width = 28
    summary.column_dimensions["B"].width = 70
    workbook.save(target)


def export_json(payload: dict[str, Any], path: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def process_files(paths: Iterable[str]) -> dict[str, Any]:
    paths = list(paths)
    records: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    source_hashes: list[str] = []
    for path in paths:
        try:
            file_path = Path(path)
            source_digest = hashlib.sha256(file_path.read_bytes()).hexdigest()
            source_hashes.append(source_digest)
            ingested = ingest_saved_file(path, file_path.name)
            records.append(extract_invoice_fields(ingested["text"], ingested["filename"], source_digest))
        except Exception as exc:
            failures.append({"source_file": Path(path).name, "error": str(exc)})
    result = process_records(records)
    result["failures"] = failures
    result["summary"]["files_received"] = len(list(paths)) if not isinstance(paths, list) else len(paths)
    result["summary"]["processing_errors"] = len(failures)
    result["evidence"] = {
        "pipeline": "INGEST -> CLASSIFY -> EXTRACT -> NORMALIZE -> VALIDATE -> CONFIDENCE -> DUPLICATE -> REVIEW -> EXPORT",
        "input_sha256": source_hashes,
        "human_review_authoritative": True,
        "confidence_is_heuristic": True,
    }
    return result


def classify_document_type(text: str, filename: str = "") -> dict[str, Any]:
    """Deterministic document classification; invoice is currently the supported type."""
    sample = f"{filename}\
{text}".lower()
    invoice_markers = ("invoice number", "invoice no", "subtotal", "amount due", "vat")
    if any(marker in sample for marker in invoice_markers):
        return {"document_type": "invoice", "classification_status": "SUPPORTED", "confidence": 0.95}
    return {"document_type": "unknown", "classification_status": "UNSUPPORTED", "confidence": 0.50}


def build_intake_manifest(paths: Iterable[str], classifications: list[dict[str, Any]], failures: list[dict[str, str]]) -> dict[str, Any]:
    files = list(paths)
    supported = sum(c.get("classification_status") == "SUPPORTED" for c in classifications)
    return {
        "manifest_version": "V4",
        "files_received": len(files),
        "supported_files": supported,
        "unsupported_files": len(classifications) - supported,
        "processing_failures": len(failures),
        "coverage": {"invoice": supported, "unknown": len(classifications) - supported},
        "status": "READY" if supported and not failures else "REVIEW_REQUIRED" if supported else "BLOCKED",
        "honesty": "Coverage is limited to the document types explicitly supported by this run.",
    }


def build_field_evidence(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for record in records:
        sources = record.get("field_sources", {})
        confidence = record.get("field_confidence", {})
        for field in FIELDS:
            if field in ("field_confidence", "field_sources"):
                continue
            if not record.get(field) and field not in sources:
                continue
            source = sources.get(field, {})
            rows.append({
                "document_id": record.get("document_id", ""),
                "source_file": record.get("source_file", ""),
                "field": field,
                "value": record.get(field, ""),
                "source_page": source.get("source_page", record.get("source_page", "1")),
                "source_line": source.get("source_line"),
                "confidence": confidence.get(field, record.get("confidence", 0.0)),
                "validation_status": record.get("validation_status", ""),
            })
    return rows


def apply_client_rules(records: list[dict[str, Any]], client_rules: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    rules = client_rules or {}
    required = tuple(rules.get("required_columns", []))
    currencies = {str(x).upper() for x in rules.get("allowed_currencies", [])}
    min_total = rules.get("min_total")
    max_total = rules.get("max_total")
    for record in records:
        issues = list(record.get("risk_issues", []))
        for field in required:
            if not _clean(record.get(field)):
                issues.append({"code": "client_required_missing", "field": field, "severity": "HIGH"})
        if currencies and _clean(record.get("currency")).upper() not in currencies:
            issues.append({"code": "client_currency_policy", "field": "currency", "severity": "HIGH"})
        try:
            total = float(record.get("total")) if record.get("total") != "" else None
            if total is not None and min_total is not None and total < float(min_total):
                issues.append({"code": "client_min_total", "field": "total", "severity": "MEDIUM"})
            if total is not None and max_total is not None and total > float(max_total):
                issues.append({"code": "client_max_total", "field": "total", "severity": "MEDIUM"})
        except (TypeError, ValueError):
            pass
        if issues:
            record["risk_issues"] = issues
            record["validation_status"] = "NEEDS_REVIEW"
            record["review_status"] = "PENDING"
    return records


def build_risk_center(records: list[dict[str, Any]], errors: list[dict[str, Any]], failures: list[dict[str, str]]) -> list[dict[str, Any]]:
    risks = []
    for record in records:
        for issue in record.get("risk_issues", []):
            risks.append({"source_file": record.get("source_file", ""), "document_id": record.get("document_id", ""), **issue, "action": "Human review required"})
    for item in errors:
        for issue in item.get("errors", []):
            risks.append({"source_file": item.get("source_file", ""), "document_id": "", "code": issue, "severity": "HIGH", "action": "Human review required"})
    for item in failures:
        risks.append({"source_file": item.get("source_file", ""), "document_id": "", "code": "processing_error", "severity": "CRITICAL", "action": "Re-upload or inspect source file"})
    return risks


def build_readiness_gate(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary", {})
    if payload.get("failures") or payload.get("intake", {}).get("status") == "BLOCKED":
        return {"status": "BLOCKED", "reasons": ["processing_failure_or_unsupported_input"]}
    if summary.get("needs_review", 0) or payload.get("risk_center"):
        return {"status": "REVIEW_REQUIRED", "reasons": sorted({r.get("code", "review_required") for r in payload.get("risk_center", [])})}
    return {"status": "READY", "reasons": []}


def build_business_insights(records: list[dict[str, Any]], risk_center: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    risk_center = risk_center or []
    totals = [float(r["total"]) for r in records if _clean(r.get("total")) and re.fullmatch(r"-?\d+(?:\.\d+)?", _clean(r.get("total")))]
    suppliers = sorted({_clean(r.get("supplier_name")) for r in records if _clean(r.get("supplier_name"))})
    customers = sorted({_clean(r.get("customer_name")) for r in records if _clean(r.get("customer_name"))})
    currencies = sorted({_clean(r.get("currency")).upper() for r in records if _clean(r.get("currency"))})
    unpaid = sum(_clean(r.get("payment_status")).lower() in {"unpaid", "pending", "overdue"} for r in records)
    high_risk = sum(str(r.get("severity", "")).upper() in {"HIGH", "CRITICAL"} for r in risk_center)
    return {
        "record_count": len(records),
        "total_value": round(sum(totals), 2),
        "average_value": round(sum(totals) / len(totals), 2) if totals else 0.0,
        "supplier_count": len(suppliers),
        "customer_count": len(customers),
        "currencies": currencies,
        "unpaid_or_pending_count": unpaid,
        "high_or_critical_risk_count": high_risk,
        "duplicate_count": sum(r.get("code") in {"duplicate_source_hash", "duplicate_invoice_supplier"} for r in risk_center),
        "top_supplier_by_value": max(
            ((s, round(sum(float(r.get("total") or 0) for r in records if _clean(r.get("supplier_name")) == s), 2)) for s in suppliers),
            key=lambda item: item[1], default=("", 0.0),
        ),
    }


def build_action_plan(insights: dict[str, Any], risk_center: list[dict[str, Any]] | None = None) -> list[dict[str, str]]:
    risk_center = risk_center or []
    actions: list[dict[str, str]] = []
    if any(str(r.get("severity", "")).upper() == "CRITICAL" for r in risk_center):
        actions.append({"priority": "P0", "action": "Resolve critical processing/input failures before delivery.", "reason": "Critical risks can block reliable processing."})
    if insights.get("high_or_critical_risk_count", 0):
        actions.append({"priority": "P1", "action": "Review high-risk records and confirm source documents.", "reason": f"{insights['high_or_critical_risk_count']} high/critical risk items detected."})
    if insights.get("duplicate_count", 0):
        actions.append({"priority": "P1", "action": "Confirm duplicate invoices before posting or payment.", "reason": f"{insights['duplicate_count']} duplicate candidates detected."})
    if insights.get("unpaid_or_pending_count", 0):
        actions.append({"priority": "P1", "action": "Review unpaid or pending invoices for follow-up.", "reason": f"{insights['unpaid_or_pending_count']} unpaid/pending records detected."})
    if not actions:
        actions.append({"priority": "P2", "action": "Proceed with normal human review and delivery.", "reason": "No priority exceptions were detected."})
    return actions


def build_client_report(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary", {})
    gate = payload.get("readiness_gate", {})
    insights = build_business_insights(payload.get("records", []), payload.get("risk_center", []))
    action_plan = build_action_plan(insights, payload.get("risk_center", []))
    return {
        "report_version": "V4",
        "executive_summary": {
            "files_received": summary.get("files_received", 0),
            "records_extracted": summary.get("records_extracted", 0),
            "valid_records": summary.get("valid_records", 0),
            "records_needing_review": summary.get("needs_review", 0),
            "duplicates_detected": summary.get("duplicates_detected", 0),
        },
        "quality": build_quality_scorecard(payload),
        "readiness": gate,
        "risk_count": len(payload.get("risk_center", [])),
        "evidence_count": len(payload.get("field_evidence", [])),
        "business_insights": insights,
        "action_plan": action_plan,
        "human_review_authoritative": True,
        "no_accuracy_guarantee": True,
    }


def export_v4_xlsx(payload: dict[str, Any], path: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    header_fill = PatternFill("solid", fgColor="17324D")
    header_font = Font(color="FFFFFF", bold=True)
    thin = Side(style="thin", color="D9E2EC")

    def sheet(name: str, headers: list[str], rows: list[list[Any]]) -> Any:
        ws = workbook.create_sheet(name)
        ws.append(headers)
        for row in rows:
            ws.append(row)
        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = Border(bottom=thin)
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        for idx, header in enumerate(headers, 1):
            ws.column_dimensions[get_column_letter(idx)].width = min(48, max(14, len(header) + 3))
        return ws

    workbook.remove(workbook.active)
    q = payload.get("quality", {})
    summary = payload.get("summary", {})
    sheet("Executive Summary", ["Metric", "Value"], [
        ["Readiness", payload.get("readiness_gate", {}).get("status", "")],
        ["Quality Score", q.get("overall_quality_score", "")],
        ["Files Received", summary.get("files_received", 0)],
        ["Records Extracted", summary.get("records_extracted", 0)],
        ["Valid Records", summary.get("valid_records", 0)],
        ["Needs Review", summary.get("needs_review", 0)],
        ["Duplicates", summary.get("duplicates_detected", 0)],
        ["Risk Items", len(payload.get("risk_center", []))],
        ["Evidence Rows", len(payload.get("field_evidence", []))],
    ])
    sheet("Clean Data", list(FIELDS), [[r.get(f, "") for f in FIELDS] for r in payload.get("records", [])])
    insights = payload.get("client_report", {}).get("business_insights", {})
    sheet("Business Insights", ["Metric", "Value"], [[k, json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list, tuple)) else v] for k, v in insights.items()])
    sheet("Action Plan", ["Priority", "Action", "Reason"], [[r.get("priority", ""), r.get("action", ""), r.get("reason", "")] for r in payload.get("client_report", {}).get("action_plan", [])])
    sheet("Review Queue", ["Source File", "Document ID", "Code", "Severity", "Action"], [[r.get("source_file", ""), r.get("document_id", ""), r.get("code", ""), r.get("severity", ""), r.get("action", "")] for r in payload.get("risk_center", [])])
    evidence = payload.get("field_evidence", [])
    sheet("Evidence", ["Document ID", "Source File", "Field", "Value", "Page", "Line", "Confidence", "Validation"], [[r.get(k, "") for k in ("document_id", "source_file", "field", "value", "source_page", "source_line", "confidence", "validation_status")] for r in evidence])
    rules = payload.get("rules", {})
    sheet("Rules", ["Rule", "Value"], [[k, json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v] for k, v in rules.items()] + [["Human Review", "Authoritative"], ["Accuracy Claim", "No 100% guarantee"]])
    workbook.save(target)


def process_files_v4(paths: Iterable[str], client_rules: dict[str, Any] | None = None) -> dict[str, Any]:
    paths = list(paths)
    records: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    classifications: list[dict[str, Any]] = []
    source_hashes: list[str] = []
    for path in paths:
        try:
            file_path = Path(path)
            source_digest = hashlib.sha256(file_path.read_bytes()).hexdigest()
            source_hashes.append(source_digest)
            ingested = ingest_saved_file(path, file_path.name)
            classification = classify_document_type(ingested["text"], file_path.name)
            classifications.append({"source_file": file_path.name, **classification})
            if classification["classification_status"] != "SUPPORTED":
                failures.append({"source_file": file_path.name, "error": "unsupported_document_type"})
                continue
            records.append(extract_invoice_fields(ingested["text"], ingested["filename"], source_digest))
        except Exception as exc:
            failures.append({"source_file": Path(path).name, "error": str(exc)})
    payload = process_records(records)
    payload["summary"]["files_received"] = len(paths)
    payload["summary"]["processing_errors"] = len(failures)
    payload["failures"] = failures
    payload["records"] = apply_client_rules(payload["records"], client_rules)
    payload["summary"]["valid_records"] = sum(r.get("validation_status") == "VALID" for r in payload["records"])
    payload["summary"]["needs_review"] = sum(r.get("validation_status") == "NEEDS_REVIEW" for r in payload["records"])
    payload["intake"] = build_intake_manifest(paths, classifications, failures)
    payload["rules"] = client_rules or {}
    payload["field_evidence"] = build_field_evidence(payload["records"])
    payload["risk_center"] = build_risk_center(payload["records"], payload.get("errors", []), failures)
    payload["quality"] = build_quality_scorecard(payload)
    payload["readiness_gate"] = build_readiness_gate(payload)
    payload["client_report"] = build_client_report(payload)
    payload["evidence"] = {
        "pipeline": "SMART INTAKE -> CLASSIFY -> EXTRACT -> EVIDENCE -> NORMALIZE -> VALIDATE -> RISK -> REVIEW -> QUALITY -> DELIVERY",
        "input_sha256": source_hashes,
        "human_review_authoritative": True,
        "confidence_is_heuristic": True,
    }
    return payload


def export_delivery_package_v4(payload: dict[str, Any], directory: str) -> dict[str, str]:
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    export_csv(payload.get("records", []), str(target / "clean.csv"))
    export_v4_xlsx(payload, str(target / "clean.xlsx"))
    export_json(payload.get("client_report", {}), str(target / "client_report.json"))
    export_json(payload.get("intake", {}), str(target / "intake_manifest.json"))
    export_json(payload, str(target / "validation_report.json"))
    return {name: str(target / name) for name in ("clean.csv", "clean.xlsx", "client_report.json", "intake_manifest.json", "validation_report.json")}

# Kemet Document Automation — Synthetic Portfolio Demo

**Synthetic demo only — not customer data.**

## Input
A sample invoice/document containing invoice number, date, supplier, customer, currency, subtotal, tax, total and payment status.

## Processing
INGEST → CLASSIFY → EXTRACT → NORMALIZE → VALIDATE → CONFIDENCE → DUPLICATE CHECK → HUMAN REVIEW → EXPORT

## Output
- clean.xlsx — structured workbook with Data, Review and Summary sheets
- clean.csv — machine-readable structured data
- validation_report.json — machine-readable processing/evidence report

## Quality behavior
- Missing critical fields are marked NEEDS_REVIEW.
- Arithmetic mismatches are marked NEEDS_REVIEW.
- Duplicate source hashes and invoice/supplier combinations are reported.
- Field source line references are retained where available.
- SHA-256 source evidence is retained.
- Confidence in the current local extractor is explicitly heuristic, not a claim of model accuracy.

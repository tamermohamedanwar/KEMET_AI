"""Fail-closed promotion gate for Kemet security hypotheses."""
from __future__ import annotations

from typing import Any

REQUIRED_EVIDENCE = ("source_evidence", "focused_test", "regression_proof")


def validate_hypothesis(hypothesis: dict[str, Any]) -> dict[str, Any]:
    missing = [key for key in REQUIRED_EVIDENCE if hypothesis.get(key) is not True]
    evidence_digest = hypothesis.get("evidence_digest")
    source_digest = hypothesis.get("source_digest")
    if not evidence_digest:
        missing.append("evidence_digest")
    if not source_digest:
        missing.append("source_digest")
    if hypothesis.get("execution_authority") is not False:
        missing.append("execution_authority_false")
    if hypothesis.get("network") is not False:
        missing.append("network_false")
    promotable = not missing
    return {
        "schema": "kemet.security_validation_gate.v1",
        "hypothesis_id": hypothesis.get("hypothesis_id"),
        "status": "PROMOTABLE_FINDING" if promotable else "HYPOTHESIS_ONLY",
        "promotable": promotable,
        "missing": missing,
        "human_review_required": True,
    }


def validate_batch(hypotheses: list[dict[str, Any]]) -> dict[str, Any]:
    results = [validate_hypothesis(item) for item in hypotheses]
    return {
        "schema": "kemet.security_validation_gate.v1",
        "promotable_count": sum(item["promotable"] for item in results),
        "hypothesis_only_count": sum(not item["promotable"] for item in results),
        "results": results,
    }

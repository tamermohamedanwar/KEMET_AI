from pathlib import Path

from app.services.ml_decision_review_service import MLDecisionReviewService


ROOT = Path(__file__).resolve().parents[2]


def test_ml_decision_review_route_is_tenant_bound_and_read_only():
    route = (ROOT / "app" / "routes" / "bos_command.py").read_text(encoding="utf-8")
    service = (ROOT / "app" / "services" / "ml_decision_review_service.py").read_text(encoding="utf-8")
    assert '@bos_command_bp.get("/ml-decision-review")' in route
    assert 'getattr(current_user, "organization_id", None)' in route
    assert '"review_only": True' in service
    assert '"execution_authority": "none"' in service
    assert '"human_review_required": True' in service


def test_ml_decision_review_preserves_control_evidence_chain():
    text = (ROOT / "app" / "services" / "ml_decision_review_service.py").read_text(encoding="utf-8")
    for stage in ("decision", "approval", "execution", "evidence", "outcome", "learning"):
        assert f'"stage": "{stage}"' in text
    assert '"decision_status": "review_required"' in text
    assert '"approval_status": "pending"' in text
    assert '"execution_status": "not_executed"' in text
    assert '"learning_status": "advisory"' in text


def test_ml_decision_review_fails_closed_without_authorized_dataset():
    text = (ROOT / "app" / "services" / "ml_decision_review_service.py").read_text(encoding="utf-8")
    assert '"authorized_dataset_present": False' in text
    assert '"benchmark_status": "blocked_until_authorized_dataset"' in text
    assert '"evidence_status": "not_available_until_authorized_dataset"' in text
    assert '"evidence_completion_status": "not_available_until_authorized_dataset"' in text
    assert '"leakage_evidence_status": "not_available_until_authorized_dataset"' in text
    assert '"generalization_evidence_status": "not_available_until_authorized_dataset"' in text
    assert '"error_analysis_status": "not_available_until_authorized_dataset"' in text
    assert '"provenance_binding_status": "not_available_until_authorized_dataset"' in text
    assert '"outcome", "status": "not_observed"' in text


def test_command_center_approval_inbox_surfaces_ml_review_without_execute_controls():
    text = (ROOT / "app" / "templates" / "command_center.html").read_text(encoding="utf-8")
    assert 'loadMLDecisionReview' in text
    assert '/api/bos/ml-decision-review' in text
    assert 'const marker="mlApprovalDecisionReview"' in text
    assert 'REVIEW ONLY' in text
    assert 'No approval or execution is created by this surface.' in text
    assert 'Evidence completion:' in text
    assert 'Leakage:' in text
    assert 'Generalization:' in text
    assert 'Error analysis:' in text
    assert 'Provenance:' in text


def test_ml_decision_review_service_contract_is_fail_closed():
    review = MLDecisionReviewService.build_empty_review(organization_id=7)
    assert review["schema"] == "kemet.ml.decision_review.v1"
    assert review["organization_id"] == 7
    assert review["authorized_dataset_present"] is False
    assert review["execution_authority"] == "none"
    assert review["review_only"] is True
    assert review["benchmark_status"] == "blocked_until_authorized_dataset"
    assert [x["stage"] for x in review["control_evidence_chain"]] == [
        "decision", "approval", "execution", "evidence", "outcome", "learning"
    ]


def test_ml_decision_review_service_rejects_invalid_tenant():
    try:
        MLDecisionReviewService.build_empty_review(organization_id=0)
    except ValueError as exc:
        assert str(exc) == "organization_required"
    else:
        raise AssertionError("invalid organization must fail closed")

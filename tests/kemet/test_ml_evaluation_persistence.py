import hashlib
import pytest

from app import create_app, db
from app.services.ml_dataset_authorization_service import MLDatasetAuthorizationService
from app.services.ml_evaluation_capability import ml_evaluation_capability
from app.models.ml_evaluation_record import MLEvaluationRecord
from app.services.ml_evaluation_persistence_service import ml_evaluation_persistence_service


def _authorization(org=1, digest=None):
    return MLDatasetAuthorizationService().authorize(
        organization_id=org, dataset_id="ds-persist", owner="owner",
        purpose="evaluation", allowed_use="evaluation", sensitivity_classification="internal",
        source="authorized_source", dataset_sha256=digest or hashlib.sha256(b"persist").hexdigest(),
        authorization_reference="AUTH-PERSIST", human_review_status="approved",
    )


def _complete(authorization, task="eval-persist"):
    digest = authorization["dataset_sha256"]
    return ml_evaluation_capability.persist_complete_record(
        authorization_record=authorization,
        organization_id=authorization["organization_id"], task_id=task, evaluation_key=task,
        dataset_digest=digest, split_strategy="train_validation_test",
        baseline={"metric": "f1", "value": 0.4}, model_results=[{"model": "svm", "f1": 0.7}],
        leakage_check="passed", generalization={"gap": 0.05},
        evidence={
            "leakage_evidence": {"status": "passed"},
            "generalization_evidence": {"validation_strategy": "train_validation_test"},
            "error_analysis": {"out_of_sample": {"summary": "reviewed"}},
            "provenance": {"dataset_digest": digest, "source": "authorized"},
        },
    )


def test_persists_complete_evaluation_with_tenant_and_digest_bindings():
    app = create_app()
    with app.app_context():
        db.create_all()
        db.session.query(MLEvaluationRecord).filter_by(organization_id=1, evaluation_key="eval-persist").delete()
        db.session.commit()
        auth = _authorization()
        result = _complete(auth)
        row = ml_evaluation_persistence_service.get_for_organization(organization_id=1, evaluation_key="eval-persist")
        assert result["persistence"]["stored"] is True
        assert row is not None
        assert row.dataset_sha256 == auth["dataset_sha256"]
        assert row.authorization_reference == auth["authorization_reference"]
        assert row.execution_status == "not_executed"
        assert row.approval_status == "pending"


def test_persistence_is_idempotent_for_same_evaluation_digest():
    app = create_app()
    with app.app_context():
        db.create_all()
        db.session.query(MLEvaluationRecord).filter_by(organization_id=1, evaluation_key="eval-persist").delete()
        db.session.commit()
        auth = _authorization()
        first = _complete(auth)
        second = _complete(auth)
        assert first["persistence"]["record_id"] == second["persistence"]["record_id"]
        assert ml_evaluation_persistence_service.get_for_organization(organization_id=1, evaluation_key="eval-persist").id == first["persistence"]["record_id"]


def test_persistence_rejects_cross_tenant_authorization():
    app = create_app()
    with app.app_context():
        db.create_all()
        db.session.query(MLEvaluationRecord).filter(MLEvaluationRecord.evaluation_key == "cross-tenant").delete(synchronize_session=False)
        db.session.commit()
        auth = _authorization(org=2)
        with pytest.raises(ValueError, match="ml_tenant_mismatch"):
            ml_evaluation_capability.persist_complete_record(
                authorization_record=auth,
                organization_id=1, task_id="cross-tenant", evaluation_key="cross-tenant",
                dataset_digest=auth["dataset_sha256"], split_strategy="train_validation_test",
                baseline={"metric": "f1"}, model_results=[{"model": "svm"}], leakage_check="passed",
                generalization={}, evidence={
                    "leakage_evidence": {"status": "passed"},
                    "generalization_evidence": {"validation_strategy": "train_validation_test"},
                    "error_analysis": {"out_of_sample": {"summary": "reviewed"}},
                    "provenance": {"dataset_digest": auth["dataset_sha256"]},
                },
            )

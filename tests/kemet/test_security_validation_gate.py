from ops.security_validation_gate import validate_batch, validate_hypothesis


def base_hypothesis():
    return {
        "hypothesis_id": "sec_test",
        "source_digest": "source",
        "evidence_digest": "evidence",
        "execution_authority": False,
        "network": False,
        "source_evidence": False,
        "focused_test": False,
        "regression_proof": False,
    }


def test_gate_is_fail_closed_by_default():
    result = validate_hypothesis(base_hypothesis())
    assert result["status"] == "HYPOTHESIS_ONLY"
    assert result["promotable"] is False
    assert len(result["missing"]) == 3


def test_gate_requires_all_evidence_before_promotion():
    hypothesis = base_hypothesis()
    hypothesis.update({"source_evidence": True, "focused_test": True, "regression_proof": True})
    result = validate_hypothesis(hypothesis)
    assert result["status"] == "PROMOTABLE_FINDING"
    assert result["promotable"] is True


def test_gate_rejects_execution_or_network_authority():
    hypothesis = base_hypothesis()
    hypothesis.update({"source_evidence": True, "focused_test": True, "regression_proof": True})
    hypothesis["execution_authority"] = True
    result = validate_hypothesis(hypothesis)
    assert result["promotable"] is False
    assert "execution_authority_false" in result["missing"]


def test_batch_summary_is_deterministic_in_shape():
    result = validate_batch([base_hypothesis(), base_hypothesis()])
    assert result["schema"] == "kemet.security_validation_gate.v1"
    assert result["promotable_count"] == 0
    assert result["hypothesis_only_count"] == 2

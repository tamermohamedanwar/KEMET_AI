from pathlib import Path

import pytest


def test_artifact_preview_rejects_traversal(tmp_path):
    from app.core.execution.artifact_execution import ArtifactExecutionError, ArtifactExecutionService

    service = ArtifactExecutionService(tmp_path)
    with pytest.raises(ArtifactExecutionError, match="artifact_path_not_allowed"):
        service.preview([{"path": "app/../.env", "content": "secret"}])


def test_artifact_preview_is_deterministic(tmp_path):
    from app.core.execution.artifact_execution import ArtifactExecutionService

    service = ArtifactExecutionService(tmp_path)
    artifacts = [{"path": "app/example.txt", "content": "hello"}]
    first = service.preview(artifacts)
    second = service.preview(artifacts)
    assert first["digest"] == second["digest"]


def test_artifact_apply_creates_backup_and_result_digest(tmp_path):
    from app.core.execution.artifact_execution import ArtifactExecutionService

    service = ArtifactExecutionService(tmp_path)
    target = tmp_path / "app" / "example.txt"
    target.parent.mkdir(parents=True)
    target.write_text("old", encoding="utf-8")
    result = service.apply([{"path": "app/example.txt", "content": "new"}])
    assert target.read_text(encoding="utf-8") == "new"
    backup = tmp_path / "runtime_logs" / "artifact_backups" / result["preview_digest"] / "app" / "example.txt"
    assert backup.read_text(encoding="utf-8") == "old"
    assert result["result_digest"]


def test_artifact_action_fails_closed_without_binding():
    from app.automation.action_registry import registry

    result = registry.execute("artifact_write", {})
    assert result["success"] is False
    assert result["error"] == "artifact_execution_binding_required"


def test_artifact_rejects_stale_hash(tmp_path):
    from app.core.execution.artifact_execution import ArtifactExecutionError, ArtifactExecutionService
    import hashlib

    service = ArtifactExecutionService(tmp_path)
    target = tmp_path / "app" / "example.txt"
    target.parent.mkdir(parents=True)
    target.write_text("changed", encoding="utf-8")
    expected = hashlib.sha256(b"old").hexdigest()
    with pytest.raises(ArtifactExecutionError, match="artifact_stale_hash"):
        service.preview([{"path": "app/example.txt", "content": "new", "expected_sha256": expected}])


def test_artifact_rejects_sensitive_suffix(tmp_path):
    from app.core.execution.artifact_execution import ArtifactExecutionError, ArtifactExecutionService

    service = ArtifactExecutionService(tmp_path)
    with pytest.raises(ArtifactExecutionError, match="artifact_path_not_allowed"):
        service.preview([{"path": "app/private.pem", "content": "secret"}])


def test_artifact_action_rejects_preview_swap(tmp_path, monkeypatch):
    from app.automation.action_registry import registry
    from app.core.execution.artifact_execution import ArtifactExecutionService

    service = ArtifactExecutionService(tmp_path)
    preview = service.preview([{"path": "app/example.txt", "content": "safe"}])
    monkeypatch.setattr("app.core.execution.artifact_execution.artifact_execution", service)
    plan = {"action": "artifact_write", "plan_id": "p1"}
    authorization = {"plan_id": "p1", "plan_hash": "h"}
    result = registry.execute("artifact_write", {
        "_execution_plan": plan,
        "_execution_authorization": authorization,
        "_execution_action": "artifact_write",
        "artifacts": [{"path": "app/example.txt", "content": "tampered"}],
        "preview_digest": preview["digest"],
    })
    assert result["success"] is False
    assert result["error"] == "artifact_preview_mismatch"


def test_execution_envelope_binds_artifact_preview():
    from app.core.federation.execution_envelope import execution_envelope

    authorization = {"plan_id": "p1", "plan_hash": "h1"}
    envelope = execution_envelope.build(
        approval_package_hash="a", decision_hash="d", handoff_hash="g",
        authorization=authorization, execution_key="k", provider_id="kemet",
        action="artifact_write", artifact_preview_digest="artifact-digest",
    )
    assert execution_envelope.verify(
        envelope, authorization=authorization, execution_key="k",
        provider_id="kemet", action="artifact_write",
        artifact_preview_digest="artifact-digest",
    )
    assert not execution_envelope.verify(
        envelope, authorization=authorization, execution_key="k",
        provider_id="kemet", action="artifact_write",
        artifact_preview_digest="different",
    )

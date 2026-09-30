import pytest


def test_post_execution_validation_accepts_matching_python(tmp_path):
    from app.core.execution.post_execution_validator import PostExecutionValidator

    target = tmp_path / "app" / "sample.py"
    target.parent.mkdir(parents=True)
    content = "value = 42\n"
    target.write_text(content, encoding="utf-8")
    result = PostExecutionValidator(tmp_path).validate([
        {"path": "app/sample.py", "content": content}
    ])
    assert result["valid"] is True
    assert result["files"][0]["checks"]["python_syntax"] is True


def test_post_execution_validation_rejects_invalid_python(tmp_path):
    from app.core.execution.post_execution_validator import PostExecutionValidationError, PostExecutionValidator

    target = tmp_path / "app" / "sample.py"
    target.parent.mkdir(parents=True)
    content = "def broken(:\n"
    target.write_text(content, encoding="utf-8")
    with pytest.raises(PostExecutionValidationError, match="post_execution_validation_failed"):
        PostExecutionValidator(tmp_path).validate([
            {"path": "app/sample.py", "content": content}
        ])


def test_artifact_rollback_restores_previous_content(tmp_path):
    from app.core.execution.artifact_execution import ArtifactExecutionService

    service = ArtifactExecutionService(tmp_path)
    target = tmp_path / "app" / "sample.py"
    target.parent.mkdir(parents=True)
    target.write_text("old = 1\n", encoding="utf-8")
    result = service.apply([{"path": "app/sample.py", "content": "new = 2\n"}])
    rollback = service.rollback(result)
    assert rollback["rollback"] is True
    assert target.read_text(encoding="utf-8") == "old = 1\n"

import json
import subprocess
from pathlib import Path

from app.core.execution.governed_executor import GovernedExecutionService


ROOT = Path(__file__).resolve().parents[2]
PUBLISHER = ROOT / "ops" / "youtube_worker" / "publisher.mjs"


def test_youtube_publish_requires_approval():
    service = GovernedExecutionService()
    assert service._policy("youtube_publish") == "approval_required"


def test_youtube_action_is_fail_closed_without_execution_binding():
    from app.automation.action_registry import registry

    result = registry.execute("youtube_publish", {"manifest": "missing.json"})
    assert result["success"] is False
    assert result["error"] == "youtube_execution_binding_required"
    assert result["executed"] is False


def test_youtube_publisher_simulation_has_no_authorization_requirement(tmp_path):
    video = tmp_path / "sample.mp4"
    video.write_bytes(b"simulation-only-video")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"video": str(video), "title": "Kemet Test", "privacy_status": "private"}), encoding="utf-8")
    result = subprocess.run(
        ["node", str(PUBLISHER), str(manifest), "--simulate"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["mode"] == "simulate"
    assert payload["action"] == "youtube_publish"


def test_youtube_publisher_rejects_invalid_authorization(tmp_path):
    video = tmp_path / "sample.mp4"
    video.write_bytes(b"invalid-auth-test-video")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"video": str(video), "title": "Kemet Auth Test", "privacy_status": "private"}), encoding="utf-8")
    authorization = tmp_path / "authorization.json"
    authorization.write_text(json.dumps({
        "token": "invalid", "plan_id": "test-plan", "plan_hash": "test-hash",
        "action": "youtube_publish", "approver_id": 1, "expires_at": 4102444800,
    }), encoding="utf-8")
    result = subprocess.run(
        ["node", str(PUBLISHER), str(manifest), "--authorization-file", str(authorization)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "execution_authorization_invalid" in result.stderr


def test_youtube_publisher_rejects_public_without_schedule(tmp_path):
    video = tmp_path / "sample.mp4"
    video.write_bytes(b"public-safety-test-video")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "video": str(video), "title": "Kemet Public Safety", "privacy_status": "public",
    }), encoding="utf-8")
    result = subprocess.run(
        ["node", str(PUBLISHER), str(manifest), "--simulate"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert result.returncode != 0
    assert "public_publish_requires_schedule" in result.stderr


def test_youtube_publisher_invalid_auth_length_fails_closed(tmp_path):
    video = tmp_path / "sample.mp4"
    video.write_bytes(b"short-auth-test-video")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "video": str(video), "title": "Kemet Short Auth", "privacy_status": "private",
    }), encoding="utf-8")
    authorization = tmp_path / "authorization.json"
    authorization.write_text(json.dumps({
        "token": "x", "plan_id": "test-plan", "plan_hash": "test-hash",
        "action": "youtube_publish", "approver_id": 1, "expires_at": 4102444800,
    }), encoding="utf-8")
    result = subprocess.run(
        ["node", str(PUBLISHER), str(manifest), "--authorization-file", str(authorization)],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert result.returncode != 0
    assert "execution_authorization_invalid" in result.stderr


def test_youtube_publish_binding_is_part_of_task_plan():
    from app.core.task_planner import TaskPlanningEngine

    planner = TaskPlanningEngine()
    plan = planner.plan(
        "prepare a YouTube publishing workflow",
        organization_id=1,
        task_id="youtube-plan-test",
    )
    bound = planner.bind_youtube_publish(
        plan,
        manifest="ops/youtube_queue/kemet_private_pilot.json",
    )
    step = bound.steps[-1]
    assert step.action == "youtube_publish"
    assert step.requires_approval is True
    assert step.risk == "high"
    assert step.parameters["manifest"] == "ops/youtube_queue/kemet_private_pilot.json"
    assert "content_publishing" in step.capabilities


def test_command_center_binds_youtube_manifest_before_package():
    from pathlib import Path

    text = (Path(__file__).resolve().parents[2] / "app/routes/command_center.py").read_text()
    assert "task_planner.bind_youtube_publish" in text
    assert '"manifest": youtube_manifest' in text

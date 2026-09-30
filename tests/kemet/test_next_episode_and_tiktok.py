from app import create_app, db
from app.core.execution.governed_executor import governed_execution_service
from app.services.next_episode_learning_service import next_episode_learning_service
from app.services.tiktok_publishing_adapter import TikTokPublishRequest, tiktok_publishing_adapter


def test_learning_generates_next_episode_without_execution():
    result = next_episode_learning_service.build_recommendation(
        organization_id=1,
        episode={"episode_id": "ep-1", "title": "The Lost Map"},
        observed={"metrics": {"views": 1000, "retention_rate": 25, "shares": 4, "qualified_views": 100, "revenue": 0}},
    )
    assert result["success"] is True
    assert result["next_episode"]["title"].endswith("— بداية أقوى")
    assert "strengthen_first_3_seconds" in result["recommendations"]
    assert result["execution_authority"] is False
    assert result["auto_publish"] is False


def test_content_outcome_evaluation_feeds_next_episode():
    from app.services.content_outcome_orchestrator import content_outcome_orchestrator
    planned = content_outcome_orchestrator.build_plan(organization_id=1, episode={"episode_id": "ep-1", "title": "The Lost Map"}, platforms=("tiktok",))
    result = content_outcome_orchestrator.evaluate_results(planned=planned, results={"metrics": {"views": 100, "retention_rate": 60, "shares": 10, "qualified_views": 70, "revenue": 2}})
    assert result["next_episode"]["success"] is True
    assert result["next_episode"]["auto_publish"] is False


def test_tiktok_is_approval_gated_and_registered():
    assert governed_execution_service._policy("tiktok_publish") == "approval_required"
    assert governed_execution_service._registry().exists("tiktok_publish")


def test_tiktok_fails_closed_without_connection():
    app = create_app()
    with app.app_context():
        request = TikTokPublishRequest(1, 1, "https://example.test/video.mp4", dry_run=True)
        result = tiktok_publishing_adapter.publish(request, execution_key="tiktok-no-connection")
        assert result["status"] == "blocked"
        assert result["error"] == "publishing_connection_not_ready"


def test_tiktok_preflight_requires_video():
    app = create_app()
    with app.app_context():
        request = TikTokPublishRequest(1, 1, "https://example.test/image.jpg", media_type="image")
        result = tiktok_publishing_adapter.preflight(request)
        assert result["status"] == "blocked"
        assert result["error"] == "tiktok_video_required"

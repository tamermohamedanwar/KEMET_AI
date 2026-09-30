from app import create_app
from app.services.tiktok_research_adapter import TikTokResearchRequest, tiktok_research_adapter


def test_research_is_blocked_without_verified_connection():
    app = create_app()
    with app.app_context():
        result = tiktok_research_adapter.preflight(TikTokResearchRequest(1, 1, "marketing"))
        assert result["status"] == "blocked"
        assert result["error"] == "research_connection_not_ready"


def test_research_is_blocked_for_commercial_org_even_with_connection_metadata():
    app = create_app()
    with app.app_context():
        from app.models.provider_connection import ProviderConnectionRecord
        connection = ProviderConnectionRecord(organization_id=1, user_id=1, provider_id="social:tiktok", mode="official_connector", status="verified", scopes_json=["research.data.basic"], metadata_json={"research_eligibility": "approved", "research_org_type": "commercial"})
        from app import db
        db.session.add(connection)
        db.session.commit()
        result = tiktok_research_adapter.preflight(TikTokResearchRequest(1, 1, "marketing"))
        assert result["status"] == "blocked"
        assert result["error"] == "tiktok_research_not_available_for_commercial_use"
        db.session.delete(connection)
        db.session.commit()

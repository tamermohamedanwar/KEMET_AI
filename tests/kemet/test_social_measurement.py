from app import create_app
from app.services.social_measurement_service import MeasurementRequest, SocialMeasurementService


def test_measurement_fails_closed_without_connection():
    app = create_app()
    with app.app_context():
        result = SocialMeasurementService().measure(
            MeasurementRequest(1, 1, "instagram", "media-1")
        )
        assert result["status"] == "blocked"
        assert result["verified"] is False


def test_normalize_metrics():
    payload = {
        "data": [
            {"name": "reach", "values": [{"value": 12}]},
            {"name": "likes", "values": [{"value": 3}, {"value": 5}]},
        ]
    }
    assert SocialMeasurementService._normalize(payload) == {"reach": 12, "likes": 5}
    service = SocialMeasurementService()
    normalized = service._normalize(payload)
    assert {name: "OBSERVED" for name in normalized} == {"reach": "OBSERVED", "likes": "OBSERVED"}


def test_measurement_endpoint_exists():
    app = create_app()
    routes = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/command-center/api/bos/social-measurement" in routes

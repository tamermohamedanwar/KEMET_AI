from app.services.public_api_catalog_service import public_api_catalog_service


def test_public_api_catalog_is_discovery_only():
    snapshot = public_api_catalog_service.snapshot(7)
    assert snapshot["source"] == "public-apis/public-apis"
    assert snapshot["purpose"] == "discovery_only"
    assert snapshot["selection_policy"]["official_provider_preferred"] is True
    assert snapshot["selection_policy"]["no_automatic_connection"] is True


def test_catalog_prioritizes_visibility_and_youtube_candidates():
    names = {item["name"] for item in public_api_catalog_service.snapshot(7)["candidates"]}
    assert "Google Search Console" in names
    assert "YouTube Data API" in names
    assert "YouTube Analytics API" in names


def test_catalog_does_not_create_execution_authority():
    snapshot = public_api_catalog_service.snapshot(7)
    assert "execute" not in snapshot["purpose"]
    assert snapshot["selection_policy"]["no_secret_discovery"] is True
    assert public_api_catalog_service.security_note()["execution_authority_never_from_catalog"] is True

from app.services.api_key_service import create_api_key, authenticate_api_key

def test_api_key_is_hashed_and_authenticates(app):
    with app.app_context():
        key,raw=create_api_key(organization_id=1,name="test")
        assert raw.startswith("kemet_")
        assert key.key_hash != raw
        assert authenticate_api_key(raw).id == key.id
        assert authenticate_api_key("kemet_invalid") is None

def test_api_key_is_tenant_bound(app):
    with app.app_context():
        key,raw=create_api_key(organization_id=123,name="tenant")
        assert authenticate_api_key(raw).organization_id == 123

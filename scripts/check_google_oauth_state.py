from app import create_app
from app.core.social_credential_store import social_credential_store
app = create_app()
with app.app_context():
    c = social_credential_store.get(1, 1, "youtube")
    print("ACCESS_TOKEN_PRESENT=" + str(bool(c.get("access_token"))))
    print("REFRESH_TOKEN_PRESENT=" + str(bool(c.get("refresh_token"))))
    print("TOKEN_TYPE=" + str(c.get("token_type") or ""))
    print("SCOPE_PRESENT=" + str(bool(c.get("scope") or c.get("scopes"))))

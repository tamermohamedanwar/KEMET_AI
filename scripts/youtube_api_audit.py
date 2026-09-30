from datetime import datetime, timezone
from app import create_app, db
from app.models.provider_connection import ProviderConnectionRecord
from app.core.social_credential_store import social_credential_store
from app.core.google_oauth_token_service import google_oauth_token_service
from app.core.governed_http import governed_request
from app.core.egress_policy import validate_public_http_target

app = create_app()
with app.app_context():
    row = ProviderConnectionRecord.query.filter_by(
        organization_id=1,
        user_id=1,
        provider_id="social:youtube",
        mode="official_connector",
        status="verified",
    ).first()
    if not row:
        raise SystemExit("youtube_connection_not_found")
    creds = social_credential_store.get(1, 1, "youtube")
    token = creds.get("access_token")
    refresh_attempted = False
    if not token:
        refresh_attempted = True
        refreshed = google_oauth_token_service.refresh_social_credential(1, 1, "youtube")
        token = refreshed["access_token"]
    endpoint = validate_public_http_target(
        "https://www.googleapis.com/youtube/v3/channels",
        allow_hosts={"www.googleapis.com"},
    )
    response = governed_request(
        "GET",
        endpoint,
        params={"part": "id,snippet,contentDetails,statistics", "mine": "true"},
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
        allow_redirects=False,
    )
    if response.status_code == 401 and creds.get("refresh_token"):
        refresh_attempted = True
        refreshed = google_oauth_token_service.refresh_social_credential(1, 1, "youtube")
        token = refreshed["access_token"]
        response = governed_request(
            "GET", endpoint,
            params={"part": "id,snippet,contentDetails,statistics", "mine": "true"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
            allow_redirects=False,
        )
    response.raise_for_status()
    payload = response.json()
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list) or not items:
        raise SystemExit("youtube_api_identity_empty")
    channel = items[0]
    channel_id = str(channel.get("id") or "")
    title = str((channel.get("snippet") or {}).get("title") or "")
    if not channel_id or not title:
        raise SystemExit("youtube_api_identity_incomplete")
    scopes = row.scopes_json if isinstance(row.scopes_json, list) else []
    upload_scope = "https://www.googleapis.com/auth/youtube.upload"
    if upload_scope not in {str(x) for x in scopes}:
        raise SystemExit("youtube_upload_scope_missing")
    previous = dict(row.metadata_json or {}) if isinstance(row.metadata_json, dict) else {}
    audit = {
        "api_audited": True,
        "audit_type": "functional_youtube_api_identity_and_scope_check",
        "audit_version": "1.1",
        "audited_at": datetime.now(timezone.utc).isoformat(),
        "endpoint": "https://www.googleapis.com/youtube/v3/channels",
        "http_status": int(response.status_code),
        "refresh_attempted": refresh_attempted,
        "account_ref_verified": channel_id == str(row.provider_account_ref or ""),
        "publishing_scope_verified": True,
        "credentials_exposed": False,
    }
    if not audit["account_ref_verified"]:
        raise SystemExit("youtube_account_ref_mismatch")
    previous.update(audit)
    row.metadata_json = previous
    db.session.commit()
    print("YOUTUBE_API_AUDIT=PASS")
    print("STATUS=", response.status_code)
    print("ACCOUNT_REF_MATCH=PASS")
    print("UPLOAD_SCOPE=PASS")
    print("REFRESH_ATTEMPTED=" + str(refresh_attempted))
    print("CREDENTIALS_EXPOSED=False")
    print("AUDIT_STORED=True")

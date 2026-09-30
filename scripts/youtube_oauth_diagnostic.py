from app import create_app
from app.models.provider_connection import ProviderConnectionRecord
from app.core.social_credential_store import social_credential_store
from app.core.governed_http import governed_request
import os

app = create_app()
with app.app_context():
    row = ProviderConnectionRecord.query.filter_by(organization_id=1, provider_id="social:youtube").first()
    if not row:
        print("CONNECTION_FOUND=False")
        raise SystemExit(0)
    token = social_credential_store.get(1, row.user_id, "youtube") or {}
    access = token.get("access_token")
    print("CONNECTION_FOUND=True")
    print("STATUS=" + str(row.status))
    print("ACCESS_TOKEN_PRESENT=" + str(bool(access)))
    print("REFRESH_TOKEN_PRESENT=" + str(bool(token.get("refresh_token"))))
    print("TOKEN_TYPE=" + str(token.get("token_type") or ""))
    print("SCOPE_PRESENT=" + str(bool(token.get("scope") or token.get("scopes"))))
    if not access:
        raise SystemExit(2)

    ti = governed_request(
        "GET",
        "https://oauth2.googleapis.com/tokeninfo",
        params={"access_token": access},
        allow_hosts={"oauth2.googleapis.com"},
        timeout=15,
    )
    print("TOKENINFO_HTTP=" + str(ti.status_code))
    if ti.ok:
        data = ti.json()
        print("TOKENINFO_AUDIENCE_MATCH=" + str(data.get("aud") == os.getenv("GOOGLE_CLIENT_ID", "").strip()))
        print("TOKENINFO_SCOPE_HAS_YOUTUBE=" + str("youtube" in str(data.get("scope", ""))))
        print("TOKENINFO_EXPIRES_IN_PRESENT=" + str(bool(data.get("expires_in"))))
        print("TOKENINFO_ISSUER=" + str(data.get("iss") or ""))
    else:
        print("TOKENINFO_ERROR_TYPE=" + str((ti.json() if ti.content else {}).get("error", "unknown")))

    yt = governed_request(
        "GET",
        "https://www.googleapis.com/youtube/v3/channels",
        params={"part": "id,snippet", "mine": "true"},
        headers={"Authorization": "Bearer " + access},
        allow_hosts={"www.googleapis.com"},
        timeout=15,
    )
    print("YOUTUBE_HTTP=" + str(yt.status_code))
    if not yt.ok:
        data = yt.json() if yt.content else {}
        err = data.get("error", {}) if isinstance(data, dict) else {}
        print("YOUTUBE_ERROR_REASON=" + str((err.get("errors") or [{}])[0].get("reason", "")))
        print("YOUTUBE_ERROR_STATUS=" + str(err.get("code", "")))

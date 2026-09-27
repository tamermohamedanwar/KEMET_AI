from __future__ import annotations

import hashlib
import json
import os
import secrets

from cryptography.fernet import Fernet, InvalidToken

from app import db
from app.models.social_oauth import EncryptedSocialCredential


class SocialCredentialStore:
    VERSION = "1.2"
    KEY_ENV = "KEMET_OAUTH_ENCRYPTION_KEY"

    def _fernet(self) -> Fernet:
        raw = os.getenv(self.KEY_ENV, "").strip()
        if not raw:
            raise RuntimeError("oauth_encryption_key_not_configured")
        try:
            return Fernet(raw.encode())
        except Exception as exc:
            raise RuntimeError("oauth_encryption_key_invalid") from exc

    @staticmethod
    def _ref(organization_id: int, user_id: int, channel: str) -> str:
        raw = f"{organization_id}:{user_id}:{channel}:{secrets.token_hex(16)}"
        return "oauthref_" + hashlib.sha256(raw.encode()).hexdigest()[:40]

    def put(self, organization_id: int, user_id: int, channel: str, payload: dict) -> str:
        if not organization_id or not user_id or not channel or not isinstance(payload, dict):
            raise ValueError("oauth_credential_scope_required")
        ciphertext = self._fernet().encrypt(json.dumps(payload, separators=(",", ":")).encode()).decode()
        row = EncryptedSocialCredential.query.filter_by(organization_id=organization_id, user_id=user_id, channel=channel).first()
        if not row:
            row = EncryptedSocialCredential(organization_id=organization_id, user_id=user_id, channel=channel, credential_ref=self._ref(organization_id, user_id, channel), ciphertext=ciphertext)
        else:
            row.ciphertext = ciphertext
        db.session.add(row)
        db.session.commit()
        return row.credential_ref

    def get(self, organization_id: int, user_id: int, channel: str) -> dict:
        row = EncryptedSocialCredential.query.filter_by(organization_id=organization_id, user_id=user_id, channel=channel).first()
        if not row:
            raise KeyError("oauth_credentials_not_found")
        try:
            return json.loads(self._fernet().decrypt(row.ciphertext.encode()).decode())
        except (InvalidToken, ValueError, TypeError) as exc:
            raise RuntimeError("oauth_credential_decryption_failed") from exc

    def public_ref(self, organization_id: int, user_id: int, channel: str) -> str | None:
        row = EncryptedSocialCredential.query.filter_by(organization_id=organization_id, user_id=user_id, channel=channel).first()
        return row.credential_ref if row else None


social_credential_store = SocialCredentialStore()

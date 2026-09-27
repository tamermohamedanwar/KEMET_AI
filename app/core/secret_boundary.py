import hashlib
import os
import re

_SECRET_KEYS = {"authorization", "password", "secret", "token", "api_key", "apikey", "private_key", "cookie", "access_token", "refresh_token", "client_secret", "x_api_key", "set_cookie"}
_SECRET_PATTERN = re.compile(r"(?i)(bearer\s+|api[_-]?key\s*[=:]\s*|password\s*[=:]\s*|token\s*[=:]\s*|access[_-]?token\s*[=:]\s*|refresh[_-]?token\s*[=:]\s*|client[_-]?secret\s*[=:]\s*)[^\s,;]+")


def redact(value):
    if isinstance(value, dict):
        return {str(k): "[REDACTED]" if str(k).lower().replace("-", "_") in _SECRET_KEYS else redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value[:100]]
    if isinstance(value, tuple):
        return [redact(v) for v in value[:100]]
    if isinstance(value, str):
        return _SECRET_PATTERN.sub(lambda m: m.group(1) + "[REDACTED]", value[:8192])
    return value


def secret_reference(provider: str, name: str) -> str:
    clean = f"{provider}:{name}".encode("utf-8")
    return "secretref_" + hashlib.sha256(clean).hexdigest()[:32]


def resolve_secret(provider: str, name: str, *, organization_id: int) -> str:
    if not organization_id:
        raise ValueError("organization_id_required")
    provider = str(provider or "").strip().lower()
    name = str(name or "").strip().lower().replace("-", "_")
    allowed = {
        ("meta_whatsapp_cloud_api", "access_token"): "ACCESS_TOKEN",
        ("meta_whatsapp_cloud_api", "app_secret"): "APP_SECRET",
        ("meta_whatsapp_cloud_api", "phone_number_id"): "PHONE_NUMBER_ID",
        ("bosta_api", "api_key"): "API_KEY",
        ("salla_api", "webhook_secret"): "WEBHOOK_SECRET",
        ("salla_api", "access_token"): "ACCESS_TOKEN",
    }
    suffix = allowed.get((provider, name))
    if suffix is None:
        raise ValueError("secret_not_allowed")
    prefixes = {
        "meta_whatsapp_cloud_api": "KEMET_META_ORG",
        "bosta_api": "KEMET_BOSTA_ORG",
        "salla_api": "KEMET_SALLA_ORG",
    }
    prefix = prefixes[provider]
    key = f"{prefix}_{int(organization_id)}_{suffix}"
    value = os.getenv(key, "").strip()
    if not value:
        # Tenant-scoped encrypted product credentials are the fallback.
        # Require exactly one credential row for this organization/channel.
        try:
            from app.models.social_oauth import EncryptedSocialCredential
            from cryptography.fernet import Fernet, InvalidToken
            import json
            channel = {
                "meta_whatsapp_cloud_api": "whatsapp_cloud_api",
                "salla_api": "salla_api",
            }[provider]
            rows = EncryptedSocialCredential.query.filter_by(
                organization_id=int(organization_id), channel=channel
            ).order_by(EncryptedSocialCredential.id.desc()).all()
            if len(rows) != 1:
                raise RuntimeError("secret_not_configured" if not rows else "secret_credential_ambiguous")
            raw = os.getenv("KEMET_OAUTH_ENCRYPTION_KEY", "").strip()
            if not raw:
                raise RuntimeError("oauth_encryption_key_not_configured")
            payload = json.loads(Fernet(raw.encode()).decrypt(rows[0].ciphertext.encode()).decode())
            value = str(payload.get(name) or "").strip()
        except RuntimeError:
            raise
        except (InvalidToken, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            raise RuntimeError("oauth_credential_decryption_failed") from exc
        except Exception:
            raise RuntimeError("secret_not_configured")
    if not value:
        raise RuntimeError("secret_not_configured")
    return value


def ensure_no_secret(value):
    redacted = redact(value)
    return redacted

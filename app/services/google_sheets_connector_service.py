from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from typing import Any, Callable
from datetime import datetime, timezone
from urllib.parse import urlencode

from app.core.egress_policy import validate_public_http_target
from app.core.governed_http import governed_request
from app.core.integration.connector_contract import ConnectorContract
from app.core.integration.connector_registry import ConnectorRegistry
from app.core.secret_boundary import redact
from app.core.social_credential_store import social_credential_store
from app.core.social_oauth_lifecycle import social_oauth_lifecycle
from app.core.federation.connection_lifecycle import ConnectionLifecycleService


GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_SHEETS_BASE = "https://sheets.googleapis.com/v4"
READ_SCOPE = "https://www.googleapis.com/auth/spreadsheets.readonly"
WRITE_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
DRIVE_FILE_SCOPE = "https://www.googleapis.com/auth/drive.file"
RANGE_RE = re.compile(r"^[A-Za-z0-9_ .'!-]{1,120}!\$?[A-Z]{1,3}\$?[1-9][0-9]*(:\$?[A-Z]{1,3}\$?[1-9][0-9]*)?$|^\$?[A-Z]{1,3}\$?[1-9][0-9]*(:\$?[A-Z]{1,3}\$?[1-9][0-9]*)?$")
MAX_CELLS = 10000
MAX_ROWS = 1000
MAX_COLS = 50


@dataclass(frozen=True)
class GoogleSheetsAction:
    action: str
    risk_tier: str
    scope: str
    side_effect: bool
    approval_required: bool
    evidence_required: bool


ACTIONS = {
    "google_sheets.read_range": GoogleSheetsAction("google_sheets.read_range", "low", READ_SCOPE, False, False, True),
    "google_sheets.write_range": GoogleSheetsAction("google_sheets.write_range", "high", WRITE_SCOPE, True, True, True),
    "google_sheets.append_rows": GoogleSheetsAction("google_sheets.append_rows", "high", WRITE_SCOPE, True, True, True),
}


class GoogleSheetsConnectorService:
    VERSION = "1.0"
    PROVIDER_ID = "google_sheets"
    PURPOSE = "google_sheets"

    def __init__(self, registry: ConnectorRegistry | None = None):
        self.registry = registry or ConnectorRegistry()

    def contract(self, organization_id: int) -> ConnectorContract:
        return ConnectorContract(
            connector_id=self.PROVIDER_ID,
            version=self.VERSION,
            organization_id=int(organization_id),
            operations=tuple(ACTIONS),
            data_scopes=("google_sheets", "spreadsheet_values"),
            risk_tier="high",
            approval_level="human",
            idempotency="required",
            timeout_seconds=20,
            max_retries=1,
            reversible=False,
            evidence_required=True,
            metadata={"provider": "google", "service": "sheets", "canonical_runtime_only": True},
        )

    def register(self, organization_id: int) -> dict[str, Any]:
        return self.registry.register(self.contract(organization_id))

    @staticmethod
    def _validate_target(spreadsheet_id: str, range_name: str) -> tuple[str, str]:
        spreadsheet_id = str(spreadsheet_id or "").strip()
        range_name = str(range_name or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]{10,150}", spreadsheet_id):
            raise ValueError("invalid_spreadsheet_id")
        if not RANGE_RE.fullmatch(range_name):
            raise ValueError("invalid_range")
        if len(range_name) > 120:
            raise ValueError("range_too_large")
        return spreadsheet_id, range_name

    @staticmethod
    def _validate_values(values: Any) -> list[list[Any]]:
        if not isinstance(values, list) or not values or not all(isinstance(row, list) for row in values):
            raise ValueError("values_matrix_required")
        rows = len(values)
        cols = max((len(row) for row in values), default=0)
        if rows > MAX_ROWS or cols > MAX_COLS or rows * cols > MAX_CELLS:
            raise ValueError("payload_too_large")
        return values

    def simulate_write(self, organization_id: int, action: str, spreadsheet_id: str, range_name: str, values: list[list[Any]]) -> dict[str, Any]:
        if action not in {"google_sheets.write_range", "google_sheets.append_rows"}:
            raise ValueError("unsupported_write_action")
        spreadsheet_id, range_name = self._validate_target(spreadsheet_id, range_name)
        values = self._validate_values(values)
        digest = hashlib.sha256(json.dumps(values, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()
        return {
            "organization_id": int(organization_id), "provider": "google", "service": "sheets",
            "action": action, "spreadsheet_id": spreadsheet_id, "range": range_name,
            "rows": len(values), "columns": max(len(row) for row in values),
            "values_digest": digest, "external_side_effects": True,
            "approval_required": True, "executed": False,
        }
    @staticmethod
    def _granted_scopes(raw_scope: Any) -> set[str]:
        if isinstance(raw_scope, str):
            return {item.strip() for item in raw_scope.split() if item.strip()}
        if isinstance(raw_scope, list):
            return {str(item).strip() for item in raw_scope if str(item).strip()}
        return set()

    @classmethod
    def _require_scope(cls, credential: dict[str, Any], required_scope: str) -> None:
        scopes = cls._granted_scopes(credential.get("scope"))
        if required_scope not in scopes:
            raise PermissionError("google_scope_not_granted")

    def access_token(self, organization_id: int, user_id: int, *, write: bool = False) -> str:
        credential = social_credential_store.get(int(organization_id), int(user_id), "google_sheets")
        required_scope = WRITE_SCOPE if write else READ_SCOPE
        self._require_scope(credential, required_scope)
        access_token = str(credential.get("access_token") or "")
        expires_at = credential.get("expires_at")
        try:
            expired = bool(expires_at) and datetime.fromisoformat(str(expires_at)).timestamp() <= datetime.now(timezone.utc).timestamp() + 30
        except (TypeError, ValueError):
            expired = False
        if access_token and not expired:
            return access_token
        refresh_token = str(credential.get("refresh_token") or "")
        if not refresh_token:
            raise PermissionError("google_access_token_expired")
        client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
        if not client_id or not client_secret:
            raise RuntimeError("google_oauth_configuration_required")
        response = governed_request("POST", GOOGLE_TOKEN_URL, headers={"Content-Type": "application/x-www-form-urlencoded"}, data={"client_id": client_id, "client_secret": client_secret, "refresh_token": refresh_token, "grant_type": "refresh_token"}, timeout=20)
        response.raise_for_status()
        token = response.json()
        new_access_token = str(token.get("access_token") or "")
        if not new_access_token:
            raise PermissionError("google_access_token_refresh_failed")
        credential["access_token"] = new_access_token
        credential["expires_at"] = datetime.now(timezone.utc).timestamp() + int(token.get("expires_in") or 3600)
        credential["scope"] = token.get("scope") or credential.get("scope")
        social_credential_store.put(int(organization_id), int(user_id), "google_sheets", credential)
        self._require_scope(credential, required_scope)
        return new_access_token

    def read_range(self, organization_id: int, spreadsheet_id: str, range_name: str, credential: str) -> dict[str, Any]:
        if not credential:
            raise ValueError("credential_required")
        if not self.registry.allows(self.PROVIDER_ID, "google_sheets.read_range", int(organization_id)):
            self.register(int(organization_id))
        if not self.registry.allows(self.PROVIDER_ID, "google_sheets.read_range", int(organization_id)):
            raise PermissionError("connector_not_authorized")
        spreadsheet_id, range_name = self._validate_target(spreadsheet_id, range_name)
        endpoint = validate_public_http_target(
            f"{GOOGLE_SHEETS_BASE}/spreadsheets/{spreadsheet_id}/values/{range_name}",
            allow_hosts={"sheets.googleapis.com"},
        )
        response = governed_request("GET", endpoint, headers={"Authorization": f"Bearer {credential}"}, timeout=20)
        response.raise_for_status()
        payload = response.json()
        values = payload.get("values") if isinstance(payload, dict) else None
        rows = len(values) if isinstance(values, list) else 0
        cols = max((len(row) for row in values if isinstance(row, list)), default=0) if values else 0
        if rows > MAX_ROWS or cols > MAX_COLS or rows * cols > MAX_CELLS:
            raise ValueError("response_too_large")
        return {"organization_id": int(organization_id), "provider": "google", "service": "sheets", "operation": "read", "range": payload.get("range", range_name), "values": values or [], "executed": True, "external_side_effects": False}

    def write_range(self, organization_id: int, spreadsheet_id: str, range_name: str, values: list[list[Any]], credential: str, *, approved: bool = False) -> dict[str, Any]:
        if not approved:
            raise PermissionError("human_approval_required")
        if not credential:
            raise ValueError("credential_required")
        if not self.registry.allows(self.PROVIDER_ID, "google_sheets.write_range", int(organization_id)):
            self.register(int(organization_id))
        if not self.registry.allows(self.PROVIDER_ID, "google_sheets.write_range", int(organization_id)):
            raise PermissionError("connector_not_authorized")
        spreadsheet_id, range_name = self._validate_target(spreadsheet_id, range_name)
        values = self._validate_values(values)
        endpoint = validate_public_http_target(
            f"{GOOGLE_SHEETS_BASE}/spreadsheets/{spreadsheet_id}/values/{range_name}",
            allow_hosts={"sheets.googleapis.com"},
        )
        response = governed_request(
            "PUT", endpoint, headers={"Authorization": f"Bearer {credential}"},
            params={"valueInputOption": "USER_ENTERED"},
            json={"range": range_name, "majorDimension": "ROWS", "values": values}, timeout=20,
        )
        response.raise_for_status()
        result = response.json()
        return {"organization_id": int(organization_id), "provider": "google", "service": "sheets", "operation": "write", "range": range_name, "updated": result.get("updatedCells", 0), "executed": True, "external_side_effects": True, "evidence": redact({"response": result})}

    def append_rows(self, organization_id: int, spreadsheet_id: str, range_name: str, values: list[list[Any]], credential: str, *, approved: bool = False) -> dict[str, Any]:
        if not approved:
            raise PermissionError("human_approval_required")
        if not credential:
            raise ValueError("credential_required")
        if not self.registry.allows(self.PROVIDER_ID, "google_sheets.append_rows", int(organization_id)):
            self.register(int(organization_id))
        if not self.registry.allows(self.PROVIDER_ID, "google_sheets.append_rows", int(organization_id)):
            raise PermissionError("connector_not_authorized")
        spreadsheet_id, range_name = self._validate_target(spreadsheet_id, range_name)
        values = self._validate_values(values)
        endpoint = validate_public_http_target(
            f"{GOOGLE_SHEETS_BASE}/spreadsheets/{spreadsheet_id}/values/{range_name}:append",
            allow_hosts={"sheets.googleapis.com"},
        )
        response = governed_request(
            "POST", endpoint, headers={"Authorization": f"Bearer {credential}"},
            params={"valueInputOption": "USER_ENTERED", "insertDataOption": "INSERT_ROWS"},
            json={"majorDimension": "ROWS", "values": values}, timeout=20,
        )
        response.raise_for_status()
        result = response.json()
        return {"organization_id": int(organization_id), "provider": "google", "service": "sheets", "operation": "append", "range": range_name, "updates": redact(result.get("updates", {})), "executed": True, "external_side_effects": True}

    def authorization_start(self, organization_id: int, user_id: int, *, write: bool = False) -> dict[str, Any]:
        client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
        redirect_uri = os.getenv("GOOGLE_SHEETS_REDIRECT_URI", "").strip()
        if not client_id or not redirect_uri:
            return {"status": "setup_required", "provider": "google", "service": "sheets", "credentials_exposed": False}
        state = social_oauth_lifecycle.create_state(int(organization_id), int(user_id), "google_sheets_write" if write else "google_sheets_read")
        scope = WRITE_SCOPE if write else READ_SCOPE
        params = {"client_id": client_id, "redirect_uri": redirect_uri, "response_type": "code", "scope": scope, "state": state, "access_type": "offline", "include_granted_scopes": "true", "prompt": "consent"}
        return {"status": "authorization_ready", "provider": "google", "service": "sheets", "authorization_url": f"{GOOGLE_AUTH_URL}?{urlencode(params)}", "scope": scope, "credentials_exposed": False, "execution_authority": False}

    def authorization_callback(self, organization_id: int, user_id: int, code: str, state: str, *, write: bool | None = None) -> dict[str, Any]:
        expected_channels = (["google_sheets_write", "google_sheets_read"] if write is None else (["google_sheets_write"] if write else ["google_sheets_read"]))
        row = None
        for channel in expected_channels:
            try:
                row = social_oauth_lifecycle.consume_state(state, int(organization_id), int(user_id), channel)
                break
            except ValueError as exc:
                if str(exc) not in {"oauth_state_mismatch", "oauth_state_replayed", "oauth_state_expired"}:
                    raise
        if row is None:
            raise ValueError("oauth_state_mismatch")
        write = row.channel == "google_sheets_write"
        client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip(); client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip(); redirect_uri = os.getenv("GOOGLE_SHEETS_REDIRECT_URI", "").strip()
        if not code or not client_id or not client_secret or not redirect_uri:
            raise ValueError("google_oauth_configuration_required")
        response = governed_request("POST", GOOGLE_TOKEN_URL, headers={"Content-Type": "application/x-www-form-urlencoded"}, data={"code": code, "client_id": client_id, "client_secret": client_secret, "redirect_uri": redirect_uri, "grant_type": "authorization_code"}, timeout=20)
        response.raise_for_status(); token = response.json()
        if not isinstance(token, dict) or not token.get("access_token"):
            raise ValueError("google_oauth_token_missing")
        scope = WRITE_SCOPE if write else READ_SCOPE
        granted_scopes = self._granted_scopes(token.get("scope") or scope)
        if scope not in granted_scopes:
            raise PermissionError("google_scope_not_granted")
        expires_in = int(token.get("expires_in") or 3600)
        credential_ref = social_credential_store.put(int(organization_id), int(user_id), "google_sheets", {"access_token": token["access_token"], "refresh_token": token.get("refresh_token"), "scope": " ".join(sorted(granted_scopes)), "token_type": token.get("token_type", "Bearer"), "expires_in": expires_in, "expires_at": datetime.now(timezone.utc).timestamp() + expires_in})
        row = ConnectionLifecycleService.register(int(organization_id), int(user_id), "social:google_sheets", mode="official_connector", scopes=[token.get("scope") or scope], credential_ref=credential_ref, metadata={"provider": "google", "service": "sheets"})
        return {"status": "connected", "provider": "google", "service": "sheets", "credential_ref": credential_ref, "connection_id": row.id, "credentials_exposed": False, "execution_authority": False}


google_sheets_connector_service = GoogleSheetsConnectorService()

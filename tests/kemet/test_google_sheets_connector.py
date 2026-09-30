import pytest

from app.services.google_sheets_connector_service import (
    GOOGLE_SHEETS_BASE,
    READ_SCOPE,
    WRITE_SCOPE,
    GoogleSheetsConnectorService,
)


def service():
    return GoogleSheetsConnectorService()


def test_google_sheets_contract_is_tenant_bound_and_governed():
    contract = service().contract(17)
    assert contract.connector_id == "google_sheets"
    assert contract.organization_id == 17
    assert set(contract.operations) == {
        "google_sheets.read_range",
        "google_sheets.write_range",
        "google_sheets.append_rows",
    }
    assert contract.evidence_required is True
    assert contract.idempotency == "required"
    assert contract.metadata["canonical_runtime_only"] is True


def test_google_sheets_scopes_are_narrow_and_explicit():
    assert READ_SCOPE.endswith("/spreadsheets.readonly")
    assert WRITE_SCOPE.endswith("/spreadsheets")
    assert "drive" not in READ_SCOPE
    assert "drive" not in WRITE_SCOPE


def test_register_isolated_by_organization():
    connector = service()
    assert connector.register(17)["registered"] is True
    assert connector.registry.allows("google_sheets", "google_sheets.read_range", 17) is True
    assert connector.registry.allows("google_sheets", "google_sheets.read_range", 18) is False


def test_simulation_is_read_only_and_does_not_call_provider():
    result = service().simulate_write(17, "google_sheets.write_range", "A1B2C3D4E5F6", "Leads!A2:C3", [[1, 2, 3], [4, 5, 6]])
    assert result["executed"] is False
    assert result["approval_required"] is True
    assert result["external_side_effects"] is True
    assert result["rows"] == 2
    assert result["columns"] == 3


def test_invalid_spreadsheet_id_fails_closed():
    with pytest.raises(ValueError, match="invalid_spreadsheet_id"):
        service().simulate_write(17, "google_sheets.write_range", "bad", "A1:B2", [[1]])


def test_invalid_range_fails_closed():
    with pytest.raises(ValueError, match="invalid_range"):
        service().simulate_write(17, "google_sheets.write_range", "A1B2C3D4E5F6", "A1;DROP", [[1]])


def test_oversized_payload_fails_closed():
    values = [[1] * 51]
    with pytest.raises(ValueError, match="payload_too_large"):
        service().simulate_write(17, "google_sheets.write_range", "A1B2C3D4E5F6", "A1:AY1", values)


def test_write_requires_human_approval_before_provider_call():
    with pytest.raises(PermissionError, match="human_approval_required"):
        service().write_range(17, "A1B2C3D4E5F6", "Leads!A1:B1", [[1, 2]], "credential")


def test_append_requires_human_approval_before_provider_call():
    with pytest.raises(PermissionError, match="human_approval_required"):
        service().append_rows(17, "A1B2C3D4E5F6", "Leads!A1:B1", [[1, 2]], "credential")


def test_append_is_tenant_bound_to_connector_registry():
    connector = service()
    connector.register(17)
    assert connector.registry.allows("google_sheets", "google_sheets.append_rows", 17) is True
    assert connector.registry.allows("google_sheets", "google_sheets.append_rows", 18) is False


def test_provider_endpoint_is_google_sheets_only():
    assert GOOGLE_SHEETS_BASE == "https://sheets.googleapis.com/v4"


def test_oauth_start_binds_requested_mode_to_state(monkeypatch):
    from app.services import google_sheets_connector_service as module

    calls = []
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "client-id")
    monkeypatch.setenv("GOOGLE_SHEETS_REDIRECT_URI", "https://kemet.example/api/google-sheets/callback")
    monkeypatch.setattr(module.social_oauth_lifecycle, "create_state", lambda org, user, channel: calls.append(channel) or "state")

    read = service().authorization_start(17, 9, write=False)
    write = service().authorization_start(17, 9, write=True)

    assert calls == ["google_sheets_read", "google_sheets_write"]
    assert read["scope"] == READ_SCOPE
    assert write["scope"] == WRITE_SCOPE


def test_oauth_callback_uses_state_bound_mode(monkeypatch):
    from types import SimpleNamespace
    from app.services import google_sheets_connector_service as module

    registered = []

    class Response:
        def raise_for_status(self):
            return None
        def json(self):
            return {"access_token": "token", "refresh_token": "refresh", "scope": READ_SCOPE, "expires_in": 3600}

    def consume(state, org, user, channel):
        if channel == "google_sheets_write":
            raise ValueError("oauth_state_mismatch")
        assert channel == "google_sheets_read"
        return SimpleNamespace(channel=channel)

    monkeypatch.setenv("GOOGLE_CLIENT_ID", "client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("GOOGLE_SHEETS_REDIRECT_URI", "https://kemet.example/api/google-sheets/callback")
    monkeypatch.setattr(module.social_oauth_lifecycle, "consume_state", consume)
    monkeypatch.setattr(module, "governed_request", lambda *args, **kwargs: Response())
    monkeypatch.setattr(module.social_credential_store, "put", lambda *args, **kwargs: "cred-ref")
    monkeypatch.setattr(module.ConnectionLifecycleService, "register", lambda *args, **kwargs: registered.append(kwargs) or SimpleNamespace(id=41))

    result = service().authorization_callback(17, 9, "code", "state")

    assert result["connection_id"] == 41
    assert registered[0]["scopes"] == [READ_SCOPE]
    assert result["execution_authority"] is False

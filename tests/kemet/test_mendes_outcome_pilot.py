from wsgi import application
from app.models.durable_workforce import WorkforceAssignment, WorkforceTask
from app.services.mendes.mendes_outcome_pilot import mendes_outcome_pilot_service


def test_prepare_is_tenant_scoped_and_approval_ready():
    with application.app_context():
        result = mendes_outcome_pilot_service.prepare(1)
        assert result["success"] is True
        assert result["status"] == "APPROVAL_READY"
        assert result["packet"]["organization_id"] == 1
        assert result["packet"]["approval"]["required"] is True


def test_prepare_preserves_truth_boundary_for_first_episode():
    with application.app_context():
        packet = mendes_outcome_pilot_service.prepare(1)["packet"]
        learning = packet["learning"]
        assert learning["observed_outcome"] is None
        assert learning["qualified_views"] is None
        assert learning["revenue"] is None
        assert learning["revenue_per_1000_qualified_views"] is None


def test_prepare_contains_bound_digests_and_quality_gates():
    with application.app_context():
        packet = mendes_outcome_pilot_service.prepare(1)["packet"]
        assert packet["episode"]["package_digest"]
        assert packet["episode"]["script_digest"]
        assert packet["production"]["voice_contract_digest"]
        assert packet["production"]["quality_gates"]
        assert packet["approval"]["approval_binding"]
        assert packet["packet_digest"]


def test_prepare_does_not_create_workforce_execution_state():
    with application.app_context():
        assignments = WorkforceAssignment.query.count()
        tasks = WorkforceTask.query.count()
        mendes_outcome_pilot_service.prepare(1)
        assert WorkforceAssignment.query.count() == assignments
        assert WorkforceTask.query.count() == tasks


def test_authoritative_outcome_requires_matching_tenant():
    with application.app_context():
        packet = mendes_outcome_pilot_service.prepare(1)["packet"]
        packet["organization_id"] = 2
        result = mendes_outcome_pilot_service.evaluate_authoritative_outcome(
            1, packet, {"views": 100, "retention_rate": 50}
        )
        assert result["status"] == "BLOCKED"
        assert result["error"] == "tenant_mismatch"


def test_authoritative_outcome_keeps_qualified_view_kpi_null_when_missing():
    with application.app_context():
        packet = mendes_outcome_pilot_service.prepare(1)["packet"]
        result = mendes_outcome_pilot_service.evaluate_authoritative_outcome(
            1, packet, {"views": 100, "retention_rate": 50, "shares": 10, "revenue": 20}
        )
        assert result["success"] is True
        assert result["evaluation"]["economics"]["revenue_per_1000_qualified_views"] is None


def test_governance_never_grants_execution():
    with application.app_context():
        result = mendes_outcome_pilot_service.prepare(1)
        governance = result["governance"]
        assert governance["execution_authority"] is False
        assert governance["external_execution"] is False
        assert governance["auto_publish"] is False
        assert governance["mcp"] is False


def test_route_is_registered_and_read_only():
    application.config["WTF_CSRF_ENABLED"] = False
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "1"
        session["_fresh"] = True
    response = client.get("/api/workforce/mendes/outcome-pilot")
    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "APPROVAL_READY"
    assert body["packet"]["governance"]["execution_authority"] is False

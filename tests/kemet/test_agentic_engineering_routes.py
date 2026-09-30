from wsgi import application


def _client():
    application.config["WTF_CSRF_ENABLED"] = False
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "1"
        session["_fresh"] = True
    return client


def test_agentic_contract_route_is_tenant_scoped_and_governed():
    response = _client().post("/api/bos/agentic/contract", json={
        "agent_id": "revenue.research",
        "provider_id": "external-provider",
        "kind": "research",
        "capabilities": ["research", "proposal"],
        "authority": "governed_submission",
    })
    assert response.status_code == 200, response.get_json()
    body = response.get_json()["contract"]
    assert body["provider_id"] == "external-provider"
    assert body["execution_authority"] is False
    assert body["metadata"]["organization_id"] == 1


def test_agentic_contract_route_rejects_external_executor():
    response = _client().post("/api/bos/agentic/contract", json={
        "agent_id": "external.executor",
        "provider_id": "external-provider",
        "kind": "execution_specialist",
        "authority": "canonical_executor",
        "execution_authority": True,
    })
    assert response.status_code == 422
    assert response.get_json()["error"] == "external_agent_execution_authority_forbidden"


def test_agentic_evaluate_route_returns_observability_without_execution():
    response = _client().post("/api/bos/agentic/evaluate", json={
        "lifecycle": {
            "decision_id": "d-route-1",
            "capability_id": "revenue",
            "state": "reviewed",
            "context": {"lead_id": 6},
            "plan": {"steps": 2},
            "proposal": {"action": "sales_follow_up"},
            "governance": {
                "read_only": True,
                "external_execution": False,
                "database_mutation": False,
            },
        }
    })
    assert response.status_code == 200, response.get_json()
    body = response.get_json()["observability"]
    assert body["evaluation"]["status"] == "review"
    assert body["governance"]["external_execution"] is False

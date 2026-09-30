from wsgi import application


def _client():
    application.config["WTF_CSRF_ENABLED"] = False
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "1"
        session["_fresh"] = True
    return client


def test_agentic_context_route_is_read_only_and_tenant_bound(monkeypatch):
    import app.routes.bos_command as routes

    def fake_build(**kwargs):
        assert kwargs["organization_id"] == 1
        return {
            "task_id": kwargs["task_id"],
            "organization_id": 1,
            "sources": [],
            "digest": "digest-1",
            "governance": {
                "read_only": True,
                "external_execution": False,
                "database_mutation": False,
                "auto_execute": False,
                "human_approval_required": True,
            },
        }

    monkeypatch.setattr(routes.evidence_backed_context_service, "build", fake_build)
    response = _client().post("/api/bos/agentic/context", json={
        "query": "pricing policy",
        "task_id": "revenue-task-1",
    })
    assert response.status_code == 200, response.get_json()
    body = response.get_json()["context"]
    assert body["organization_id"] == 1
    assert body["governance"]["external_execution"] is False
    assert body["governance"]["database_mutation"] is False


def test_agentic_context_route_validates_input(monkeypatch):
    import app.routes.bos_command as routes

    monkeypatch.setattr(
        routes.evidence_backed_context_service,
        "build",
        lambda **kwargs: (_ for _ in ()).throw(ValueError("query_required")),
    )
    response = _client().post("/api/bos/agentic/context", json={"task_id": "t"})
    assert response.status_code == 422
    assert response.get_json()["error"] == "query_required"

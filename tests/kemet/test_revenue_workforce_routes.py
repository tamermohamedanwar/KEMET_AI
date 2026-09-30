from wsgi import application


def _client_as_admin():
    application.config["WTF_CSRF_ENABLED"] = False
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "1"
        session["_fresh"] = True
    return client


def test_revenue_workforce_contract_route_is_read_only_and_governed():
    client = _client_as_admin()
    response = client.post("/api/bos/workforce/revenue-contract", json={
        "product": {"name": "Kemet Demo Product"},
        "qualification": {"status": "qualified", "missing_fields": [], "score": 95},
        "lead_id": 6,
        "channel": "web",
    })
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    assert body["contract"] == "Kemet Revenue Workforce"
    assert body["governance"]["read_only"] is True
    assert body["governance"]["external_execution"] is False
    assert body["governance"]["human_approval_required"] is True
    assert body["commercial"]["revenue"] == "not_available"
    assert body["commercial"]["roi"] == "not_proven"


def test_revenue_workforce_route_rejects_unqualified_follow_up_path():
    client = _client_as_admin()
    response = client.post("/api/bos/workforce/revenue-contract", json={
        "product": {"name": "Kemet Demo Product"},
        "qualification": {"status": "needs_information", "missing_fields": ["budget"]},
        "lead_id": 6,
    })
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    assert body["workflow"]["status"] == "blocked"
    assert body["workflow"]["follow_up"]["status"] == "blocked"

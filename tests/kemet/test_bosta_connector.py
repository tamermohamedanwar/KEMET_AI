from wsgi import application


def _client():
    application.config["WTF_CSRF_ENABLED"] = False
    return application.test_client()


def _kwargs():
    return {
        "business_reference": "order-1001",
        "customer": {"firstName": "Ali", "mobile": "01000000000"},
        "shipping_address": {"city": "Cairo", "firstLine": "Test address"},
        "cod": 1250,
        "items": [{"name": "Leather Wallet", "quantity": 1}],
    }


def test_bosta_plan_is_governed_and_fail_closed():
    from app.services.bosta_connector_service import bosta_connector_service

    result = bosta_connector_service.plan_create_delivery(organization_id=1, **_kwargs())
    assert result["status"] == "proposal"
    assert result["governance"]["human_approval_required"] is True
    assert result["governance"]["external_execution"] is False
    assert result["secret_reference"].startswith("secretref_")

    blocked = bosta_connector_service.execute_create_delivery(organization_id=1, **_kwargs())
    assert blocked["error"] == "canonical_execution_required"
    assert blocked["executed"] is False

def test_bosta_canonical_execution_sends_with_tenant_secret(monkeypatch):
    from app.services.bosta_connector_service import bosta_connector_service
    monkeypatch.setenv('KEMET_BOSTA_ORG_1_API_KEY', 'bosta-secret')
    class Response:
        ok = True
        status_code = 201
        def json(self):
            return {'success': True, 'data': {'order': {'_id': 'bosta-order-1', 'trackingNumber': 123456}}}
    captured = {}
    def fake_post(method, url, **kwargs):
        captured.update(kwargs)
        return Response()
    monkeypatch.setattr('app.services.bosta_connector_service.governed_request', fake_post)
    result = bosta_connector_service.execute_create_delivery(
        organization_id=1, approved_execution=True,
        execution_authorization={'execution_key': 'bosta-exec-1'}, **_kwargs()
    )
    assert result['success'] is True
    assert result['order_id'] == 'bosta-order-1'
    assert result['tracking_number'] == 123456
    assert captured['headers']['Authorization'] == 'bosta-secret'


def test_bosta_webhook_is_durable_and_idempotent(monkeypatch):
    monkeypatch.setenv('KEMET_BOSTA_WEBHOOK_SECRET', 'bosta-webhook-secret')
    client = _client()
    payload = {'_id': 'bosta-order-2', 'trackingNumber': 654321, 'state': 45,
               'type': 'SEND', 'businessReference': 'order-1002', 'timeStamp': 1770000000}
    headers = {'Authorization': 'bosta-webhook-secret'}
    first = client.post('/api/bos/fulfillment/bosta/webhook/1', json=payload, headers=headers)
    second = client.post('/api/bos/fulfillment/bosta/webhook/1', json=payload, headers=headers)
    assert first.status_code == 200, first.get_json()
    assert first.get_json()['tracking']['state_name'] == 'delivered'
    assert second.status_code == 200, second.get_json()
    assert second.get_json()['status'] == 'deduplicated'


def test_bosta_webhook_rejects_missing_secret(monkeypatch):
    monkeypatch.setenv('KEMET_BOSTA_WEBHOOK_SECRET', 'bosta-webhook-secret')
    response = _client().post('/api/bos/fulfillment/bosta/webhook/1', json={'_id': 'x', 'state': 45})
    assert response.status_code == 403


def test_bosta_tracking_binds_to_existing_execution_evidence():
    from app import create_app, db
    from app.core.execution_evidence import execution_evidence
    from app.services.bosta_connector_service import bosta_connector_service

    app = create_app()
    with app.app_context():
        execution_evidence.record(
            organization_id=1,
            execution_key='bosta-exec-binding',
            job_id=9012,
            stage='runtime.finished',
            status='completed',
            evidence_key='bosta-exec-binding:runtime.finished',
            receipt={'provider': 'bosta_api', 'order_id': 'bosta-order-bind', 'tracking_number': '778899'},
        )
        event = bosta_connector_service.normalize_tracking_event(
            organization_id=1,
            payload={'_id': 'bosta-order-bind', 'trackingNumber': '778899', 'state': 45,
                     'businessReference': 'order-bind', 'timeStamp': 1770000001},
        )
        binding = bosta_connector_service.record_tracking_evidence(organization_id=1, event=event)
        db.session.commit()

    assert binding['execution_key'] == 'bosta-exec-binding'
    assert binding['job_id'] == 9012


def test_bosta_tracking_unknown_execution_does_not_create_execution_authority():
    from app import create_app
    from app.services.bosta_connector_service import bosta_connector_service

    app = create_app()
    with app.app_context():
        event = bosta_connector_service.normalize_tracking_event(
            organization_id=1,
            payload={'_id': 'unbound-order', 'trackingNumber': '112233', 'state': 30,
                     'businessReference': 'unbound', 'timeStamp': 1770000002},
        )
        binding = bosta_connector_service.record_tracking_evidence(organization_id=1, event=event)

    assert binding['execution_key'] is None
    assert binding['correlation'] is None


def test_bosta_execution_disables_redirect_following(monkeypatch):
    from app.services.bosta_connector_service import BostaConnectorService
    service = BostaConnectorService()
    monkeypatch.setattr("app.services.bosta_connector_service.resolve_secret", lambda *args, **kwargs: "secret")
    monkeypatch.setattr("app.services.bosta_connector_service.connector_registry.allows", lambda *args, **kwargs: True)
    captured = {}
    class Response:
        ok = True
        status_code = 200
        def json(self):
            return {"data": {"order": {"_id": "bosta-1"}}}
    def fake_post(*args, **kwargs):
        captured.update(kwargs)
        return Response()
    monkeypatch.setattr("app.services.bosta_connector_service.governed_request", fake_post)
    result = service.execute_create_delivery(
        organization_id=7, approved_execution=True, execution_authorization={"ok": True},
        business_reference="ref-1", customer={"firstName": "A", "mobile": "01000000000"},
        shipping_address={"city": "Cairo"}, cod=10, items=[{"name": "x"}],
    )
    assert result["success"] is True
    assert captured["allow_redirects"] is False

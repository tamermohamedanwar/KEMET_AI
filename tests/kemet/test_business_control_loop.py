def test_business_control_loop_requires_organization():
    from app.services.business_control_loop import business_control_loop

    result = business_control_loop.build(None, [])
    assert result["success"] is False
    assert result["error"] == "organization_required"


def test_business_control_loop_exposes_governed_policy():
    from app import create_app
    from app.services.business_control_loop import business_control_loop

    app = create_app()
    with app.app_context():
        result = business_control_loop.build(7, [])
    assert result["success"] is True
    assert result["engine"] == "kemet_business_control_loop"
    assert result["control_policy"]["auto_execute"] is False
    assert result["control_policy"]["human_approval_required"] is True
    assert result["governance"]["database_mutation"] is False
    assert result["decision_intelligence"]["enabled"] is True


def test_business_control_loop_has_full_lifecycle_states():
    from app.services.business_control_loop import BusinessControlLoopService

    assert BusinessControlLoopService.STATES == (
        "detected",
        "ranked",
        "reviewed",
        "approved",
        "executed",
        "outcome_observed",
    )


def test_business_control_loop_route_supports_get_and_post():
    from app import create_app

    app = create_app()
    routes = {rule.rule: sorted(rule.methods) for rule in app.url_map.iter_rules()}
    assert "/api/bos/business-control-loop" in routes
    assert "GET" in routes["/api/bos/business-control-loop"]
    assert "POST" in routes["/api/bos/business-control-loop"]


def test_business_control_loop_integrates_cross_channel_learning(monkeypatch):
    from app.services.business_control_loop import business_control_loop

    monkeypatch.setattr(
        "app.services.business_control_loop.cross_channel_outcome_learning.build",
        lambda organization_id, execution_keys=None, period="30d": {
            "success": True,
            "status": "LEARNING_READY",
            "learning_digest": "d" * 64,
            "learning": {
                "next_action": "review_observed_outcomes",
                "cross_channel_comparison": "descriptive_only",
            },
            "governance": {"read_only": True, "external_execution": False, "causal_claim": False},
        },
    )
    result = business_control_loop.build(7, [], execution_keys=["exec-1"])

    section = result["cross_channel_outcome_learning"]
    assert section["enabled"] is True
    assert section["status"] == "LEARNING_READY"
    assert section["next_action"] == "review_observed_outcomes"
    assert section["comparison"] == "descriptive_only"
    assert section["governance"]["external_execution"] is False



def test_business_control_loop_route_forwards_execution_keys(monkeypatch):
    from flask_login import login_user
    from app import db
    from app.models.user import User
    from wsgi import application

    application.config["WTF_CSRF_ENABLED"] = False
    captured = {}
    monkeypatch.setattr(
        "app.routes.bos_command.BusinessControlLoopService.build",
        lambda organization_id, decisions=None, period="30d", execution_keys=None, revenue_intelligence=None: captured.update({
            "organization_id": organization_id,
            "period": period,
            "execution_keys": execution_keys,
            "revenue_intelligence": revenue_intelligence,
        }) or {"success": True},
    )
    monkeypatch.setattr(
        "app.routes.bos_command.BOSIntelligenceService.get_decisions",
        lambda organization_id, limit=10: [],
    )

    with application.app_context():
        user = User(
            organization_id=11,
            full_name="Control Loop Test",
            email="control-loop-route@example.com",
            password_hash="x",
        )
        db.session.add(user)
        db.session.commit()
        with application.test_request_context():
            login_user(user)
            from app.routes.bos_command import bos_business_control_loop
            from flask import request
            with application.test_client() as client:
                with client.session_transaction() as session:
                    session["_user_id"] = str(user.id)
                    session["_fresh"] = True
                response = client.post(
                    "/api/bos/business-control-loop",
                    json={"period": "30d", "execution_keys": ["exec-1", "", "exec-2"]},
                )
        db.session.delete(user)
        db.session.commit()

    assert response.status_code == 200
    assert captured["organization_id"] == 11
    assert captured["execution_keys"] == ["exec-1", "exec-2"]


def test_business_control_loop_integrates_revenue_decision_signals(monkeypatch):
    from app.services.business_control_loop import business_control_loop

    captured = {}

    def fake_signals(*, organization_id, intelligence=None):
        captured["organization_id"] = organization_id
        captured["intelligence"] = intelligence
        return {
            "success": True,
            "signals": {
                "verified_revenue": 125.0,
                "verified_content_count": 1,
                "authoritatively_measured_content_count": 1,
            },
            "decision_support": {
                "basis": "reconciled_payment_identity_plus_authoritative_measurement",
            },
        }

    monkeypatch.setattr(
        "app.services.business_control_loop.revenue_content_decision_signal_service.build",
        fake_signals,
    )
    from app import create_app
    with create_app().app_context():
        result = business_control_loop.build(
            7,
            [],
            revenue_intelligence={"records": [{"content_id": "c1"}]},
        )
    section = result["revenue_decision_signals"]
    assert section["enabled"] is True
    assert section["verified_revenue"] == 125.0
    assert section["verified_content_count"] == 1
    assert section["automatic_action"] is False
    assert section["external_action"] is False
    assert captured["organization_id"] == 7
    assert captured["intelligence"]["records"][0]["content_id"] == "c1"


def test_business_control_loop_defaults_to_empty_revenue_evidence(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        "app.services.business_control_loop.revenue_content_decision_signal_service.build",
        lambda **kwargs: captured.update(kwargs) or {
            "success": True,
            "signals": {"verified_revenue": 0.0, "verified_content_count": 0, "authoritatively_measured_content_count": 0},
            "decision_support": {"basis": "reconciled_payment_identity_plus_authoritative_measurement"},
        },
    )
    from app.services.business_control_loop import business_control_loop
    from app import create_app
    with create_app().app_context():
        result = business_control_loop.build(7, [])
    assert result["revenue_decision_signals"]["verified_revenue"] == 0.0
    assert captured["intelligence"] == {"records": []}


def test_business_control_loop_route_forwards_revenue_intelligence(monkeypatch):
    from flask_login import login_user
    from app import db
    from app.models.user import User
    from wsgi import application

    application.config["WTF_CSRF_ENABLED"] = False
    captured = {}
    monkeypatch.setattr(
        "app.routes.bos_command.BusinessControlLoopService.build",
        lambda organization_id, decisions=None, period="30d", execution_keys=None, revenue_intelligence=None: captured.update({
            "organization_id": organization_id,
            "revenue_intelligence": revenue_intelligence,
        }) or {"success": True},
    )
    monkeypatch.setattr(
        "app.routes.bos_command.BOSIntelligenceService.get_decisions",
        lambda organization_id, limit=10: [],
    )

    with application.app_context():
        user = User(
            organization_id=12,
            full_name="Revenue Signal Route Test",
            email="revenue-signal-route@example.com",
            password_hash="x",
        )
        db.session.add(user)
        db.session.commit()
        with application.test_client() as client:
            with client.session_transaction() as session:
                session["_user_id"] = str(user.id)
                session["_fresh"] = True
            response = client.post(
                "/api/bos/business-control-loop",
                json={"revenue_intelligence": {"records": [{"content_id": "c1"}]}},
            )
        db.session.delete(user)
        db.session.commit()

    assert response.status_code == 200
    assert captured["organization_id"] == 12
    assert captured["revenue_intelligence"]["records"][0]["content_id"] == "c1"

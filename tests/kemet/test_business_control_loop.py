def test_business_control_loop_requires_organization():
    from app.services.business_control_loop import business_control_loop

    result = business_control_loop.build(None, [])
    assert result["success"] is False
    assert result["error"] == "organization_required"


def test_business_control_loop_exposes_governed_policy():
    from app.services.business_control_loop import business_control_loop

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

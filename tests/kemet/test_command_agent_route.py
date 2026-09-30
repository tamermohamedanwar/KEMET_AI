from __future__ import annotations

import pytest

from app import db
from app.core.agent_reasoning import AgentDecision
from app.models.user import User


@pytest.fixture(autouse=True)
def app_context():
    from wsgi import application
    with application.app_context():
        yield


def test_command_agent_route_uses_canonical_runtime(monkeypatch):
    from flask_login import login_user
    from wsgi import application
    from app.routes.command_agent import command_agent

    with application.app_context():
        user = User(
            organization_id=11,
            full_name="Test User",
            email="agent-route@example.com",
            password_hash="x",
        )
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    class FakeRun:
        organization_id = 11
        run_id = "agent-test"
        state = "approve"
        instruction = "grow revenue"
        classification = {"task_type": "research"}
        plan = {
            "plan_hash": "hash",
            "steps": [
                {
                    "step_id": "step-1",
                    "objective": "analyze revenue",
                    "action": "business_insights",
                    "risk": "low",
                    "requires_approval": True,
                    "parameters": {},
                }
            ],
        }
        simulation = {"simulation": True, "executed": False}
        decision = None
        evidence = ()
        outcome = None
        learning = None
        next_action = "request_human_approval"
        evidence_context_hash = "ctx"

    class FakeRuntime:
        def ask(self, instruction, *, organization_id, user_id):
            assert instruction == "grow revenue"
            assert organization_id == 11
            assert user_id == user_id_expected
            return FakeRun()

        def reason(self, run):
            return run, AgentDecision(
                "grow revenue", "revenue", ("revenue",), "revenue_intelligence",
                "revenue signal", 0.9,
            )

    user_id_expected = user_id
    monkeypatch.setattr("app.routes.command_agent.kemet_agent_runtime", FakeRuntime())

    with application.test_request_context(
        "/api/command-agent",
        method="POST",
        json={"instruction": "grow revenue"},
    ):
        login_user(user)
        response = command_agent()
        payload = response[0].get_json() if isinstance(response, tuple) else response.get_json()
        status = response[1] if isinstance(response, tuple) else 200

    assert status == 200, payload
    assert payload["engine"] == "kemet_agent_runtime"
    assert payload["decision"]["specialist"] == "revenue"
    assert payload["decision"]["tool"] == "revenue_intelligence"
    assert payload["executed"] is False
    assert payload["canonical_execution_runtime"] is True

def test_command_agent_approval_transitions_queue_to_queued(monkeypatch):
    from flask_login import login_user
    from wsgi import application
    from app.routes.command_agent import command_agent, approve_command_agent
    from app.models.automation_queue import AutomationQueueJob

    with application.app_context():
        user = User(
            organization_id=11,
            full_name="Approval Test User",
            email="agent-approval-route@example.com",
            password_hash="x",
        )
        db.session.add(user)
        db.session.commit()
        expected_user_id = user.id

    class FakeRun:
        organization_id = 11
        run_id = "agent-approval-test"
        state = "approve"
        instruction = "grow revenue"
        classification = {"task_type": "research"}
        plan = {
            "plan_hash": "approval-plan-hash",
            "workflow_id": "agent:agent-approval-test",
            "steps": [
                {
                    "step_id": "step-1",
                    "objective": "analyze revenue",
                    "action": "business_insights",
                    "risk": "low",
                    "requires_approval": True,
                    "parameters": {},
                }
            ],
        }
        simulation = {"simulation": True, "executed": False}
        decision = None
        evidence = ()
        outcome = None
        learning = None
        next_action = "request_human_approval"
        evidence_context_hash = "approval-context"

    class FakeRuntime:
        def ask(self, instruction, *, organization_id, user_id):
            assert instruction == "grow revenue"
            assert organization_id == 11
            assert user_id == expected_user_id
            return FakeRun()

        def reason(self, run):
            return run, AgentDecision(
                "grow revenue",
                "revenue",
                ("revenue",),
                "revenue_intelligence",
                "revenue signal",
                0.9,
            )

    monkeypatch.setattr(
        "app.routes.command_agent.kemet_agent_runtime",
        FakeRuntime(),
    )

    with application.test_request_context(
        "/api/command-agent",
        method="POST",
        json={"instruction": "grow revenue"},
    ):
        login_user(user)
        response = command_agent()
        payload = (
            response[0].get_json()
            if isinstance(response, tuple)
            else response.get_json()
        )
        status = response[1] if isinstance(response, tuple) else 200

    assert status == 200, payload
    assert payload["approval_required"] is True
    assert payload["executed"] is False
    assert payload["approval"]["approval_status"] == "pending"

    approval_id = payload["approval"]["approval_id"]
    job_id = payload["approval"]["job_id"]

    with application.test_request_context(
        f"/api/command-agent/approvals/{approval_id}/approve",
        method="POST",
    ):
        login_user(user)
        response = approve_command_agent(approval_id)
        approval_payload = (
            response[0].get_json()
            if isinstance(response, tuple)
            else response.get_json()
        )
        approval_status = (
            response[1] if isinstance(response, tuple) else 200
        )

    assert approval_status == 200, approval_payload
    assert approval_payload["ok"] is True
    assert approval_payload["result"]["success"] is True

    with application.app_context():
        job = db.session.get(AutomationQueueJob, job_id)
        assert job is not None
        assert job.organization_id == 11
        assert job.status == "queued"
        assert job.workflow_state == "queued"


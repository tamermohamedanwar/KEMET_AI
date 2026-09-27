from __future__ import annotations

import pytest

from app.core.agent_runtime import AgentRuntimeState, KemetAgentRuntime


def test_agent_tracing_records_run_stage_without_execution_authority(monkeypatch):
    events = []

    class FakeSpan:
        def set_attribute(self, key, value):
            events.append((key, value))

        def end(self):
            events.append(("ended", True))

    monkeypatch.setattr(
        "app.core.agent_runtime.application_telemetry.tracer.start_span",
        lambda name: (events.append(("span", name)) or FakeSpan()),
    )

    run = KemetAgentRuntime().ask("review project health", organization_id=11)
    assert ("span", "kemet.agent.run") in events
    assert ("kemet.agent.run_id", run.run_id) in events
    assert ("kemet.agent.stage", "ask") in events
    assert ("kemet.organization_id", 11) in events
    assert ("ended", True) in events
    assert KemetAgentRuntime().status()["tracing"] is True


@pytest.fixture(autouse=True)
def app_context():
    from wsgi import application
    with application.app_context():
        yield


def test_status_exposes_single_governed_lifecycle():
    status = KemetAgentRuntime().status()
    assert status["engine"] == "kemet_agent_runtime"
    assert status["canonical_execution_runtime"] is True
    assert status["approval_required_for_side_effects"] is True
    assert status["one_time_authorization"] is True
    assert status["parallel_executor"] is False
    assert status["mcp"] is False
    assert status["lifecycle"] == [
        "ask", "plan", "simulate", "reason", "guard", "approve",
        "execute", "verify", "evidence", "outcome", "learn", "next_action", "replay"
    ]


def test_ask_builds_context_plan_and_simulation():
    run = KemetAgentRuntime().ask("create a governed automation plan", organization_id=7, user_id=12)
    assert run.organization_id == 7
    assert run.state == AgentRuntimeState.APPROVE
    assert run.plan["plan_hash"]
    assert run.evidence_context_hash
    assert run.simulation["simulation"] is True
    assert run.simulation["executed"] is False
    assert run.next_action == "request_human_approval"


def test_ask_is_deterministic_for_same_instruction_and_tenant():
    runtime = KemetAgentRuntime()
    first = runtime.ask("review project health", organization_id=9)
    second = runtime.ask("review project health", organization_id=9)
    assert first.run_id == second.run_id
    assert first.plan["plan_hash"] == second.plan["plan_hash"]


def test_tenant_identity_is_required():
    with pytest.raises(ValueError, match="organization_id_required"):
        KemetAgentRuntime().ask("review project health", organization_id=0)


def test_empty_instruction_is_rejected():
    with pytest.raises(ValueError, match="instruction_required"):
        KemetAgentRuntime().ask("   ", organization_id=1)


def test_execute_requires_approval_state():
    runtime = KemetAgentRuntime()
    run = runtime.ask("explain why revenue changed", organization_id=1)
    assert run.state == AgentRuntimeState.REVIEW
    with pytest.raises(ValueError, match="agent_run_not_awaiting_approval"):
        runtime.execute_approved(run, authorization={})


def test_execute_requires_authorization():
    runtime = KemetAgentRuntime()
    run = runtime.ask("create a governed automation", organization_id=1)
    with pytest.raises(ValueError, match="execution_authorization_required"):
        runtime.execute_approved(run, authorization=None)


def test_side_effect_plan_never_executes_during_ask():
    run = KemetAgentRuntime().ask("send a notification", organization_id=1)
    assert run.state == AgentRuntimeState.APPROVE
    assert run.execution is None
    assert run.simulation["executed"] is False
    assert run.plan["requires_approval"] is True


def test_execute_uses_canonical_runtime_and_closes_evidence_outcome_learning(monkeypatch):
    runtime = KemetAgentRuntime()
    run = runtime.ask("create a governed automation", organization_id=3)
    captured = {}

    def fake_execute(**kwargs):
        captured.update(kwargs)
        return {
            "success": True,
            "status": "completed",
            "executed": True,
            "execution_status": "completed",
            "runtime": "canonical",
        }

    monkeypatch.setattr("app.core.agent_runtime.canonical_execution_runtime.execute", fake_execute)
    result = runtime.execute_approved(run, authorization={"execution_key": "one-time-test"})

    assert result.state == AgentRuntimeState.NEXT_ACTION
    assert result.execution["runtime"] == "canonical"
    assert result.evidence
    assert result.evidence[0]["digest"]
    assert result.outcome["objective_match"] is True
    assert result.outcome["authoritative"] is True
    assert result.learning["next_action"] == "measure_real_outcome"
    assert captured["plan"]["runtime"] == "kemet_agent_runtime"
    assert captured["action_registry"] is not None
    assert captured["authorization"]["execution_key"] == "one-time-test"


def test_verify_blocks_claim_of_authoritative_evidence_when_execution_is_not_complete():
    runtime = KemetAgentRuntime()
    run = runtime.ask("create a governed automation", organization_id=3)
    blocked = runtime._replace(
        run,
        execution={"success": True, "status": "pending", "executed": False},
        evidence=({"digest": "internal"},),
    )
    verified = runtime.verify(blocked)
    assert verified.state == AgentRuntimeState.VERIFY
    assert verified.outcome["authoritative"] is False
    assert verified.outcome["evidence_quality"] == "verified_internal"
    assert verified.next_action == "obtain_authoritative_evidence"


def test_replay_requires_fresh_authorization_path():
    runtime = KemetAgentRuntime()
    run = runtime.ask("create a governed automation", organization_id=3)
    replay = runtime.replay(run)
    assert replay.state == AgentRuntimeState.REPLAY
    assert replay.next_action == "fresh_authorization_required"


def test_agent_runtime_keeps_external_execution_authority_false():
    assert KemetAgentRuntime().status()["external_execution_authority"] is False

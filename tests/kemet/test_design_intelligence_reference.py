from app.services.design_intelligence_reference import design_intelligence_reference
from wsgi import application


def _client_as_admin():
    application.config["WTF_CSRF_ENABLED"] = False
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "1"
        session["_fresh"] = True
    return client


def test_inspo_reference_becomes_governed_evidence():
    with application.app_context():
        result = design_intelligence_reference.build_reference_evidence(
            1, "https://inspomcp.dev/", "Inspo reference archive",
            macrostructure="bento_grid",
            observations=["strong hierarchy", "responsive composition"],
            provenance={"source": "official_archive"},
        )
    assert result["status"] == "READY_FOR_REVIEW"
    assert result["schema"] == "kemet.design_intelligence_reference.v1"
    assert result["governance"]["reference_only"] is True
    assert result["governance"]["mcp_dependency"] is False
    assert result["evidence"]["copy_code"] is False
    assert result["evidence_digest"]


def test_untrusted_reference_is_fail_closed():
    with application.app_context():
        result = design_intelligence_reference.build_reference_evidence(
            1, "https://example.com/", "Unknown reference"
        )
    assert result["status"] == "BLOCKED"
    assert result["error"] == "untrusted_reference_source"


def test_design_contract_binds_business_ux_and_evidence():
    reference = {
        "source_url": "https://inspomcp.dev/", "title": "Reference",
        "evidence_digest": "abc123", "macrostructure": "dashboard",
        "observations": ["task clarity"],
    }
    with application.app_context():
        result = design_intelligence_reference.build_design_contract(
            1, "Make business decisions visible and actionable",
            ux_constraints={"mobile_first": True, "rtl": True},
            references=[reference],
        )
    assert result["status"] == "READY_FOR_REVIEW"
    assert result["schema"] == "kemet.design_contract.v1"
    assert result["contract"]["business_objective"]
    assert result["contract"]["design_intent"]["rtl_ready"] is True
    assert result["contract"]["accessibility"]["standard"] == "WCAG 2.2"
    assert result["contract"]["implementation_rules"]["do_not_copy_third_party_code"] is True
    assert result["contract_digest"]


def test_design_contract_rejects_untrusted_reference():
    with application.app_context():
        result = design_intelligence_reference.build_design_contract(
            1, "Improve onboarding",
            references=[{"source_url": "http://bad.example/"}],
        )
    assert result["status"] == "BLOCKED"


def test_ai_design_strategist_is_advisory_only():
    with application.app_context():
        result = design_intelligence_reference.strategist_preview(
            1, "Clarify the next business action",
            ux_constraints={"mobile_first": True},
            references=[{
                "source_url": "https://inspomcp.dev/", "title": "Reference",
                "evidence_digest": "digest", "macrostructure": "bento_grid",
            }],
        )
    assert result["status"] == "REVIEW_REQUIRED"
    assert result["role"]["id"] == "ai_design_strategist"
    assert result["role"]["authority"] == "advisory_only"
    assert result["execution_authority"] is False
    assert result["external_execution"] is False
    assert result["mcp"] is False


def test_design_intelligence_routes_are_review_only():
    client = _client_as_admin()
    payload = {
        "business_objective": "Improve task clarity",
        "ux_constraints": {"mobile_first": True, "rtl": True},
        "references": [{
            "source_url": "https://inspomcp.dev/", "title": "Inspo",
            "evidence_digest": "digest", "macrostructure": "dashboard",
        }],
    }
    reference = client.post(
        "/api/workforce/design-intelligence/reference",
        json={"source_url": "https://inspomcp.dev/", "title": "Inspo"},
    )
    contract = client.post("/api/workforce/design-intelligence/contract", json=payload)
    strategist = client.post("/api/workforce/design-intelligence/strategist/preview", json=payload)
    assert reference.status_code == 200
    assert contract.status_code == 200
    assert strategist.status_code == 200
    assert strategist.get_json()["execution_authority"] is False

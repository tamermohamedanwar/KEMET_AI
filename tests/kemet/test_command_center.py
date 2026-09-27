from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_command_center_template_exists():
    path = ROOT / "app" / "templates" / "admin" / "command_center.html"
    assert path.exists()
    assert path.stat().st_size > 0


def test_command_center_route_exists():
    path = ROOT / "app" / "routes" / "bos_command_center.py"
    text = path.read_text(encoding="utf-8")
    assert "/admin/automation/command-center" in text


def test_command_api_exists():
    path = ROOT / "app" / "routes" / "bos_command.py"
    text = path.read_text(encoding="utf-8")
    assert "/command" in text


def test_existing_bos_intelligence_exists():
    path = ROOT / "app" / "services" / "bos_intelligence.py"
    assert path.exists()


def test_existing_orchestrator_exists():
    path = ROOT / "app" / "automation" / "orchestrator.py"
    assert path.exists()


def test_command_center_integrates_sales_support_snapshot():
    template = (ROOT / "app" / "templates" / "admin" / "command_center.html").read_text(encoding="utf-8")
    route = (ROOT / "app" / "routes" / "command_center.py").read_text(encoding="utf-8")
    assert '/command-center/api/bos/sales-support' in template
    assert 'id="salesSupportPanel"' in template
    assert 'salesSupportTopLead' in template
    assert '@command_center_bp.get("/api/bos/sales-support")' in route
    assert 'sales_support_command_center.snapshot' in route

def test_command_center_exposes_distribution_preview():
    route = (ROOT / "app" / "routes" / "command_center.py").read_text(encoding="utf-8")
    assert '@command_center_bp.get("/api/bos/distribution")' in route
    assert 'distribution_service.preview_sales' in route
    assert 'database_mutation' in (ROOT / "app" / "services" / "distribution_service.py").read_text(encoding="utf-8")


def test_command_center_plan_exposes_tool_intelligence_advice():
    route = (ROOT / "app" / "routes" / "command_center.py").read_text(encoding="utf-8")
    assert 'tool_intelligence_registry' in route
    assert '"tool_intelligence": tool_recommendations' in route
    assert 'canonical_runtime_only' in (ROOT / "app" / "services" / "tool_intelligence_registry.py").read_text(encoding="utf-8")


def test_command_center_exposes_governed_follow_up_preview():
    route = (ROOT / "app" / "routes" / "command_center.py").read_text(encoding="utf-8")
    assert '@command_center_bp.get("/api/bos/sales-support/follow-up")' in route
    assert 'governed_followup_service.build_plan' in route
    assert 'lead_organization_mismatch' in route


def test_command_center_exposes_governed_distribution_workflow():
    template = (ROOT / "app" / "templates" / "admin" / "command_center.html").read_text(encoding="utf-8")
    route = (ROOT / "app" / "routes" / "command_center.py").read_text(encoding="utf-8")
    assert 'id="socialDistributionPanel"' in template
    assert 'id="distributionPlanBtn"' in template
    assert '/command-center/api/bos/social-distribution/plan' in template
    assert '@command_center_bp.post("/api/bos/social-distribution/plan")' in route
    assert 'social_distribution_hub.plan' in route
    assert '"executed": False' in route




def test_revenue_routes_require_server_derived_evidence_bindings():
    route = (ROOT / "app" / "routes" / "command_center.py").read_text(encoding="utf-8")
    assert 'def _server_verified_revenue_portfolio' in route
    assert 'content_commercial_loop_service.evaluate_verified' in route
    assert '@command_center_bp.post("/api/bos/revenue-portfolio")' in route
    assert '@command_center_bp.post("/api/bos/growth-experiment-proposals")' in route


def test_growth_approval_package_is_not_client_proposal_authoritative():
    route = (ROOT / "app" / "routes" / "command_center.py").read_text(encoding="utf-8")
    start = route.index('@command_center_bp.post("/api/bos/growth-experiment-approval-package")')
    end = route.index('@command_center_bp.post("/api/bos/growth-experiment-approve")', start)
    block = route[start:end]
    assert 'payload.get("proposal")' not in block
    assert '_server_verified_revenue_portfolio' in block
    assert 'growth_experiment_proposal_service.propose' in block
    assert 'server_verified_proposal_not_found' in block

def test_command_center_exposes_tenant_bound_approval_review_route():
    route = (ROOT / "app" / "routes" / "command_center.py").read_text(encoding="utf-8")
    assert '@command_center_bp.get("/api/approvals/<int:approval_id>/review")' in route
    assert 'filter_by(id=int(approval_id), organization_id=int(organization_id))' in route
    assert '"review_only": True' in route


def test_approval_review_contract_exposes_governance_identity_fields():
    route = (ROOT / "app" / "routes" / "command_center.py").read_text(encoding="utf-8")
    for field in (
        '"approval_id"', '"organization_id"', '"workflow_id"',
        '"execution_id"', '"risk_level"', '"plan_hash"',
        '"decision_hash"', '"execution_key"', '"evidence_reference"',
        '"authorization_status"', '"requires_human_approval"',
    ):
        assert field in route


def test_phase28_content_studio_contract_is_integrated():
    template = (ROOT / "app" / "templates" / "command_center.html").read_text(encoding="utf-8")
    route = (ROOT / "app" / "routes" / "command_center.py").read_text(encoding="utf-8")
    assert 'id="contentStudioPanel"' in template
    assert 'data-surface="content"' in template
    assert 'id="studioBuildBtn"' in template
    assert 'id="studioApproveBtn"' in template
    assert 'id="studioPublishBtn"' in template
    assert '@command_center_bp.post("/api/bos/content-studio/approve")' in route
    assert '@command_center_bp.post("/api/bos/content-studio/publishing-intent")' in route
    assert 'content_social_governance_service.build_asset' in route
    assert 'validate_approval_for_publish' in route


def test_phase28_content_studio_refuses_placeholder_target_accounts():
    route = (ROOT / "app" / "routes" / "command_center.py").read_text(encoding="utf-8")
    assert 'verified_target_account_required' in route
    assert 'account_ref.endswith("-account")' in route
    assert '"external_execution": False' in route


def test_phase28_content_studio_preserves_no_mcp_boundary():
    template = (ROOT / "app" / "templates" / "command_center.html").read_text(encoding="utf-8")
    route = (ROOT / "app" / "routes" / "command_center.py").read_text(encoding="utf-8")
    assert 'contentStudioPanel' in template
    assert 'mcp' not in route.lower().split('content-studio')[0][-500:]

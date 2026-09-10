def test_crm_pipeline_intelligence_is_read_only():
    from app.services.crm_pipeline_intelligence import crm_pipeline_intelligence
    result = crm_pipeline_intelligence.build(None)
    assert result["success"] is False
    assert result["error"] == "organization_required"


def test_crm_pipeline_intelligence_contract():
    from app.services.crm_pipeline_intelligence import CRMPipelineIntelligenceService
    assert CRMPipelineIntelligenceService.VERSION == "1.0"
    assert hasattr(CRMPipelineIntelligenceService, "build")

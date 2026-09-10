from app.models.demo_lead import DemoLead
from app.services.lead_scoring_service import score_lead


class CRMPipelineIntelligenceService:
    VERSION = "1.0"

    @staticmethod
    def build(organization_id):
        if not organization_id:
            return {"success": False, "error": "organization_required"}

        leads = (
            DemoLead.query
            .filter(DemoLead.organization_id == organization_id)
            .order_by(DemoLead.lead_score.desc(), DemoLead.created_at.desc())
            .all()
        )
        stages = {key: 0 for key in ("new", "contacted", "qualified", "proposal", "won", "lost")}
        value = {key: 0.0 for key in stages}
        ranked = []
        for lead in leads:
            status = (lead.status or "new").lower()
            status = "won" if status == "converted" else status
            if status not in stages:
                status = "new"
            stages[status] += 1
            value[status] += float(lead.estimated_value or 0)
            scored = score_lead(lead)
            ranked.append({
                "id": lead.id,
                "company_name": lead.company_name or "Unnamed Lead",
                "status": status,
                "score": scored.get("score", lead.lead_score or 0),
                "temperature": scored.get("temperature", "cold"),
                "estimated_value": float(lead.estimated_value or 0),
            })

        ranked.sort(key=lambda item: (float(item["score"] or 0), item["estimated_value"]), reverse=True)
        total = len(leads)
        won = stages["won"]
        return {
            "success": True,
            "engine": "kemet_crm_pipeline_intelligence",
            "version": CRMPipelineIntelligenceService.VERSION,
            "organization_id": organization_id,
            "summary": {"total": total, "won": won, "conversion_rate": round(won / total * 100, 2) if total else 0},
            "stages": stages,
            "stage_value": value,
            "top_leads": ranked[:10],
            "governance": {"read_only": True, "advisory": True, "external_execution": False, "database_mutation": False, "auto_execute": False},
        }


crm_pipeline_intelligence = CRMPipelineIntelligenceService()

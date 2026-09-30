from typing import Any, Mapping

from app.services.commerce_revenue_workflow_service import commerce_revenue_workflow_service
from app.services.evidence_backed_context_service import evidence_backed_context_service


class RevenueWorkforceContract:
    VERSION = "1.0"
    NAME = "Kemet Revenue Workforce"

    ROLES = (
        "research",
        "marketing",
        "creative",
        "lead_capture",
        "qualification",
        "sales_decision",
        "follow_up",
        "outcome_learning",
    )

    def build(self, *, organization_id: int, product: Mapping[str, Any],
              qualification: Mapping[str, Any], lead_id: Any = None,
              customer_id: Any = None, channel: str = "web",
              audience: str = "", style: str = "", language: str = "ar",
              context_query: str | None = None, task_id: str | None = None,
              context_limit: int = 5) -> dict[str, Any]:
        if not organization_id:
            raise ValueError("organization_id_required")
        context = None
        if context_query or task_id:
            if not context_query or not task_id:
                raise ValueError("context_query_and_task_id_required")
            context = evidence_backed_context_service.build(
                organization_id=int(organization_id),
                query=context_query,
                task_id=task_id,
                limit=context_limit,
                source_metadata={"channel": channel, "workforce": self.NAME},
            )
        workflow = commerce_revenue_workflow_service.build_plan(
            organization_id=organization_id,
            product=product,
            qualification=qualification,
            lead_id=lead_id,
            customer_id=customer_id,
            channel=channel,
            audience=audience,
            style=style,
            language=language,
        )
        if context is not None:
            workflow["evidence_context"] = {
                "digest": context.get("digest"),
                "query_digest": context.get("query_digest"),
                "evidence_count": len(context.get("sources") or []),
                "excluded_untrusted": int((context.get("retrieval") or {}).get("excluded", 0) or 0),
                "references": [
                    {
                        "filename": source.get("filename"),
                        "chunk_index": source.get("chunk_index"),
                        "content_digest": source.get("content_digest"),
                    }
                    for source in context.get("sources") or []
                ],
            }
        return {
            "success": True,
            "contract": self.NAME,
            "version": self.VERSION,
            "organization_id": int(organization_id),
            "roles": list(self.ROLES),
            "workforce_mode": "specialist_proposal_then_governed_execution",
            "authority": {
                "specialists": "propose_reason_research_prepare",
                "kemet": "decide_approve_execute_measure_audit",
            },
            "lifecycle": [
                "intent", "research", "creative", "lead_capture",
                "qualification", "sales_decision", "follow_up_proposal",
                "human_approval", "governed_execution", "outcome",
                "recorded_revenue", "roi_when_proven", "learning",
            ],
            "workflow": workflow,
            "governance": {
                "read_only": True,
                "advisory": True,
                "database_mutation": False,
                "external_execution": False,
                "auto_execute": False,
                "human_approval_required": True,
                "tenant_scoped": True,
                "fail_closed": True,
            },
            "commercial": {
                "revenue": "not_available",
                "roi": "not_proven",
                "causal_claim": False,
            },
        }


revenue_workforce_contract = RevenueWorkforceContract()

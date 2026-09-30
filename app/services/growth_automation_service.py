from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any


@dataclass(frozen=True)
class GrowthPlaybook:
    playbook_id: str
    name: str
    objective: str
    discovery_sources: tuple[str, ...]
    actions: tuple[str, ...]
    risk: str


class GrowthAutomationService:
    VERSION = "1.0"

    PLAYBOOKS = (
        GrowthPlaybook("linkedin_comment_leads", "LinkedIn Comment Lead Capture", "find relevant prospects from public discussion", ("linkedin_public_posts",), ("score_prospect", "draft_connection", "draft_followup"), "external_outreach"),
        GrowthPlaybook("social_engagement_prospects", "Weak Social Presence Prospecting", "find businesses with weak public engagement", ("instagram_public_profiles", "facebook_public_pages"), ("measure_engagement_gap", "score_prospect", "draft_offer"), "external_outreach"),
        GrowthPlaybook("seo_prospects", "SEO Opportunity Prospecting", "find public websites with search visibility gaps", ("google_search", "public_website"), ("measure_visibility_gap", "discover_public_contact", "draft_email"), "external_outreach"),
        GrowthPlaybook("youtube_to_linkedin_carousel", "Video to Carousel", "turn public video insights into original carousel concepts", ("youtube_public_video",), ("extract_topics", "create_original_carousel", "rights_review", "draft_publish"), "content_publication"),
        GrowthPlaybook("tiktok_engagement", "TikTok Engagement Discovery", "find relevant new public videos and draft useful comments", ("tiktok_public_video",), ("rank_relevance", "draft_comment", "approval_queue"), "external_engagement"),
        GrowthPlaybook("cross_language_reels", "Cross-language Reel Factory", "transform public trend signals into original Arabic short-form content", ("tiktok_public_video", "youtube_public_video"), ("trend_extract", "originality_transform", "arabic_script", "media_plan", "approval_queue", "publish"), "content_publication"),
        GrowthPlaybook("voice_sales_agent", "Voice Sales Agent", "qualify inbound calls and route qualified opportunities", ("phone_call", "crm", "calendar"), ("transcribe", "qualify", "schedule_or_escalate", "record_outcome"), "customer_interaction"),
    )

    @classmethod
    def catalog(cls, organization_id: int | None) -> dict[str, Any]:
        return {
            "version": cls.VERSION,
            "organization_id": organization_id,
            "playbooks": [cls._serialize(p) for p in cls.PLAYBOOKS],
            "governance": {"tenant_scoped": True, "discovery_read_only": True, "external_execution": False, "human_approval_required": True, "canonical_runtime_only": True},
        }

    @classmethod
    def plan(cls, organization_id: int | None, playbook_id: str, target: dict[str, Any] | None = None, evidence: dict[str, Any] | None = None) -> dict[str, Any]:
        if not organization_id or organization_id <= 0:
            return cls._blocked("organization_required")
        playbook = next((p for p in cls.PLAYBOOKS if p.playbook_id == playbook_id), None)
        if playbook is None:
            return cls._blocked("unknown_playbook")
        target = dict(target or {})
        evidence = dict(evidence or {})
        plan = {
            "playbook_id": playbook.playbook_id,
            "objective": playbook.objective,
            "target": target,
            "evidence": evidence,
            "steps": [{"action": action, "status": "proposed"} for action in playbook.actions],
            "risk": playbook.risk,
            "approval_required": True,
            "execution_authority": False,
            "external_execution": False,
            "database_mutation": False,
            "canonical_runtime_only": True,
            "credentials_exposed": False,
        }
        plan["plan_digest"] = sha256(json.dumps(plan, sort_keys=True, default=str).encode()).hexdigest()
        return {"success": True, "status": "planned", "plan": plan}

    @staticmethod
    def _serialize(playbook: GrowthPlaybook) -> dict[str, Any]:
        return {"playbook_id": playbook.playbook_id, "name": playbook.name, "objective": playbook.objective, "discovery_sources": list(playbook.discovery_sources), "actions": list(playbook.actions), "risk": playbook.risk}

    @staticmethod
    def _blocked(error: str) -> dict[str, Any]:
        return {"success": False, "status": "blocked", "error": error, "execution_authority": False, "external_execution": False}


growth_automation_service = GrowthAutomationService()

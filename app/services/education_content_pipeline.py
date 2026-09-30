from __future__ import annotations

from typing import Any, Mapping

from app.services.tool_intelligence_registry import tool_intelligence_registry


class EducationContentPipeline:
    VERSION = "1.1"

    def build_plan(self, *, organization_id: int, problem: str, subject: str,
                   learner_level: str = "general", language: str = "ar-EG",
                   include_video: bool = True) -> dict[str, Any]:
        if int(organization_id or 0) <= 0:
            raise ValueError("organization_required")
        if not str(problem or "").strip():
            raise ValueError("problem_required")
        if not str(subject or "").strip():
            raise ValueError("subject_required")
        return {
            "success": True, "engine": "kemet_education_content_pipeline", "version": self.VERSION,
            "organization_id": int(organization_id), "status": "proposal",
            "flow": ["problem", "understanding", "explanation", "visual_story"] + (["educational_video"] if include_video else []),
            "input": {"problem": str(problem).strip()[:10000], "subject": str(subject).strip()[:200],
                      "learner_level": str(learner_level).strip()[:100], "language": str(language).strip()[:20]},
            "outputs": {"simple_explanation": True, "worked_examples": True, "diagrams": True,
                        "animation_plan": True, "voice_plan": True, "video_plan": include_video},
            "tool_intelligence": tool_intelligence_registry.recommend(
                "research", organization_id=int(organization_id)
            ),
            "practice": {
                "mode": "learn_by_doing",
                "steps": ["understand", "attempt", "feedback", "retry", "verify"],
                "real_task": True,
                "answer_first": False,
                "progress_signal": "observed_skill",
                "loop_guard": {
                    "max_attempts": 3,
                    "requires_progress": True,
                    "on_stall": "escalate_to_coach",
                    "on_success": "record_skill_signal",
                },
            },
            "quality": {"correctness_check": True, "source_trace": True, "uncertainty_label": True,
                        "age_appropriate": True, "original_visuals": True},
            "governance": self._governance(),
        }

    @staticmethod
    def _governance() -> dict[str, Any]:
        return {"mode": "advisory", "read_only": True, "execution_authority": False,
                "external_execution": False, "database_mutation": False, "auto_publish": False,
                "human_approval_required": True, "canonical_executor": "kemet_canonical_runtime"}


education_content_pipeline = EducationContentPipeline()

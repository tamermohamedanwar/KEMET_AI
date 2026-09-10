from datetime import datetime
from typing import Any


class BusinessFeedbackService:
    VERSION = "1.1"
    MAX_NOTE_LENGTH = 500
    ALLOWED_SIGNALS = {"positive", "neutral", "negative"}
    ALLOWED_PERIODS = {"7d", "30d", "90d"}

    @classmethod
    def build(cls, organization_id, decision_id=None, capability_id=None, signal="neutral", note="", period="30d"):
        if not organization_id:
            return {"success": False, "error": "organization_required", "engine": "kemet_business_feedback", "version": cls.VERSION}
        signal = str(signal or "neutral").strip().lower()
        note = str(note or "").strip()[: cls.MAX_NOTE_LENGTH]
        period = str(period or "30d").strip()
        if signal not in cls.ALLOWED_SIGNALS:
            return {"success": False, "error": "invalid_feedback_signal", "allowed": sorted(cls.ALLOWED_SIGNALS), "engine": "kemet_business_feedback", "version": cls.VERSION}
        if period not in cls.ALLOWED_PERIODS:
            return {"success": False, "error": "invalid_period", "allowed": sorted(cls.ALLOWED_PERIODS), "engine": "kemet_business_feedback", "version": cls.VERSION}
        return {
            "success": True,
            "engine": "kemet_business_feedback",
            "version": cls.VERSION,
            "organization_id": organization_id,
            "decision_id": str(decision_id).strip() if decision_id else None,
            "capability_id": str(capability_id).strip() if capability_id else None,
            "feedback": {"signal": signal, "note": note, "period": period},
            "next_state": "reviewed",
            "learning": {"mode": "observational", "ranking_adjustment": "recommendation_only", "confidence_calibration": True},
            "governance": {"read_only": True, "advisory": True, "external_execution": False, "database_mutation": False, "auto_execute": False, "human_approval_required": True},
            "generated_at": datetime.utcnow().isoformat(),
        }


business_feedback = BusinessFeedbackService()

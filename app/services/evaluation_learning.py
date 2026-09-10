class EvaluationLearningService:
    """Read-only evaluation gate and learning signals for governed decisions."""

    VERSION = "1.1"

    @classmethod
    def _quality_dimensions(cls, lifecycle):
        governance = lifecycle.get("governance") or {}
        approval = lifecycle.get("approval") or {}
        execution = lifecycle.get("execution") or {}
        outcome = lifecycle.get("observed_outcome") or []
        state = str(lifecycle.get("state") or "detected").lower()
        decision_quality = bool(lifecycle.get("decision_id") and lifecycle.get("capability_id"))
        approval_status = str(approval.get("status") or "").lower()
        approval_quality = (
            not approval.get("id")
            or approval_status in {"approved", "rejected", "pending"}
            or state in {"detected", "ranked", "reviewed"}
        )
        execution_quality = execution.get("status") in {None, "", "completed"}
        measurement_quality = bool(outcome)
        outcome_signal = bool(outcome) and state == "outcome_observed"
        return {
            "decision_quality": decision_quality,
            "approval_quality": approval_quality,
            "execution_quality": execution_quality,
            "measurement_quality": measurement_quality,
            "outcome_signal": outcome_signal,
        }

    @classmethod
    def evaluate(cls, lifecycle):
        if not isinstance(lifecycle, dict):
            return {"success": False, "error": "lifecycle_required"}
        if not lifecycle.get("decision_id"):
            return {"success": False, "error": "decision_id_required"}

        governance = lifecycle.get("governance") or {}
        execution = lifecycle.get("execution") or {}
        approval = lifecycle.get("approval") or {}
        state = str(lifecycle.get("state") or "detected")
        checks = {
            "identity": bool(lifecycle.get("capability_id")),
            "governance": (
                governance.get("read_only") is True
                and governance.get("external_execution") is False
                and governance.get("database_mutation") is False
            ),
            "approval": (
                not approval.get("id")
                or str(approval.get("status") or "").lower() == "approved"
                or state in {"detected", "ranked", "reviewed", "rejected"}
            ),
            "execution": execution.get("status") in {None, "", "completed"},
            "outcome": bool(lifecycle.get("observed_outcome")),
        }
        dimensions = cls._quality_dimensions(lifecycle)
        score = sum(20 for passed in checks.values() if passed)
        if not checks["governance"] or not checks["execution"]:
            status = "fail"
        elif score == 100:
            status = "pass"
        else:
            status = "review"

        return {
            "success": True,
            "version": cls.VERSION,
            "status": status,
            "score": score,
            "checks": checks,
            "quality_dimensions": dimensions,
            "recommendation": cls._recommendation(status, checks, state),
            "governance": cls._governance(),
        }

    @staticmethod
    def _recommendation(status, checks, state):
        if status == "fail":
            if not checks["governance"]:
                return "Review governance boundary before any execution."
            return "Investigate the failed execution path before retrying."
        if not checks["outcome"]:
            return "Improve outcome measurement coverage before claiming business impact."
        if state == "rejected":
            return "Use rejection feedback to improve decision ranking and plan quality."
        return "Preserve the governed path and monitor observed outcomes."

    @staticmethod
    def _governance():
        return {
            "read_only": True,
            "advisory": True,
            "policy_mutation": False,
            "external_execution": False,
            "database_mutation": False,
            "causal_claim": False,
            "roi_claim": False,
        }

    @classmethod
    def build(cls, lifecycle_items):
        items = []
        for lifecycle in lifecycle_items or []:
            evaluation = cls.evaluate(lifecycle)
            if evaluation.get("success"):
                items.append({
                    "decision_id": lifecycle.get("decision_id"),
                    "capability_id": lifecycle.get("capability_id"),
                    "state": lifecycle.get("state"),
                    "evaluation": evaluation,
                })

        total = len(items)
        passed = sum(item["evaluation"]["status"] == "pass" for item in items)
        reviewed = sum(item["evaluation"]["status"] == "review" for item in items)
        failed = sum(item["evaluation"]["status"] == "fail" for item in items)
        approved = sum(
            str((item.get("state") or "")).lower() in {"approved", "executed", "outcome_observed"}
            for item in items
        )
        executed = sum(
            item.get("state") in {"executed", "outcome_observed"}
            for item in items
        )
        observed = sum(item.get("state") == "outcome_observed" for item in items)
        rejected = sum(item.get("state") == "rejected" for item in items)
        scores = [item["evaluation"]["score"] for item in items]
        dimension_names = (
            "decision_quality",
            "approval_quality",
            "execution_quality",
            "measurement_quality",
            "outcome_signal",
        )
        dimension_rates = {
            name: round(
                sum(bool(item["evaluation"]["quality_dimensions"].get(name)) for item in items) / total,
                4,
            ) if total else 0.0
            for name in dimension_names
        }

        return {
            "success": True,
            "version": cls.VERSION,
            "summary": {
                "decisions": total,
                "evaluation_pass_rate": round(passed / total, 4) if total else 0.0,
                "review_rate": round(reviewed / total, 4) if total else 0.0,
                "failure_rate": round(failed / total, 4) if total else 0.0,
                "approval_rate": round(approved / total, 4) if total else 0.0,
                "execution_rate": round(executed / total, 4) if total else 0.0,
                "outcome_observation_rate": round(observed / total, 4) if total else 0.0,
                "rejection_rate": round(rejected / total, 4) if total else 0.0,
                "mean_score": round(sum(scores) / total, 2) if total else 0.0,
                "quality_dimensions": dimension_rates,
            },
            "items": items,
            "learning_signals": cls._signals(items),
            "governance": cls._governance(),
        }

    @staticmethod
    def _signals(items):
        signals = []
        summary = {
            "decisions": len(items),
            "failed": sum(i["evaluation"]["status"] == "fail" for i in items),
            "review": sum(i["evaluation"]["status"] == "review" for i in items),
            "observed": sum(i.get("state") == "outcome_observed" for i in items),
            "rejected": sum(i.get("state") == "rejected" for i in items),
        }
        if summary["failed"]:
            signals.append({"type": "execution_quality", "priority": "high", "action": "investigate_failures"})
        if summary["review"]:
            signals.append({"type": "measurement_coverage", "priority": "medium", "action": "improve_outcome_coverage"})
        if summary["rejected"]:
            signals.append({"type": "decision_quality", "priority": "medium", "action": "review_rejection_patterns"})
        if not signals and summary["decisions"]:
            signals.append({"type": "stability", "priority": "low", "action": "continue_monitoring"})
        return signals

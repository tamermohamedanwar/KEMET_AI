from typing import Any, Dict, Optional


class ExecutionService:
    @staticmethod
    def validate_request(
        action: str,
        parameters: Optional[Dict[str, Any]] = None,
        requires_approval: bool = False,
    ) -> Dict[str, Any]:
        action = str(action or "").strip()

        if not action:
            return {
                "success": False,
                "status": "invalid",
                "error": "action_required",
            }

        return {
            "success": True,
            "status": "waiting_approval" if requires_approval else "ready",
            "action": action,
            "parameters": parameters or {},
            "requires_approval": bool(requires_approval),
        }

    @staticmethod
    def build_execution_plan(
        action: str,
        parameters: Optional[Dict[str, Any]] = None,
        requires_approval: bool = False,
    ) -> Dict[str, Any]:
        validation = ExecutionService.validate_request(
            action=action,
            parameters=parameters,
            requires_approval=requires_approval,
        )

        if not validation["success"]:
            return validation

        return {
            "success": True,
            "status": validation["status"],
            "engine": "kemet_execution",
            "version": "1.0",
            "action": validation["action"],
            "parameters": validation["parameters"],
            "requires_approval": validation["requires_approval"],
            "external_execution": False,
            "database_mutation": False,
        }


def execution_plan(
    action: str,
    parameters: Optional[Dict[str, Any]] = None,
    requires_approval: bool = False,
) -> Dict[str, Any]:
    return ExecutionService.build_execution_plan(
        action=action,
        parameters=parameters,
        requires_approval=requires_approval,
    )

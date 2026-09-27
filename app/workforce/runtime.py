from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from app.workforce.registry import workforce_registry


class WorkforceRuntime:
    """
    Runtime layer for AI Employees.

    Flow:
        Employee
        -> Permission Check
        -> Dispatcher
        -> Automation Engine
        -> Result
    """

    def __init__(self):
        self._tasks = {}

    def _task_id(self):
        return f"task_{uuid4().hex[:12]}"

    def _now(self):
        return datetime.utcnow().isoformat() + "Z"

    def validate_employee(self, workforce_id):
        if not workforce_registry.exists(workforce_id):
            return {
                "success": False,
                "status": "blocked",
                "error": "workforce_not_found",
            }

        employee = workforce_registry.get(workforce_id)

        return {
            "success": True,
            "employee": employee,
        }

    def validate_action(self, workforce_id, action):
        employee_check = self.validate_employee(
            workforce_id
        )

        if not employee_check["success"]:
            return employee_check

        employee = employee_check["employee"]

        allowed = action in employee.get(
            "allowed_actions",
            [],
        )
        approval = action in employee.get(
            "approval_actions",
            [],
        )

        if not allowed and not approval:
            return {
                "success": False,
                "status": "blocked",
                "error": "action_not_allowed_for_workforce",
                "workforce_id": workforce_id,
                "action": action,
                "allowed_actions": employee.get(
                    "allowed_actions",
                    [],
                ),
                "approval_actions": employee.get(
                    "approval_actions",
                    [],
                ),
            }

        return {
            "success": True,
            "employee": employee,
            "requires_approval": approval,
        }

    def create_task(
        self,
        workforce_id,
        action,
        organization_id,
        data=None,
        user_id=None,
    ):
        if not organization_id:
            return {
                "success": False,
                "status": "blocked",
                "error": "organization_required",
            }

        validation = self.validate_action(
            workforce_id,
            action,
        )

        if not validation["success"]:
            return validation

        data = dict(data or {})

        data["organization_id"] = organization_id

        if user_id is not None:
            data["user_id"] = user_id

        task_id = self._task_id()

        task = {
            "id": task_id,
            "workforce_id": workforce_id,
            "action": action,
            "organization_id": organization_id,
            "user_id": user_id,
            "status": "queued",
            "created_at": self._now(),
            "started_at": None,
            "completed_at": None,
            "data": data,
            "result": None,
        }

        self._tasks[task_id] = task

        return {
            "success": True,
            "status": "queued",
            "task": task,
        }

    def execute_task(
        self,
        task_id,
    ):
        task = self._tasks.get(task_id)

        if task is None:
            return {
                "success": False,
                "status": "not_found",
                "error": "task_not_found",
            }

        if task["status"] not in {
            "queued",
            "retry",
        }:
            return {
                "success": False,
                "status": task["status"],
                "task": task,
            }

        validation = self.validate_action(
            task["workforce_id"],
            task["action"],
        )

        if not validation["success"]:
            task["status"] = "blocked"
            task["result"] = validation
            task["completed_at"] = self._now()

            return {
                "success": False,
                "status": "blocked",
                "task": task,
                "result": validation,
            }

        task["status"] = "running"
        task["started_at"] = self._now()

        from app.automation.dispatcher import dispatcher

        result = dispatcher.dispatch(
            action=task["action"],
            organization_id=task["organization_id"],
            data={
                **(task.get("data") or {}),
                "workforce_id": task["workforce_id"],
                "task_id": task["id"],
                "user_id": task["user_id"],
            },
        )

        task["result"] = result
        task["completed_at"] = self._now()

        status = result.get(
            "status",
            "failed",
        )

        if status == "completed":
            task["status"] = "completed"
            success = True

        elif status == "waiting_approval":
            task["status"] = "waiting_approval"
            success = False

        elif status == "deduplicated":
            task["status"] = "completed"
            success = True

        else:
            task["status"] = status
            success = False

        return {
            "success": success,
            "status": task["status"],
            "task": task,
            "result": result,
        }

    def run(
        self,
        workforce_id,
        action,
        organization_id,
        data=None,
        user_id=None,
    ):
        created = self.create_task(
            workforce_id=workforce_id,
            action=action,
            organization_id=organization_id,
            data=data,
            user_id=user_id,
        )

        if not created["success"]:
            return created

        task_id = created["task"]["id"]

        return self.execute_task(task_id)

    def get_task(self, task_id):
        return self._tasks.get(task_id)

    def list_tasks(self, organization_id=None):
        tasks = list(self._tasks.values())

        if organization_id is not None:
            tasks = [
                task
                for task in tasks
                if task["organization_id"]
                == organization_id
            ]

        return tasks


workforce_runtime = WorkforceRuntime()

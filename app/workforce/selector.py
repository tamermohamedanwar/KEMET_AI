from app.workforce.registry import workforce_registry


class WorkforceSelector:
    """
    Select the safest AI employee for an already validated action.
    The selector never executes actions.
    """

    def select(
        self,
        action,
        industry_id=None,
        preferred_workforce_id=None,
    ):
        candidates = []

        if preferred_workforce_id:
            employee = workforce_registry.get(preferred_workforce_id)

            if employee and (
                action in employee.get("allowed_actions", [])
                or action in employee.get("approval_actions", [])
            ):
                candidates.append(
                    (
                        employee,
                        100
                        if action in employee.get("allowed_actions", [])
                        else 90,
                    )
                )

        for summary in workforce_registry.list():
            workforce_id = summary.get("id")

            if (
                preferred_workforce_id
                and workforce_id == preferred_workforce_id
            ):
                continue

            employee = workforce_registry.get(workforce_id)

            if not employee:
                continue

            allowed = action in employee.get(
                "allowed_actions",
                [],
            )
            approval = action in employee.get(
                "approval_actions",
                [],
            )

            if not allowed and not approval:
                continue

            score = 0

            if allowed:
                score += 50
            elif approval:
                score += 40

            industries = employee.get("industries", [])

            if industry_id and industry_id in industries:
                score += 30

            capabilities = employee.get(
                "capabilities",
                [],
            )

            if action in capabilities:
                score += 20

            candidates.append((employee, score))

        if not candidates:
            return {
                "success": False,
                "status": "blocked",
                "error": "no_workforce_employee_available",
                "action": action,
            }

        candidates.sort(
            key=lambda item: (
                item[1],
                item[0].get("id", ""),
            ),
            reverse=True,
        )

        employee, score = candidates[0]

        requires_approval = action in employee.get(
            "approval_actions",
            [],
        )

        return {
            "success": True,
            "status": "selected",
            "workforce_id": employee.get("id"),
            "employee": employee,
            "score": score,
            "requires_approval": requires_approval,
            "action": action,
        }


workforce_selector = WorkforceSelector()

from app.automation.action_registry import registry
from app.core.execution.governed_executor import governed_execution_service
import json
import hashlib
from datetime import datetime

from app import db
from app.models.automation import (
    AutomationWorkflow,
    AutomationAction,
    AutomationExecution,
)
from app.services.automation_service import automation_service
from app.services.automation_approval_service import automation_approval_service
from app.services.ai_usage_service import check_limit, record_usage
from app.services.monetization_guard import monetization_guard
from app.automation.router import AutomationRouter


class AutomationEngine:
    @staticmethod
    def _build_idempotency_key(
        workflow_id,
        event,
        data,
        organization_id,
    ):
        payload = {
            "organization_id": organization_id,
            "workflow_id": workflow_id,
            "event": event or "unknown",
            "data": data or {},
        }

        canonical = json.dumps(
            payload,
            sort_keys=True,
            ensure_ascii=False,
            default=str,
        )

        return hashlib.sha256(
            canonical.encode("utf-8")
        ).hexdigest()

    def __init__(self):
        self.workflows = []
        self.router = AutomationRouter()

    def register(self, workflow):
        self.workflows.append(workflow)

    def _execute_action(self, action, config, data):
        action_type = action.action_type

        parameters = {}

        if isinstance(config, dict):
            parameters.update(config)

        if isinstance(data, dict):
            for key, value in data.items():
                parameters.setdefault(key, value)

        organization_id = parameters.get("organization_id")
        user_id = parameters.get("user_id")

        if organization_id is not None and user_id is not None:
            from app.models.user import User

            user = User.query.filter_by(id=user_id).first()

            if not user:
                return {
                    "success": False,
                    "status": "blocked",
                    "error": "Tenant security violation: user not found.",
                    "organization_id": organization_id,
                    "user_id": user_id,
                }

            if user.organization_id != organization_id:
                return {
                    "success": False,
                    "status": "blocked",
                    "error": "Tenant security violation: user does not belong to organization.",
                    "organization_id": organization_id,
                    "user_id": user_id,
                    "user_organization_id": user.organization_id,
                }

        result = governed_execution_service.execute(
            action=action_type,
            parameters=parameters,
            data=data,
            organization_id=organization_id,
            user_id=user_id,
        )

        if isinstance(result, dict):
            return result

        return {
            "success": True,
            "action": action_type,
            "result": result,
        }

    def _execute_with_retry(self, action, config, data, retry_policy=None):
        policy = dict(retry_policy or {})
        max_attempts = max(1, int(policy.get("max_attempts", 1)))
        retry_on = {str(item) for item in (policy.get("retry_on") or [])}
        attempts = []
        result = None

        for attempt in range(1, max_attempts + 1):
            result = self._execute_action(action, config, data)
            attempts.append({
                "attempt": attempt,
                "success": bool(result.get("success")) if isinstance(result, dict) else True,
                "status": result.get("status") if isinstance(result, dict) else "completed",
                "error": result.get("error") if isinstance(result, dict) else None,
            })
            if not isinstance(result, dict) or result.get("success"):
                break
            error_code = str(result.get("error_code") or result.get("status") or "")
            error_text = str(result.get("error") or result.get("message") or "")
            transient = error_code in retry_on or error_text in retry_on
            if not transient or attempt >= max_attempts:
                break

        if not isinstance(result, dict):
            result = {"success": True, "result": result}
        result = dict(result)
        result["retry"] = {
            "attempts": len(attempts),
            "max_attempts": max_attempts,
            "history": attempts,
        }
        return result

    @staticmethod
    def _checkpoint(execution, action_results, current_position, status="running", error=None):
        prior = {}
        if execution.output_json:
            try:
                parsed = json.loads(execution.output_json)
                if isinstance(parsed, dict):
                    prior = parsed
            except Exception:
                prior = {}
        state = {
            "version": "1.1",
            "status": status,
            "current_position": current_position,
            "completed_positions": [
                item.get("position") for item in action_results
                if item.get("status") == "completed"
            ],
            "steps": action_results,
        }
        if prior.get("outcome_baseline"):
            state["outcome_baseline"] = prior["outcome_baseline"]
        if prior.get("outcome"):
            state["outcome"] = prior["outcome"]
        execution.status = status
        execution.output_json = json.dumps(state, ensure_ascii=False, default=str)
        execution.error_message = error
        execution.completed_at = datetime.utcnow() if status in {"completed", "failed", "rejected"} else None

    def execute(self, event=None, data=None, organization_id=None, workflow_id=None):
        data = data or {}
        results = []

        # Resolve organization from an explicitly selected database workflow.
        # This allows direct workflow execution while preserving tenant isolation.
        if workflow_id is not None and organization_id is None:
            selected_workflow = AutomationWorkflow.query.filter_by(
                id=workflow_id
            ).first()

            if selected_workflow is not None:
                organization_id = selected_workflow.organization_id

        if organization_id is not None:
            monetization = monetization_guard.feature(organization_id, "automation")
            if not monetization.get("allowed"):
                return [{
                    "success": False,
                    "status": "blocked",
                    "error_code": "feature_not_entitled",
                    "error": monetization.get("reason"),
                    "organization_id": organization_id,
                    "feature": "automation",
                }]

        # Propagate tenant context into action parameters.
        # Preserve an explicitly supplied user_id.
        if organization_id is not None:
            data["organization_id"] = organization_id

        # Legacy workflows
        for workflow in self.workflows:
            if workflow.get("event") == event:
                results.append({
                    "workflow": workflow.get("name"),
                    "action": workflow.get("action"),
                    "status": "queued",
                    "source": "legacy",
                })

        # Database workflows require organization
        if not organization_id:
            return results

        workflow_query = AutomationWorkflow.query.filter_by(
            organization_id=organization_id,
            is_active=True,
        )

        # Billing / usage guard:
        # Do not execute paid AI automation when the organization
        # has exhausted its current plan allowance.
        try:
            usage_limit = check_limit(organization_id)
        except Exception as exc:
            return [{
                "status": "failed",
                "source": "billing",
                "error": f"Usage check failed: {exc}",
            }]

        if not usage_limit.get("allowed", False):
            return [{
                "status": "blocked",
                "source": "billing",
                "organization_id": organization_id,
                "plan": usage_limit.get("plan"),
                "limit": usage_limit.get("limit"),
                "used": usage_limit.get("used"),
                "remaining": usage_limit.get("remaining"),
                "error": "Automation usage limit reached.",
            }]

        if workflow_id is not None:
            workflow_query = workflow_query.filter_by(id=workflow_id)
        elif event == "ticket_message_created":
            routed_action = self.router.route(data.get("message"))

            workflow_ids = [
                action.workflow_id
                for action in AutomationAction.query
                .filter_by(
                    action_type=routed_action,
                    is_active=True,
                )
                .all()
            ]

            if workflow_ids:
                workflow_query = workflow_query.filter(
                    AutomationWorkflow.id.in_(workflow_ids)
                )
            else:
                workflow_query = workflow_query.filter(
                    AutomationWorkflow.id == -1
                )
        else:
            workflow_query = workflow_query.filter_by(trigger_type=event)

        workflows = (
            workflow_query
            .order_by(AutomationWorkflow.id.asc())
            .all()
        )

        for workflow in workflows:
            idempotency_key = self._build_idempotency_key(
                workflow_id=workflow.id,
                event=event,
                data=data,
                organization_id=organization_id,
            )

            existing_execution = (
                AutomationExecution.query
                .filter_by(
                    workflow_id=workflow.id,
                    idempotency_key=idempotency_key,
                )
                .order_by(
                    AutomationExecution.id.desc()
                )
                .first()
            )

            if existing_execution is not None:
                results.append({
                    "workflow": workflow.id,
                    "workflow_name": workflow.name,
                    "status": "deduplicated",
                    "source": "idempotency",
                    "execution_id": existing_execution.id,
                    "execution_status": existing_execution.status,
                    "idempotency_key": idempotency_key,
                })
                continue

            execution = AutomationExecution(
                workflow_id=workflow.id,
                trigger_type=event or "unknown",
                idempotency_key=idempotency_key,
                status="running",
                input_json=json.dumps(
                    data,
                    ensure_ascii=False,
                    default=str,
                ),
                started_at=datetime.utcnow(),
                created_at=datetime.utcnow(),
            )

            db.session.add(execution)
            db.session.flush()

            try:
                from app.services.business_outcome_service import business_outcome_service
                execution_identity = {
                    "organization_id": organization_id,
                    "workflow_id": workflow.id,
                    "execution_id": execution.id,
                    "execution_key": idempotency_key,
                    "idempotency_key": idempotency_key,
                }
                baseline = business_outcome_service.capture_snapshot(organization_id, "30d", execution_identity=execution_identity)
                execution.output_json = json.dumps({
                    "version": "1.1",
                    "status": "running",
                    "current_position": 0,
                    "completed_positions": [],
                    "steps": [],
                    "outcome_baseline": baseline if baseline.get("success") else None,
                }, ensure_ascii=False, default=str)
                db.session.flush()

                actions = (
                    AutomationAction.query
                    .filter_by(
                        workflow_id=workflow.id,
                        is_active=True,
                    )
                    .order_by(AutomationAction.position.asc())
                    .all()
                )

                action_results = []
                step_context = dict(data)
                step_context["workflow_context"] = {"steps": []}

                for action in actions:
                    config = {}

                    if action.config_json:
                        try:
                            config = json.loads(action.config_json)
                        except Exception:
                            config = {}

                    retry_policy = {}
                    try:
                        if isinstance(config, dict):
                            retry_policy = config.get("retry_policy") or {}
                    except Exception:
                        retry_policy = {}

                    action_result = self._execute_with_retry(
                        action,
                        config,
                        step_context,
                        retry_policy=retry_policy,
                    )

                    # Human approval gate.
                    # Actions explicitly requesting approval are persisted
                    # and execution stops before any downstream action.
                    if (
                        isinstance(action_result, dict)
                        and action_result.get("approval_required") is True
                    ):
                        approval = automation_approval_service.create(
                            organization_id=organization_id,
                            action_type=action.action_type,
                            reason=(
                                action_result.get("message")
                                or action_result.get("reason")
                                or f"Human approval required for {action.action_type}"
                            ),
                            request_data={
                                "action_id": action.id,
                                "action": action.action_type,
                                "parameters": config,
                                "data": data,
                                "action_result": action_result,
                            },
                            workflow_id=workflow.id,
                            execution_id=execution.id,
                            requested_by=data.get("user_id"),
                        )

                        action_result = {
                            **action_result,
                            "approval_id": approval.get("approval_id"),
                            "status": "pending",
                            "approval_required": True,
                            "requires_human": True,
                            "financial_action_executed": False,
                        }

                        action_results.append({
                            "position": action.position,
                            "action_id": action.id,
                            "action_type": action.action_type,
                            "config": config,
                            "result": action_result,
                            "status": "waiting_approval",
                        })

                        self._checkpoint(
                            execution,
                            action_results,
                            current_position=action.position,
                            status="waiting_approval",
                        )

                        results.append({
                            'workflow': workflow.name,
                            'workflow_id': workflow.id,
                            'execution_id': execution.id,
                            "status": "waiting_approval",
                            "approval_id": approval.get("approval_id"),
                            "approval_required": True,
                            "requires_human": True,
                            "financial_action_executed": False,
                            'actions': action_results,
                            "source": "database",
                        })

                        break

                    action_results.append({
                        "position": action.position,
                        "action_id": action.id,
                        "action_type": action.action_type,
                        "config": config,
                        "result": action_result,
                        "status": (
                            "completed"
                            if action_result.get("success")
                            else "failed"
                        ),
                    })

                    step_context["workflow_context"]["steps"].append({
                        "position": action.position,
                        "action_id": action.id,
                        "action_type": action.action_type,
                        "success": bool(action_result.get("success")),
                        "result": action_result,
                    })
                    step_context["previous_result"] = action_result
                    self._checkpoint(
                        execution,
                        action_results,
                        current_position=action.position,
                        status="running",
                    )

                    if not action_result.get("success"):
                        raise RuntimeError(
                            action_result.get(
                                "message",
                                "Automation action failed",
                            )
                        )

                if execution.status != "waiting_approval":
                    self._checkpoint(
                        execution,
                        action_results,
                        current_position=(actions[-1].position if actions else 0),
                        status="completed",
                    )
                    try:
                        checkpoint = json.loads(execution.output_json or "{}")
                        baseline = checkpoint.get("outcome_baseline")
                        capability = action_results[-1].get("action_type") if action_results else None
                        if baseline and capability:
                            from app.services.business_outcome_service import business_outcome_service
                            outcome = business_outcome_service.build_execution_outcome(
                                organization_id, f"kemet.{capability}", baseline, "30d", execution_identity={
                                    "organization_id": organization_id,
                                    "workflow_id": workflow.id,
                                    "execution_id": execution.id,
                                    "execution_key": idempotency_key,
                                    "idempotency_key": idempotency_key,
                                }
                            )
                            checkpoint["outcome"] = outcome if outcome.get("success") else {"success": False, "error": outcome.get("error")}
                            checkpoint["outcome_measurement"] = {
                                "status": "completed" if outcome.get("success") else "failed",
                                "attempted_at": datetime.utcnow().isoformat(),
                                "error": outcome.get("error") if not outcome.get("success") else None,
                            }
                            execution.output_json = json.dumps(checkpoint, ensure_ascii=False, default=str)
                    except Exception as exc:
                        try:
                            checkpoint = json.loads(execution.output_json or "{}")
                            checkpoint["outcome_measurement"] = {
                                "status": "failed",
                                "attempted_at": datetime.utcnow().isoformat(),
                                "error_type": type(exc).__name__,
                                "error": str(exc),
                                "non_blocking": True,
                            }
                            execution.output_json = json.dumps(checkpoint, ensure_ascii=False, default=str)
                        except Exception:
                            pass

                    results.append({
                        "workflow": workflow.name,
                        "workflow_id": workflow.id,
                        "status": "completed",
                        "actions": action_results,
                        "source": "database",
                    })

            except Exception as exc:
                db.session.rollback()

                execution.status = "failed"
                execution.error_message = str(exc)
                execution.completed_at = datetime.utcnow()

                db.session.add(execution)

                results.append({
                    "workflow": workflow.name,
                    "workflow_id": workflow.id,
                    "status": "failed",
                    "error": str(exc),
                    "source": "database",
                })

        db.session.commit()

        return results



    def resume_after_approval(
        self,
        approval_id,
        execution_id,
        workflow_id,
        organization_id,
    ):
        from app.models.automation import AutomationAction, AutomationApproval, AutomationExecution, AutomationWorkflow

        approval = db.session.get(AutomationApproval, approval_id)
        execution = db.session.get(AutomationExecution, execution_id)
        workflow = db.session.get(AutomationWorkflow, workflow_id)

        if not approval or approval.status != "approved":
            raise RuntimeError("Approval request is not approved.")
        if not execution:
            raise RuntimeError("Automation execution not found.")
        if not workflow:
            raise RuntimeError("Automation workflow not found.")
        if approval.organization_id != organization_id or workflow.organization_id != organization_id:
            raise RuntimeError("Automation tenant mismatch.")
        if approval.execution_id != execution.id or approval.workflow_id != workflow.id:
            raise RuntimeError("Automation approval execution binding mismatch.")
        if execution.workflow_id != workflow.id:
            raise RuntimeError("Automation execution workflow mismatch.")
        if execution.status == "completed":
            return {
                "success": True,
                "status": "deduplicated",
                "reason": "execution_already_completed",
                "approval_id": approval.id,
                "execution_id": execution.id,
                "workflow_id": workflow.id,
            }
        if execution.status in {"rejected", "failed"}:
            raise RuntimeError("Automation execution is not resumable.")

        decision_data = {}
        if approval.decision_json:
            try:
                decision_data = json.loads(approval.decision_json)
            except Exception:
                decision_data = {}
        plan = decision_data.get("plan") or {}
        authorization = decision_data.get("authorization")
        if not plan or not authorization:
            raise RuntimeError("Execution plan authorization is missing.")

        context = plan.get("context") or {}
        if (context.get("approval_id") != approval.id or
                context.get("execution_id") != execution.id or
                context.get("workflow_id") != workflow.id or
                context.get("organization_id") != organization_id):
            raise RuntimeError("Authorized execution context mismatch.")

        action_type = plan.get("action")
        action_id = context.get("action_id")
        if not action_type or not action_id:
            raise RuntimeError("Authorized action identity is missing.")

        action = AutomationAction.query.filter_by(
            id=action_id, workflow_id=workflow.id, action_type=action_type, is_active=True
        ).first()
        if not action:
            raise RuntimeError("Authorized action is no longer available.")

        from app.core.execution.execution_boundary import execution_boundary
        gate_result = execution_boundary.require(
            plan=plan, authorization=authorization, action=action_type
        )
        if not gate_result.get("allowed"):
            raise RuntimeError(gate_result.get("error", "Central execution gate denied execution."))

        parameters = plan.get("parameters") or {}
        data = plan.get("data") or {}
        if not isinstance(parameters, dict) or not isinstance(data, dict):
            raise RuntimeError("Authorized execution payload is invalid.")

        from app.core.execution.runtime import canonical_execution_runtime

        execution_key = str(authorization.get("execution_key") or f"approval:{approval.id}")
        from app.services.execution_entitlement_service import execution_entitlement_service
        entitlement = execution_entitlement_service.check(
            organization_id, execution_key=execution_key
        )
        if not entitlement.get("allowed"):
            raise RuntimeError(entitlement.get("reason", "execution_not_entitled"))

        from app.core.execution_ledger import execution_ledger
        import hashlib
        token = str(authorization.get("token") or "")
        approval_hash = hashlib.sha256(token.encode("utf-8")).hexdigest() if token else None
        started = execution_ledger.begin(
            organization_id=organization_id,
            execution_key=execution_key,
            plan_hash=str(authorization.get("plan_hash") or plan.get("plan_hash") or ""),
            job_id=execution.id,
            worker_id="automation-engine",
            approval_hash=approval_hash,
            decision_hash=(authorization.get("gate_handoff") or {}).get("decision_hash"),
        )
        if not started.get("created"):
            raise RuntimeError("execution_ledger_replay_or_in_progress")

        outcome_started_at = datetime.utcnow()
        canonical_parameters = dict(parameters)
        canonical_parameters["_approved_execution"] = True
        for key, value in data.items():
            canonical_parameters.setdefault(key, value)
        canonical_plan = dict(plan)
        canonical_plan["action"] = action_type
        canonical_plan["parameters"] = canonical_parameters

        approved_result = canonical_execution_runtime.execute(
            plan=canonical_plan,
            authorization=authorization,
            action_registry=registry,
            user_id=canonical_parameters.get("user_id"),
            execution_envelope_payload=authorization.get("execution_envelope"),
        )
        if approved_result.get("approval_required"):
            raise RuntimeError("Action requested approval again.")
        if not approved_result.get("success"):
            execution_ledger.finish(
                organization_id=organization_id,
                execution_key=execution_key,
                status="failed",
                receipt=approved_result,
            )
            raise RuntimeError(approved_result.get("message") or approved_result.get("error") or "Approved action failed.")

        action_results = []
        if execution.output_json:
            try:
                checkpoint = json.loads(execution.output_json)
                if isinstance(checkpoint, dict):
                    action_results = list(checkpoint.get("steps") or [])
                elif isinstance(checkpoint, list):
                    action_results = checkpoint
            except Exception:
                action_results = []

        action_results = [item for item in action_results if item.get("action_id") != action.id]
        action_results.append({
            "position": action.position,
            "action_id": action.id,
            "action_type": action.action_type,
            "result": approved_result,
            "status": "completed",
            "approval_id": approval.id,
        })
        action_results.sort(key=lambda item: item.get("position", 0))

        step_context = dict(data)
        step_context["organization_id"] = organization_id
        step_context["workflow_context"] = {
            "steps": [
                {
                    "position": item.get("position"),
                    "action_id": item.get("action_id"),
                    "action_type": item.get("action_type"),
                    "success": bool((item.get("result") or {}).get("success")),
                    "result": item.get("result"),
                }
                for item in action_results
            ]
        }
        step_context["previous_result"] = approved_result

        actions = AutomationAction.query.filter_by(
            workflow_id=workflow.id, is_active=True
        ).order_by(AutomationAction.position.asc()).all()

        for next_action in actions:
            if next_action.position <= action.position:
                continue

            config = {}
            if next_action.config_json:
                try:
                    config = json.loads(next_action.config_json)
                except Exception:
                    config = {}

            retry_policy = config.get("retry_policy") if isinstance(config, dict) else {}
            next_result = self._execute_with_retry(
                next_action, config, step_context, retry_policy=retry_policy
            )

            if next_result.get("approval_required") is True:
                approval_next = automation_approval_service.create(
                    organization_id=organization_id,
                    action_type=next_action.action_type,
                    reason=next_result.get("message") or next_result.get("reason") or f"Human approval required for {next_action.action_type}",
                    request_data={
                        "action_id": next_action.id,
                        "action": next_action.action_type,
                        "parameters": config,
                        "data": data,
                        "action_result": next_result,
                    },
                    workflow_id=workflow.id,
                    execution_id=execution.id,
                    requested_by=data.get("user_id"),
                )
                item = {
                    "position": next_action.position,
                    "action_id": next_action.id,
                    "action_type": next_action.action_type,
                    "config": config,
                    "result": {**next_result, "approval_id": approval_next.get("approval_id"), "status": "pending", "financial_action_executed": False},
                    "status": "waiting_approval",
                }
                action_results.append(item)
                self._checkpoint(execution, action_results, next_action.position, status="waiting_approval")
                db.session.commit()
                return {
                    "success": False, "status": "waiting_approval",
                    "approval_id": approval_next.get("approval_id"),
                    "execution_id": execution.id, "workflow_id": workflow.id,
                    "actions": action_results,
                }

            item = {
                "position": next_action.position,
                "action_id": next_action.id,
                "action_type": next_action.action_type,
                "config": config,
                "result": next_result,
                "status": "completed" if next_result.get("success") else "failed",
            }
            action_results.append(item)
            step_context["workflow_context"]["steps"].append({
                "position": next_action.position,
                "action_id": next_action.id,
                "action_type": next_action.action_type,
                "success": bool(next_result.get("success")),
                "result": next_result,
            })
            step_context["previous_result"] = next_result
            self._checkpoint(execution, action_results, next_action.position, status="running")
            if not next_result.get("success"):
                self._checkpoint(execution, action_results, next_action.position, status="failed", error=next_result.get("error") or next_result.get("message"))
                db.session.commit()
                return {
                    "success": False, "status": "failed",
                    "execution_id": execution.id, "workflow_id": workflow.id,
                    "actions": action_results,
                    "error": next_result.get("error") or next_result.get("message"),
                }

        final_position = actions[-1].position if actions else action.position
        self._checkpoint(execution, action_results, final_position, status="completed")
        try:
            checkpoint = json.loads(execution.output_json or "{}")
            baseline = checkpoint.get("outcome_baseline")
            capability = action_results[-1].get("action_type") if action_results else None
            if baseline and capability:
                from app.services.business_outcome_service import business_outcome_service
                outcome = business_outcome_service.build_execution_outcome(
                    organization_id, f"kemet.{capability}", baseline, "30d", execution_identity={
                        "organization_id": organization_id,
                        "workflow_id": workflow.id,
                        "execution_id": execution.id,
                        "execution_key": execution_key,
                        "idempotency_key": execution.idempotency_key,
                    }
                )
                checkpoint["outcome"] = outcome if outcome.get("success") else {"success": False, "error": outcome.get("error")}
                checkpoint["outcome_measurement"] = {
                    "status": "completed" if outcome.get("success") else "failed",
                    "attempted_at": datetime.utcnow().isoformat(),
                    "error": outcome.get("error") if not outcome.get("success") else None,
                }
                execution.output_json = json.dumps(checkpoint, ensure_ascii=False, default=str)
        except Exception as exc:
            try:
                checkpoint = json.loads(execution.output_json or "{}")
                checkpoint["outcome_measurement"] = {
                    "status": "failed", "attempted_at": datetime.utcnow().isoformat(),
                    "error_type": type(exc).__name__, "error": str(exc), "non_blocking": True,
                }
                execution.output_json = json.dumps(checkpoint, ensure_ascii=False, default=str)
            except Exception:
                pass
        from app.core.automation_outcome_service import automation_outcome_service
        outcome_receipt = approved_result.get("receipt") or approved_result
        outcome = automation_outcome_service.record(
            organization_id=organization_id,
            status="completed",
            executed=True,
            job_id=execution.id,
            workflow_id=workflow.id,
            started_at=outcome_started_at,
            cost_amount=approved_result.get("cost_amount"),
            currency=approved_result.get("currency"),
            business_outcome=approved_result.get("business_outcome"),
            receipt=outcome_receipt,
        )
        execution_receipt = {
            **outcome_receipt,
            "outcome_id": outcome.get("outcome_id"),
            "commercial_entitlement": {
                "plan": entitlement.get("plan"),
                "limit": entitlement.get("limit"),
                "used_before": entitlement.get("used"),
                "remaining_after_reservation": entitlement.get("remaining"),
            },
        }
        execution_ledger.finish(
            organization_id=organization_id,
            execution_key=execution_key,
            status="completed",
            receipt=execution_receipt,
        )
        from app.core.execution_evidence import execution_evidence
        decision_hash = (authorization.get("gate_handoff") or {}).get("decision_hash")
        evidence_identity = {
            "execution_key": execution_key,
            "job_id": execution.id,
            "workflow_id": workflow.id,
            "decision_hash": decision_hash,
            "approval_id": approval.id,
        }
        execution_evidence.record(
            organization_id=organization_id,
            execution_key=execution_key,
            job_id=execution.id,
            workflow_id=str(workflow.id),
            stage="outcome.recorded",
            status="completed",
            worker_id="automation-engine",
            plan_hash=str(authorization.get("plan_hash") or plan.get("plan_hash") or ""),
            evidence_key=f"{execution_key}:outcome:{outcome.get('outcome_id')}",
            receipt={"outcome_id": outcome.get("outcome_id"), "executed": True, "execution_identity": evidence_identity},
        )
        execution_evidence.record(
            organization_id=organization_id,
            execution_key=execution_key,
            job_id=execution.id,
            workflow_id=str(workflow.id),
            stage="runtime.finished",
            status="completed",
            worker_id="automation-engine",
            plan_hash=str(authorization.get("plan_hash") or plan.get("plan_hash") or ""),
            evidence_key=f"{execution_key}:runtime.finished",
            receipt={**execution_receipt, "execution_identity": evidence_identity},
        )
        db.session.commit()
        return {
            "success": True, "status": "completed",
            "approval_id": approval.id, "execution_id": execution.id,
            "workflow_id": workflow.id, "actions": action_results,
            "outcome_id": outcome.get("outcome_id"),
            "execution_key": execution_key,
        }


engine = AutomationEngine()

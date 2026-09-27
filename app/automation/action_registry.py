from app.services.automation_service import automation_service


class ActionRegistry:
    def __init__(self, actions=None):
        if actions is not None:
            self._actions = actions
        else:
            self._actions = registry._actions if "registry" in globals() else {}

    def register(self, name, handler):
        self._actions[name] = handler

    def exists(self, name):
        return name in self._actions

    def get(self, name):
        return self._actions.get(name)

    def execute(self, name, parameters=None, user_id=None):
        handler = self.get(name)

        if not handler:
            return {
                "success": False,
                "message": f"Unknown automation action: {name}",
            }

        try:
            return handler(parameters or {}, user_id=user_id)
        except Exception as exc:
            return {
                "success": False,
                "message": str(exc),
            }



    
def _business_insights(parameters=None, user_id=None):
    """Read-only organization-scoped business intelligence action."""
    parameters = dict(parameters or {})

    organization_id = parameters.get("organization_id")
    if organization_id is None:
        return {
            "success": False,
            "status": "blocked",
            "type": "business_insights",
            "error": "organization_id_required",
            "message": "Organization context is required for business insights.",
        }

    try:
        organization_id = int(organization_id)
    except (TypeError, ValueError):
        return {
            "success": False,
            "status": "blocked",
            "type": "business_insights",
            "error": "invalid_organization_id",
            "message": "Invalid organization context.",
        }

    try:
        from app.core.context.live_business_data import LiveBusinessData
        from app.core.sales.sales_engine import SalesEngine
        from app.core.revenue.revenue_engine import RevenueEngine
        from app.core.analytics.roi_engine import ROIEngine
        from app.services.bos_intelligence import BOSIntelligenceService

        snapshot = LiveBusinessData().snapshot(organization_id)
        data = snapshot.to_dict()

        sales = SalesEngine.analyze(
            leads=data.get("leads", 0),
            qualified_leads=data.get("qualified_leads", 0),
            opportunities=data.get("opportunities", 0),
            customers=data.get("customers", 0),
            pipeline_value=data.get("pipeline_value", 0.0),
            average_deal_value=data.get("average_deal_value", 0.0),
        )

        revenue = RevenueEngine().analyze(
            leads=data.get("leads", 0),
            opportunities=data.get("opportunities", 0),
            customers=data.get("customers", 0),
            revenue=data.get("revenue", 0.0),
            pipeline_value=data.get("pipeline_value", 0.0),
        )

        roi = ROIEngine.calculate(
            revenue=data.get("revenue", 0.0),
            cost=0.0,
            customers=data.get("customers", 0),
            leads=data.get("leads", 0),
            automated_tasks=data.get("successful_executions", 0),
            manual_hours_saved=0.0,
        )

        executive_snapshot = BOSIntelligenceService.get_executive_snapshot(
            organization_id=organization_id,
        )

        return {
            "success": True,
            "status": "completed",
            "type": "business_insights",
            "message": "Business intelligence generated successfully.",
            "organization_id": organization_id,
            "user_id": user_id,
            "read_only": True,
            "external_execution": False,
            "database_mutation": False,
            "kpis": {
                "leads": data.get("leads", 0),
                "qualified_leads": data.get("qualified_leads", 0),
                "opportunities": data.get("opportunities", 0),
                "customers": data.get("customers", 0),
                "revenue": data.get("revenue", 0.0),
                "pipeline_value": data.get("pipeline_value", 0.0),
                "conversion_rate": data.get("conversion_rate", 0.0),
                "average_deal_value": data.get("average_deal_value", 0.0),
            },
            "sales": sales,
            "revenue": revenue,
            "roi": roi,
            "executive_snapshot": executive_snapshot,
        }

    except Exception as exc:
        return {
            "success": False,
            "status": "failed",
            "type": "business_insights",
            "error": "business_insights_failed",
            "message": str(exc),
            "organization_id": organization_id,
            "read_only": True,
            "external_execution": False,
            "database_mutation": False,
        }


def _federated_command(parameters=None, user_id=None):
    """Execute a provider-routed command only after a verified connection and approval."""
    parameters = dict(parameters or {})
    organization_id = parameters.get("organization_id")
    provider_id = str(parameters.get("provider_id") or "").strip()
    prompt = str(parameters.get("prompt") or "").strip()
    model_id = parameters.get("model_id")
    capabilities = tuple(str(item) for item in (parameters.get("required_capabilities") or ()))
    if not organization_id or not provider_id or not prompt:
        return {"success": False, "status": "blocked", "error": "federated_command_binding_required", "executed": False}
    try:
        organization_id = int(organization_id)
    except (TypeError, ValueError):
        return {"success": False, "status": "blocked", "error": "invalid_organization_id", "executed": False}
    try:
        from app.core.federation.connection_lifecycle import ConnectionLifecycleService
        from app.core.provider_factory import federated_generate
        from app.core.provider_health import provider_health

        rows = ConnectionLifecycleService.list_for_user(organization_id, user_id)
        verified = next((row for row in rows if row.provider_id == provider_id and row.status == "verified"), None)
        if verified is None:
            return {"success": False, "status": "blocked", "error": "provider_not_verified", "provider_id": provider_id, "executed": False}
        if not provider_health.is_healthy(provider_id):
            return {"success": False, "status": "blocked", "error": "provider_unhealthy", "provider_id": provider_id, "executed": False}
        result = federated_generate(
            prompt, model=model_id, preferred=provider_id,
            required_capabilities=capabilities, organization_id=organization_id,
        )
        return {
            "success": True, "status": "completed", "type": "federated_command",
            "content": result.content, "provider_id": result.provider_id,
            "model_id": result.model, "organization_id": organization_id,
            "external_call": True, "external_execution": False,
            "database_mutation": False, "executed": True,
        }
    except Exception as exc:
        return {
            "success": False, "status": "failed", "type": "federated_command",
            "error": "federated_command_failed", "message": str(exc),
            "provider_id": provider_id, "executed": False,
        }


registry = ActionRegistry()


def _create_ticket(parameters, user_id=None):
    return automation_service.create_ticket(
        parameters,
        user_id=user_id,
    )


def _check_order(parameters, user_id=None):
    return automation_service.check_order(parameters)


def _generate_ai_reply(parameters, user_id=None):
    return automation_service.generate_ai_reply(
        parameters or {},
        user_id=user_id,
    )



def _smart_ticket_ai(parameters, user_id=None):
    return automation_service.smart_ticket_ai(
        parameters or {},
        user_id=user_id,
    )


def _send_notification(parameters, user_id=None):
    from app.services.automation_service import automation_service

    return automation_service.send_notification(
        parameters or {},
        user_id=user_id,
    )

registry.register("create_ticket", _create_ticket)
registry.register("check_order", _check_order)
registry.register("generate_ai_reply", _generate_ai_reply)
registry.register("smart_ticket_ai", _smart_ticket_ai)
registry.register("send_notification", _send_notification)


def _media_render(parameters=None, user_id=None):
    parameters = dict(parameters or {})
    authorization = parameters.get("_execution_authorization")
    plan = parameters.get("_execution_plan")
    if not parameters.get("_approved_execution") or not isinstance(authorization, dict) or not isinstance(plan, dict):
        return {"success": False, "status": "blocked", "error": "canonical_execution_required", "executed": False}
    from app.core.media.render_engine import render_engine_v1
    return render_engine_v1.render(
        plan, approval=True, execution_authorization=authorization,
    )

registry.register("media_render", _media_render)


def _kemet_self_owned_tts_generate(parameters=None, user_id=None):
    """Execute verified local Nabra TTS only inside the canonical runtime."""
    parameters=dict(parameters or {})
    if not parameters.get("_approved_execution") or not isinstance(parameters.get("_execution_authorization"),dict):
        return {"success":False,"status":"blocked","error":"canonical_execution_required","executed":False}
    from pathlib import Path
    import hashlib,json,os,struct,subprocess,time,wave,shutil
    organization_id=int(parameters.get("organization_id") or 0); text=str(parameters.get("text") or "").strip(); output_path=str(parameters.get("output_path") or "").strip()
    if organization_id<=0 or not text or not output_path: return {"success":False,"status":"blocked","error":"tts_execution_binding_required","executed":False}
    root=Path(__file__).resolve().parents[2]; model_dir=root/".kemet_runtime"/"nabra_tts"; model_path=model_dir/"model.int4.onnx"; runtime_root=root/".kemet_runtime"/"sherpa_test_full4"; lib=runtime_root/"sherpa_onnx"/"lib"/"libonnxruntime.so"; python_bin=shutil.which("python3")
    if not (python_bin and model_path.is_file() and (model_dir/"tokens.txt").is_file() and (model_dir/"voices.bin").is_file() and lib.is_file()): return {"success":False,"status":"blocked","error":"nabra_runtime_binding_unavailable","executed":False}
    target=Path(output_path); target.parent.mkdir(parents=True,exist_ok=True)
    script="""import os,struct,sys,wave,sherpa_onnx
base,text,out=sys.argv[1],sys.argv[2],sys.argv[3]
d='/data/data/com.termux/files/usr/share/espeak-ng-data'
c=sherpa_onnx.OfflineTtsConfig(model=sherpa_onnx.OfflineTtsModelConfig(kokoro=sherpa_onnx.OfflineTtsKokoroModelConfig(model=os.path.join(base,'model.int4.onnx'),voices=os.path.join(base,'voices.bin'),tokens=os.path.join(base,'tokens.txt'),data_dir=d)))
a=sherpa_onnx.OfflineTts(c).generate(text,sid=0,speed=1.0)
with wave.open(out,'wb') as w:
 w.setnchannels(1); w.setsampwidth(2); w.setframerate(a.sample_rate); pcm=bytearray()
 for x in a.samples: pcm+=struct.pack('<h',int(max(-1.0,min(1.0,float(x)))*32767))
 w.writeframes(pcm)
print(a.sample_rate,len(a.samples))"""
    env=dict(os.environ); env["PYTHONPATH"]=str(runtime_root); env["LD_PRELOAD"]=str(lib)
    started=time.time(); result=subprocess.run([python_bin,"-c",script,str(model_dir),text,str(target)],capture_output=True,text=True,timeout=180,check=False,env=env)
    if result.returncode!=0 or not target.is_file() or target.stat().st_size<=44: return {"success":False,"status":"failed","error":"nabra_generation_failed","executed":True,"stderr":result.stderr[-2000:]}
    digest=hashlib.sha256(target.read_bytes()).hexdigest()
    with wave.open(str(target),'rb') as w: audio={"sample_rate":w.getframerate(),"channels":w.getnchannels(),"sample_width":w.getsampwidth(),"frames":w.getnframes(),"duration":w.getnframes()/w.getframerate()}
    artifact={"schema":"kemet.media.self_owned_generation_artifact.v1","version":1,"organization_id":organization_id,"worker_id":"kemet_sherpa_onnx_nabra_local_worker","capability":"TEXT_TO_SPEECH","provider_id":"sherpa_onnx_local","model_id":"nabra-82m-sherpa-onnx","model_version":"v0.1-derived-int4","runtime":"sherpa-onnx","runtime_version":"1.13.8","python_runtime":"3.14.6","artifact":{"uri":str(target),"sha256":digest,"mime_type":"audio/wav","bytes":target.stat().st_size,"audio":audio},"execution":{"location":"local Android ARM64 CPU","network":"disabled","credentials_required":False,"external_execution":False,"mcp":False,"execution_seconds":round(time.time()-started,6)},"governance":{"execution_authority":False,"human_approval_required":True}}
    artifact["evidence_digest"]=hashlib.sha256(json.dumps(artifact,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
    return {"success":True,"status":"completed","executed":True,"artifact":artifact}

registry.register("kemet_self_owned_tts_generate", _kemet_self_owned_tts_generate)


def _kemet_self_owned_transcription(parameters=None, user_id=None):
    """Execute Kemet-owned local Whisper transcription only inside the canonical runtime."""
    parameters = dict(parameters or {})
    if not parameters.get("_approved_execution") or not isinstance(parameters.get("_execution_authorization"), dict):
        return {"success": False, "status": "blocked", "error": "canonical_execution_required", "executed": False}
    from pathlib import Path
    import hashlib
    import json
    from app.services.native_transcription_service import native_transcription_service
    organization_id = int(parameters.get("organization_id") or 0)
    input_path = str(parameters.get("input_path") or "").strip()
    output_path = str(parameters.get("output_path") or "").strip()
    language = str(parameters.get("language") or "ar")
    if organization_id <= 0 or not input_path or not output_path:
        return {"success": False, "status": "blocked", "error": "transcription_execution_binding_required", "executed": False}
    result = native_transcription_service.transcribe(organization_id=organization_id, input_uri=input_path, language=language)
    if not result.get("success"):
        return result
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "kemet.media.transcription_artifact.v1",
        "version": 1,
        "organization_id": organization_id,
        "worker_id": "kemet_whisper_cpp_local_worker",
        "capability": "TRANSCRIPTION",
        "model_id": "whisper-tiny",
        "language": language,
        "input_path": input_path,
        "transcript": result.get("transcript") or [],
        "transcript_digest": result.get("transcript_digest"),
        "governance": {"execution_authority": False, "external_execution": False, "mcp": False, "human_approval_required": True},
    }
    target.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    artifact = {
        "uri": str(target), "sha256": digest, "mime_type": "application/json",
        "bytes": target.stat().st_size, "transcript_digest": result.get("transcript_digest"),
        "segment_count": len(result.get("transcript") or []),
    }
    evidence = {
        "schema": "kemet.media.self_owned_transcription_artifact.v1", "version": 1,
        "organization_id": organization_id, "worker_id": "kemet_whisper_cpp_local_worker",
        "capability": "TRANSCRIPTION", "model_id": "whisper-tiny", "artifact": artifact,
        "runtime": native_transcription_service.snapshot(organization_id),
        "provenance": {"source": "canonical_execution_runtime", "cost_classification": "SELF_HOSTED", "network": "disabled"},
    }
    evidence["evidence_digest"] = hashlib.sha256(json.dumps(evidence, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    return {"success": True, "status": "completed", "executed": True, "artifact": {"artifact": artifact}, "evidence": evidence}


registry.register("kemet_self_owned_transcription", _kemet_self_owned_transcription)


def _whatsapp_send_text(parameters=None, user_id=None):
    from app.services.whatsapp_cloud_api_service import whatsapp_cloud_api_service

    parameters = dict(parameters or {})
    organization_id = parameters.get("organization_id")
    if not parameters.get("_approved_execution") or not parameters.get("_execution_authorization"):
        return {"success": False, "status": "blocked", "error": "canonical_execution_required", "executed": False}
    return whatsapp_cloud_api_service.execute_send_text(
        organization_id=int(organization_id),
        recipient=parameters.get("recipient"),
        content=parameters.get("content"),
        external_message_id=parameters.get("external_message_id"),
        phone_number_id=parameters.get("phone_number_id"),
        approved_execution=True,
        execution_authorization=parameters.get("_execution_authorization"),
    )


def _whatsapp_send_template(parameters=None, user_id=None):
    from app.services.whatsapp_cloud_api_service import whatsapp_cloud_api_service

    parameters = dict(parameters or {})
    organization_id = parameters.get("organization_id")
    if not parameters.get("_approved_execution") or not parameters.get("_execution_authorization"):
        return {"success": False, "status": "blocked", "error": "canonical_execution_required", "executed": False}
    return whatsapp_cloud_api_service.execute_send_template(
        organization_id=int(organization_id),
        recipient=parameters.get("recipient"),
        template_name=parameters.get("template_name"),
        language_code=parameters.get("language_code"),
        external_message_id=parameters.get("external_message_id"),
        phone_number_id=parameters.get("phone_number_id"),
        parameters=parameters.get("template_parameters"),
        approved_execution=True,
        execution_authorization=parameters.get("_execution_authorization"),
    )


registry.register("whatsapp_send_text", _whatsapp_send_text)
registry.register("whatsapp_send_template", _whatsapp_send_template)


def _bosta_create_delivery(parameters=None, user_id=None):
    from app.services.bosta_connector_service import bosta_connector_service

    parameters = dict(parameters or {})
    organization_id = parameters.get("organization_id")
    if not parameters.get("_approved_execution") or not parameters.get("_execution_authorization"):
        return {"success": False, "status": "blocked", "error": "canonical_execution_required", "executed": False}
    return bosta_connector_service.execute_create_delivery(
        organization_id=int(organization_id),
        business_reference=parameters.get("business_reference"),
        customer=parameters.get("customer") or {},
        shipping_address=parameters.get("shipping_address") or {},
        cod=parameters.get("cod", 0),
        items=parameters.get("items") or [],
        package_type=parameters.get("package_type", "Small"),
        package_description=parameters.get("package_description", ""),
        webhook_url=parameters.get("webhook_url"),
        approved_execution=True,
        execution_authorization=parameters.get("_execution_authorization"),
    )


registry.register("bosta_create_delivery", _bosta_create_delivery)

def _salla_update_order(parameters=None, user_id=None):
    from app.services.salla_connector_service import salla_connector_service
    parameters = dict(parameters or {})
    if not parameters.get("_approved_execution") or not parameters.get("_execution_authorization"):
        return {"success": False, "status": "blocked", "error": "canonical_execution_required", "executed": False}
    return salla_connector_service.execute_update_order(
        organization_id=int(parameters.get("organization_id")),
        order_id=parameters.get("order_id"),
        updates=parameters.get("updates") or {},
        approved_execution=True,
        execution_authorization=parameters.get("_execution_authorization"),
    )

registry.register("salla_update_order", _salla_update_order)

registry.register(
    "classify_ticket",
    lambda parameters, user_id=None:
        automation_service.classify_ticket(parameters, user_id),
)


# Specialized AI automation routes.
# These aliases reuse the existing AI reply engine while preserving
# the specialized route name for workflow routing and analytics.

def _order_tracking(parameters, user_id=None):
    return automation_service.order_tracking(
        parameters or {},
        user_id=user_id,
    )
def _payment_issue(parameters, user_id=None):
    return automation_service.payment_issue(
        parameters or {},
        user_id=user_id,
    )
def _refund_request(parameters, user_id=None):
    return automation_service.refund_request(
        parameters or {},
        user_id=user_id,
    )
def _account_help(parameters, user_id=None):
    return automation_service.account_help(
        parameters or {},
        user_id=user_id,
    )
registry.register("order_tracking", _order_tracking)
registry.register("payment_issue", _payment_issue)
registry.register("refund_request", _refund_request)
registry.register("account_help", _account_help)



registry.register(
    "escalate_ticket",
    lambda parameters, user_id=None:
        automation_service.escalate_ticket(parameters, user_id),
)


registry.register(
    "smart_assignment",
    lambda parameters, user_id=None:
        automation_service.smart_assignment(parameters, user_id),
)


registry.register(
    "sla_management",
    lambda parameters, user_id=None:
        automation_service.sla_management(parameters, user_id),
)


registry.register(
    "auto_follow_up",
    lambda parameters, user_id=None:
        automation_service.auto_follow_up(parameters, user_id),
)

    
registry.register(
    "customer_retention",
    lambda parameters, user_id=None:
        automation_service.customer_retention(parameters, user_id),
)


registry.register(
    "churn_detection",
    lambda parameters, user_id=None:
        automation_service.churn_detection(parameters, user_id),
)


registry.register(
    "lead_scoring",
    lambda parameters, user_id=None:
        automation_service.lead_scoring(parameters, user_id),
)


registry.register(
    "sales_follow_up",
    lambda parameters, user_id=None:
        automation_service.sales_follow_up(parameters, user_id),
)


registry.register(
    "ai_sales_qualification",
    lambda parameters, user_id=None:
        automation_service.ai_sales_qualification(parameters, user_id),
)


registry.register(
    "ai_intent_classifier",
    lambda parameters, user_id=None:
        automation_service.ai_intent_classifier(parameters, user_id),
)


registry.register(
    "customer_lifecycle",
    lambda parameters, user_id=None:
        automation_service.customer_lifecycle(parameters, user_id),
)


registry.register(
    "revenue_opportunity",
    lambda parameters, user_id=None:
        automation_service.revenue_opportunity(parameters, user_id),
)


def _revenue_autopilot_plan(parameters, user_id=None):
    from app.services.revenue_autopilot_facade import RevenueAutopilotFacade

    parameters = parameters or {}
    lead_id = parameters.get("lead_id")
    organization_id = parameters.get("organization_id")

    if not lead_id:
        return {
            "success": False,
            "message": "lead_id is required",
        }

    if not organization_id:
        return {
            "success": False,
            "status": "blocked",
            "error": "organization_required",
        }

    return RevenueAutopilotFacade.plan_for_lead(
        int(lead_id),
        organization_id=int(organization_id),
    )


def _revenue_autopilot_run(parameters, user_id=None):
    from app.services.revenue_autopilot_facade import RevenueAutopilotFacade

    parameters = parameters or {}
    lead_id = parameters.get("lead_id")
    organization_id = parameters.get("organization_id")

    if not lead_id:
        return {
            "success": False,
            "message": "lead_id is required",
        }

    if not organization_id:
        return {
            "success": False,
            "status": "blocked",
            "error": "organization_required",
        }

    revenue_reference = parameters.get("recorded_revenue_payment_id")
    recorded_revenue = None
    revenue_currency = None
    if revenue_reference is not None:
        from app.models.payment import Payment

        payment = Payment.query.filter_by(
            id=int(revenue_reference),
            organization_id=int(organization_id),
            status="paid",
        ).first()
        if payment is None:
            return {
                "success": False,
                "status": "blocked",
                "error": "recorded_revenue_reference_not_found",
                "executed": False,
            }
        recorded_revenue = float(payment.amount)
        revenue_currency = payment.currency

    result = RevenueAutopilotFacade.run_for_lead(
        int(lead_id),
        user_id=user_id,
        organization_id=int(organization_id),
    )
    if result.get("success") and recorded_revenue is not None:
        result["recorded_revenue"] = recorded_revenue
        result["revenue_currency"] = revenue_currency
        result["revenue_source"] = "payment_record"
        result["revenue_record_id"] = int(revenue_reference)
    return result


registry.register(
    "revenue_autopilot_plan",
    _revenue_autopilot_plan,
)

registry.register(
    "revenue_autopilot_run",
    _revenue_autopilot_run,
)

registry.register("business_insights", _business_insights)


# === GOVERNED ENGINEERING ACTIONS ===

def _engineering_health(parameters=None, user_id=None):
    return {
        "success": True,
        "status": "completed",
        "action": "health",
        "message": "Kemet AI health check passed.",
        "data": {"result": "KEMET_HEALTH_OK"},
        "read_only": True,
        "external_execution": False,
        "database_mutation": False,
    }


def _engineering_test_health(parameters=None, user_id=None):
    return {
        "success": True,
        "status": "completed",
        "action": "test_health",
        "message": "Kemet AI test health check passed.",
        "data": {"result": "KEMET_TEST_HEALTH_OK"},
        "read_only": True,
        "external_execution": False,
        "database_mutation": False,
    }


def _engineering_compile(parameters=None, user_id=None):
    import subprocess

    result = subprocess.run(
        ["python", "-m", "compileall", "-q", "app", "agent"],
        cwd=str(__import__("pathlib").Path(__file__).resolve().parents[2]),
        capture_output=True,
        text=True,
        timeout=120,
    )

    return {
        "success": result.returncode == 0,
        "status": "completed" if result.returncode == 0 else "failed",
        "action": "compile",
        "data": {
            "returncode": result.returncode,
            "stdout": result.stdout[-12000:],
            "stderr": result.stderr[-12000:],
        },
        "external_execution": False,
        "database_mutation": False,
    }


def _engineering_git_status(parameters=None, user_id=None):
    import subprocess

    result = subprocess.run(
        ["git", "status", "--short"],
        cwd=str(__import__("pathlib").Path(__file__).resolve().parents[2]),
        capture_output=True,
        text=True,
        timeout=120,
    )

    return {
        "success": result.returncode == 0,
        "status": "completed" if result.returncode == 0 else "failed",
        "action": "git_status",
        "data": {
            "returncode": result.returncode,
            "stdout": result.stdout[-12000:],
            "stderr": result.stderr[-12000:],
        },
        "read_only": True,
        "external_execution": False,
        "database_mutation": False,
    }


registry.register("health", _engineering_health)
registry.register("test_health", _engineering_test_health)
registry.register("compile", _engineering_compile)
registry.register("git_status", _engineering_git_status)


def _termux_engineering(parameters=None, user_id=None):
    from app.core.execution.termux_execution import termux_execution

    parameters = dict(parameters or {})
    operation = str(parameters.get("operation") or "").strip()
    plan = parameters.get("_execution_plan")
    authorization = parameters.get("_execution_authorization")
    action = str(parameters.get("_execution_action") or "termux_engineering").strip()
    if not isinstance(plan, dict) or not isinstance(authorization, dict):
        return {"success": False, "status": "blocked", "error": "termux_execution_binding_required", "executed": False}
    try:
        result = termux_execution.execute(
            operation=operation,
            plan=plan,
            authorization=authorization,
            action=action,
        )
        success = bool(result.get("ok"))
        return {
            "success": success,
            "status": "completed" if success else "failed",
            "type": "termux_engineering",
            "operation": operation,
            "result": result,
            "external_execution": True,
            "database_mutation": False,
            "executed": True,
        }
    except Exception as exc:
        return {"success": False, "status": "failed", "type": "termux_engineering", "error": str(exc), "executed": False}


registry.register("termux_engineering", _termux_engineering)


def _artifact_write(parameters=None, user_id=None):
    from app.core.execution.artifact_execution import artifact_execution
    from app.core.execution.artifact_termux_execution import artifact_termux_execution

    parameters = parameters or {}
    plan = parameters.get("_execution_plan")
    authorization = parameters.get("_execution_authorization")
    action = parameters.get("_execution_action")
    artifacts = parameters.get("artifacts")
    preview_digest = parameters.get("preview_digest") or parameters.get("artifact_preview_digest")
    if not isinstance(plan, dict) or not isinstance(authorization, dict):
        return {"success": False, "status": "blocked", "error": "artifact_execution_binding_required", "executed": False}
    if action != "artifact_write":
        return {"success": False, "status": "blocked", "error": "artifact_action_binding_invalid", "executed": False}
    if not isinstance(artifacts, list) or not artifacts:
        return {"success": False, "status": "blocked", "error": "artifact_binding_required", "executed": False}
    if not preview_digest:
        return {"success": False, "status": "blocked", "error": "artifact_preview_binding_required", "executed": False}
    try:
        preview = artifact_execution.preview(artifacts)
        if str(preview.get("digest")) != str(preview_digest):
            return {"success": False, "status": "blocked", "error": "artifact_preview_mismatch", "executed": False}
    except Exception as exc:
        return {"success": False, "status": "blocked", "error": str(exc), "executed": False}
    try:
        result = artifact_termux_execution.execute(
            artifacts=artifacts,
            plan=plan,
            authorization=authorization,
            action=action,
            preview_digest=str(preview_digest),
        )
        return {"success": True, "status": "completed", "type": "artifact_write", "result": result, "external_execution": True, "database_mutation": False, "executed": True}
    except Exception as exc:
        return {"success": False, "status": "failed", "type": "artifact_write", "error": str(exc), "executed": False}

registry.register("artifact_write", _artifact_write)


def _social_publish(parameters=None, user_id=None):
    from app.services.social_publishing_adapters import PublishRequest, social_publishing_adapter

    parameters = dict(parameters or {})
    organization_id = int(parameters.get("organization_id") or 0)
    channel = str(parameters.get("channel") or "").strip().lower()
    if channel not in {"facebook", "instagram"}:
        return {"success": False, "status": "blocked", "error": "unsupported_social_publish_channel", "executed": False}
    request = PublishRequest(
        organization_id=organization_id,
        user_id=int(user_id or parameters.get("user_id") or 0),
        channel=channel,
        asset_uri=str(parameters.get("asset_uri") or ""),
        media_type=str(parameters.get("media_type") or ""),
        caption=str(parameters.get("caption") or ""),
        title=str(parameters.get("title") or ""),
        idempotency_key=str(parameters.get("idempotency_key") or ""),
        production_job_id=str(parameters.get("production_job_id") or ""),
        publication_approval=bool(parameters.get("publication_approval", False)),
        publication_contract_digest=str(parameters.get("publication_contract_digest") or ""),
        dry_run=bool(parameters.get("dry_run", False)),
    )
    plan = parameters.get("_execution_plan") or {}
    authorization = parameters.get("_execution_authorization") or {}
    execution_key = str(plan.get("execution_key") or authorization.get("execution_key") or plan.get("plan_id") or "")
    return social_publishing_adapter.publish(request, execution_key=execution_key, plan_hash=plan.get("plan_hash"), approved_execution=parameters.get("_approved_execution") is True, execution_authorization=authorization)


registry.register("facebook_publish", _social_publish)
registry.register("instagram_publish", _social_publish)


def _tiktok_publish(parameters=None, user_id=None):
    from app.services.tiktok_publishing_adapter import TikTokPublishRequest, tiktok_publishing_adapter

    parameters = dict(parameters or {})
    request = TikTokPublishRequest(
        organization_id=int(parameters.get("organization_id") or 0),
        user_id=int(user_id or parameters.get("user_id") or 0),
        asset_uri=str(parameters.get("asset_uri") or ""),
        media_type=str(parameters.get("media_type") or "video"),
        caption=str(parameters.get("caption") or ""),
        idempotency_key=str(parameters.get("idempotency_key") or ""),
        production_job_id=str(parameters.get("production_job_id") or ""),
        publication_approval=bool(parameters.get("publication_approval", False)),
        publication_contract_digest=str(parameters.get("publication_contract_digest") or ""),
        dry_run=bool(parameters.get("dry_run", False)),
    )
    plan = parameters.get("_execution_plan") or {}
    authorization = parameters.get("_execution_authorization") or {}
    execution_key = str(plan.get("execution_key") or authorization.get("execution_key") or plan.get("plan_id") or "")
    return tiktok_publishing_adapter.publish(request, execution_key=execution_key, plan_hash=plan.get("plan_hash"), approved_execution=parameters.get("_approved_execution") is True, execution_authorization=authorization)


registry.register("tiktok_publish", _tiktok_publish)


# === GOVERNED YOUTUBE EXECUTION ===

def _youtube_publish(parameters=None, user_id=None):
    import json
    import os
    import pathlib
    import subprocess
    import tempfile

    parameters = dict(parameters or {})
    plan = parameters.get("_execution_plan")
    authorization = parameters.get("_execution_authorization")
    manifest = str(parameters.get("manifest") or "").strip()
    if not isinstance(plan, dict) or not isinstance(authorization, dict):
        return {"success": False, "status": "blocked", "error": "youtube_execution_binding_required", "executed": False}
    if str(plan.get("action") or "") != "youtube_publish":
        return {"success": False, "status": "blocked", "error": "youtube_action_binding_invalid", "executed": False}
    if not manifest:
        return {"success": False, "status": "blocked", "error": "youtube_manifest_required", "executed": False}
    root = pathlib.Path(__file__).resolve().parents[2]
    publisher = root / "ops" / "youtube_worker" / "publisher.mjs"
    manifest_path = pathlib.Path(manifest).expanduser().resolve()
    if not publisher.is_file() or not manifest_path.is_file():
        return {"success": False, "status": "blocked", "error": "youtube_worker_or_manifest_missing", "executed": False}
    auth_path = None
    try:
        fd, auth_path = tempfile.mkstemp(prefix="kemet-youtube-auth-", suffix=".json", dir=str(root / "ops" / "youtube_state"))
        os.chmod(auth_path, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(authorization, handle, separators=(",", ":"))
        result = subprocess.run(
            ["node", str(publisher), str(manifest_path), "--authorization-file", auth_path],
            cwd=str(root), capture_output=True, text=True, timeout=900,
        )
        output = (result.stdout or "").strip().splitlines()
        payload = output[-1] if output else ""
        try:
            data = json.loads(payload)
        except Exception:
            data = {"output": payload, "stderr": (result.stderr or "")[-4000:]}
        return {
            "success": result.returncode == 0,
            "status": "completed" if result.returncode == 0 else "failed",
            "type": "youtube_publish",
            "result": data,
            "external_execution": True,
            "database_mutation": False,
            "executed": result.returncode == 0,
        }
    except Exception as exc:
        return {"success": False, "status": "failed", "type": "youtube_publish", "error": str(exc), "executed": False}
    finally:
        if auth_path:
            try:
                os.unlink(auth_path)
            except OSError:
                pass


registry.register("youtube_publish", _youtube_publish)

from flask import Blueprint, jsonify, request, current_app
from flask_login import login_required, current_user
from app import csrf

from app.services.business_control_loop import BusinessControlLoopService
from app.services.business_feedback import business_feedback
from app.services.decision_learning import decision_learning
from app.services.decision_feedback_loop import decision_feedback_loop
from app.services.outcome_priority import OutcomePriorityService
from app.services.bos_intelligence import BOSIntelligenceService
from app.services.saas_control_plane import saas_control_plane
from app.services.monetization_guard import monetization_guard
from app.services.agentic_engineering_service import agentic_engineering_service
from app.services.evidence_backed_context_service import evidence_backed_context_service

from app.automation.orchestrator import orchestrator
from app.core.orchestration.command_center_wiring import KemetCommandCenterWiring
from app.core.decision.decision_engine import DecisionEngine


bos_command_bp = Blueprint(
    "bos_command",
    __name__,
    url_prefix="/api/bos",
)


def _notify_video_lead_owner(*, organization_id: int, message: dict, lead: dict | None = None, qualification: dict | None = None) -> dict:
    """Create one internal owner notification for a commercially relevant video inquiry."""
    text = str(message.get("text") or "").strip()
    lowered = text.lower()
    video_terms = ("video", "فيديو", "فيديوهات", "اعلان", "إعلان", "موشن", "motion", "كرتون", "cartoon", "سينمائي", "cinematic", "فيلم", "فلم")
    if not text or not any(term in lowered for term in video_terms):
        return {"notified": False, "reason": "not_video_intent"}
    from app.services.automation_service import AutomationService
    lead_data = lead or {}
    qual_data = qualification or {}
    title = "Kemet — New Video Lead"
    parts = [
        "A commercially relevant video request was received.",
        f"Telegram user: {message.get('external_user_id')}",
        f"Message ID: {message.get('external_message_id')}",
        f"Message: {text}",
    ]
    if lead_data.get("lead_id"):
        parts.append(f"Lead ID: {lead_data.get('lead_id')}")
    if qual_data.get("next_field"):
        parts.append(f"Next qualification field: {qual_data.get('next_field')}")
    result = AutomationService().send_notification(
        {"organization_id": int(organization_id), "title": title, "message": "\n".join(parts)},
        user_id=None,
    )
    return {"notified": bool(result.get("success")), "notification": result}


@bos_command_bp.get("/channels/<channel>/webhook")
def bos_channel_webhook_verify(channel):
    """Provider challenge endpoint; no unauthenticated payload is accepted."""
    channel = str(channel or "").strip().lower()
    if channel == "telegram":
        return jsonify({"success": False, "error": "telegram_challenge_not_supported"}), 404
    if channel != "whatsapp":
        return jsonify({"success": False, "error": "unsupported_channel"}), 404
    from app.services.channel_webhook_service import channel_webhook_service
    mode = request.args.get("hub.mode", "")
    token = request.args.get("hub.verify_token", "")
    challenge = request.args.get("hub.challenge", "")
    if mode != "subscribe" or not channel_webhook_service.verify_meta_challenge(verify_token=token, challenge=challenge):
        return jsonify({"success": False, "error": "webhook_verification_failed"}), 403
    return challenge, 200


@bos_command_bp.post("/fulfillment/bosta/webhook/<int:organization_id>")
def bos_bosta_webhook(organization_id):
    from app.services.bosta_connector_service import bosta_connector_service
    from app.core.event_ingestion_gateway import event_ingestion_gateway

    if not bosta_connector_service.verify_webhook(
        authorization=request.headers.get("Authorization", "")
    ):
        return jsonify({"success": False, "error": "webhook_authentication_failed"}), 403
    payload = request.get_json(silent=True) or {}
    try:
        event = bosta_connector_service.normalize_tracking_event(
            organization_id=int(organization_id), payload=payload
        )
        event_key = f"bosta:{int(organization_id)}:tracking:{event['order_id']}:{event.get('state')}:{event.get('timestamp')}"
        ingress = event_ingestion_gateway.ingest(
            organization_id=int(organization_id), event_type="fulfillment.bosta.tracking",
            payload=event, source="bosta.webhook", event_id=event_key, idempotency_key=event_key,
        )
        evidence = bosta_connector_service.record_tracking_evidence(
            organization_id=int(organization_id), event=event
        )
        return jsonify({"success": True, "status": "deduplicated" if not ingress.get("accepted") else "accepted",
                        "tracking": event, "evidence": evidence,
                        "ingress": {"record_id": ingress.get("record_id"), "status": ingress.get("status")},
                        "governance": {"verified_ingress": True, "durable_ingress": True,
                                       "external_execution": False, "database_mutation": True, "auto_execute": False}}), 200
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 422


@bos_command_bp.post("/channels/<channel>/webhook/<int:organization_id>")
@csrf.exempt
def bos_channel_webhook(channel, organization_id):
    """Verify provider authenticity, extract messages, then pass them to the canonical channel adapter."""
    from app.services.channel_webhook_service import channel_webhook_service
    from app.services.channel_adapter_service import channel_adapter_service
    from app.core.event_ingestion_gateway import event_ingestion_gateway
    channel = str(channel or "").strip().lower()
    raw_body = request.get_data(cache=True)
    if channel == "telegram":
        if not channel_webhook_service.verify_telegram(secret_token=request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")):
            return jsonify({"success": False, "error": "webhook_authentication_failed"}), 403
        payload = request.get_json(silent=True) or {}
        messages = [channel_webhook_service.extract_telegram(payload)]
    elif channel == "whatsapp":
        if not channel_webhook_service.verify_meta_signature(
            raw_body=raw_body,
            signature=request.headers.get("X-Hub-Signature-256", ""),
            organization_id=int(organization_id),
        ):
            return jsonify({"success": False, "error": "webhook_authentication_failed"}), 403
        payload = request.get_json(silent=True) or {}
        messages = channel_webhook_service.extract_meta(payload)
    else:
        return jsonify({"success": False, "error": "unsupported_channel"}), 404
    accepted = []
    rejected = []
    for message in messages:
        try:
            if channel == "whatsapp" and message.get("kind") == "delivery":
                from app.services.whatsapp_delivery_evidence_service import whatsapp_delivery_evidence_service
                status = whatsapp_delivery_evidence_service.normalize(
                    organization_id=int(organization_id),
                    payload={
                        "message_id": message.get("external_message_id"),
                        "status": message.get("status"),
                        "recipient_id": message.get("external_user_id"),
                        "metadata": message.get("metadata") or {},
                    },
                )
                binding = whatsapp_delivery_evidence_service.record_delivery(
                    organization_id=int(organization_id),
                    message_id=status["message_id"],
                    status=status["status"],
                    metadata=message.get("metadata") or {},
                )
                status["commercial_binding"] = binding
                event_key = whatsapp_delivery_evidence_service.event_key(
                    organization_id=int(organization_id),
                    message_id=status["message_id"],
                    status=status["status"],
                )
                event = event_ingestion_gateway.ingest(
                    organization_id=int(organization_id),
                    event_type="whatsapp.message.delivery",
                    payload=status,
                    source="whatsapp.cloud.webhook",
                    event_id=event_key,
                    idempotency_key=event_key,
                )
                accepted.append({"success": True, "status": "deduplicated" if not event.get("accepted") else "accepted", "delivery": status, "ingress": {"record_id": event.get("record_id"), "status": event.get("status")}})
                continue
            telegram_metadata = dict(message.get("metadata") or {})
            is_telegram_document = channel == "telegram" and telegram_metadata.get("telegram_update_kind") == "document"
            if not message.get("external_message_id") or not message.get("external_user_id") or (not message.get("text") and not is_telegram_document):
                raise ValueError("inbound_message_incomplete")
            event = event_ingestion_gateway.ingest(
                organization_id=int(organization_id),
                event_type=f"channel.{channel}.message",
                payload=message,
                source=f"{channel}.webhook",
                event_id=f"{channel}:{organization_id}:{message['external_message_id']}",
                idempotency_key=f"{channel}:{organization_id}:{message['external_message_id']}",
            )
            deduplicated = not event.get("accepted")
            normalized = channel_adapter_service.ingest(channel=channel, organization_id=organization_id, payload=message)
            if channel == "whatsapp":
                from app.services.channel_webhook_service import channel_webhook_service
                from app.services.revenue_pipeline_service import revenue_pipeline_service
                from app.services.commercial_qualification_conversation_service import commercial_qualification_conversation_service
                from app.models.revenue_pipeline import RevenuePipelineRecord

                whatsapp_user_id = str(message.get("external_user_id") or "").strip()
                whatsapp_message_id = str(message.get("external_message_id") or "").strip()
                whatsapp_phone = whatsapp_user_id
                incoming_text = str(message.get("text") or "").strip()
                identity = channel_webhook_service.extract_commercial_identity(incoming_text)

                candidates = RevenuePipelineRecord.query.filter_by(
                    organization_id=int(organization_id), source="whatsapp"
                ).order_by(
                    RevenuePipelineRecord.updated_at.desc(),
                    RevenuePipelineRecord.id.desc(),
                ).all()
                record = None
                for candidate in candidates:
                    whatsapp = dict((candidate.metadata_json or {}).get("whatsapp") or {})
                    if str(whatsapp.get("user_id") or "") == whatsapp_user_id:
                        record = candidate
                        break

                if record is None and identity.get("company_name") and identity.get("email"):
                    normalized["lead"] = revenue_pipeline_service.intake_whatsapp_prospect(
                        organization_id=int(organization_id),
                        whatsapp_user_id=whatsapp_user_id,
                        whatsapp_message_id=whatsapp_message_id,
                        company_name=identity["company_name"],
                        email=identity["email"],
                        phone=whatsapp_phone,
                        message=incoming_text,
                    )
                    record = RevenuePipelineRecord.query.filter_by(
                        organization_id=int(organization_id),
                        pipeline_key=str(normalized["lead"]["pipeline_key"]),
                    ).first()
                    normalized["lead_intake"] = "created_or_existing"
                    normalized["qualification"] = commercial_qualification_conversation_service.start_or_resume(
                        organization_id=int(organization_id),
                        pipeline_key=record.pipeline_key,
                        channel="whatsapp",
                    )
                elif record is not None:
                    normalized["lead"] = revenue_pipeline_service.snapshot(record)
                    normalized["qualification"] = commercial_qualification_conversation_service.ingest_answer(
                        organization_id=int(organization_id),
                        pipeline_key=record.pipeline_key,
                        text=incoming_text,
                        external_message_id=whatsapp_message_id,
                        channel="whatsapp",
                    )
                else:
                    normalized["lead_intake"] = "awaiting_explicit_company_and_email"
                    # Present the same canonical customer catalog on WhatsApp.
                    # This is a response plan only; external delivery remains approval-gated.
                    from app.services.channel_catalog_service import channel_catalog_service
                    try:
                        from app.services.whatsapp_cloud_api_service import whatsapp_cloud_api_service
                        normalized["whatsapp_response_plan"] = whatsapp_cloud_api_service.plan_send_text(
                            organization_id=int(organization_id),
                            recipient=whatsapp_user_id,
                            content=channel_catalog_service.whatsapp_home_text(),
                            external_message_id=whatsapp_message_id,
                            phone_number_id=str((message.get("metadata") or {}).get("phone_number_id") or ""),
                        )
                    except Exception as exc:
                        normalized["whatsapp_response_plan"] = {
                            "success": False,
                            "status": "blocked",
                            "error": type(exc).__name__,
                        }

                qualification_result = normalized.get("qualification") or {}
                if qualification_result.get("status") == "qualified":
                    try:
                        from app.services.commercial_offer_service import commercial_offer_service
                        answers = dict(qualification_result.get("qualification", {}).get("qualification") or {})
                        normalized["draft_offer"] = commercial_offer_service.draft_offer(
                            organization_id=int(organization_id),
                            pipeline_key=str((normalized.get("lead") or {}).get("pipeline_key") or ""),
                            offer_name="Kemet Document Intelligence — Pilot",
                            offer_description=(
                                "Pilot document-automation service: PDF/images/business documents to "
                                "clean Excel/CSV with validation, duplicate detection, review queue and client report. "
                                f"Requested scope: {answers.get('scope', '')}. Deadline: {answers.get('target_deadline', '')}."
                            ),
                            quoted_amount=400,
                            currency="EGP",
                        )
                    except Exception as exc:
                        normalized["draft_offer"] = {"status": "draft_creation_failed_closed", "error": type(exc).__name__}

                if qualification_result.get("question"):
                    from app.services.whatsapp_cloud_api_service import whatsapp_cloud_api_service
                    try:
                        normalized["whatsapp_response_plan"] = whatsapp_cloud_api_service.plan_send_text(
                            organization_id=int(organization_id),
                            recipient=whatsapp_user_id,
                            content=str(qualification_result["question"]),
                            external_message_id=whatsapp_message_id,
                            phone_number_id=str((message.get("metadata") or {}).get("phone_number_id") or ""),
                        )
                    except Exception as exc:
                        normalized["whatsapp_response_plan"] = {
                            "success": False,
                            "status": "blocked",
                            "error": type(exc).__name__,
                        }

            if is_telegram_document:
                from pathlib import Path
                from app.services.telegram_connection_service import telegram_connection_service
                from app.services.document_automation import process_files_v4, export_delivery_package_v4
                from app.models.revenue_pipeline import RevenuePipelineRecord
                file_id = str(telegram_metadata.get("document_file_id") or "").strip()
                chat_id = str(message.get("conversation_id") or "").strip()
                # Commercial gate: receiving a customer file is allowed before payment,
                # but final processing/delivery is not. Fulfillment starts only after
                # an evidence-backed paid/fulfillment pipeline state.
                pipeline = RevenuePipelineRecord.query.filter_by(
                    organization_id=int(organization_id),
                ).order_by(RevenuePipelineRecord.updated_at.desc(), RevenuePipelineRecord.id.desc()).first()
                if pipeline and pipeline.metadata_json and str((pipeline.metadata_json.get("telegram") or {}).get("chat_id") or "") == chat_id:
                    if pipeline.stage not in {"paid", "fulfillment"}:
                        telegram_connection_service.send_message(
                            chat_id=chat_id,
                            text=(
                                "📥 تم استلام الملف بنجاح.\n\n"
                                "سيبدأ Kemet المعالجة والتسليم النهائي بعد تأكيد الدفع. "
                                "لن يتم إرسال ملفات النتائج قبل ذلك.\n\n"
                                "الحالة الحالية: بانتظار الدفع | Awaiting payment."
                            ),
                        )
                        normalized["document_intelligence"] = {
                            "status": "intake_received_awaiting_payment",
                            "pipeline_stage": pipeline.stage,
                            "final_delivery_blocked": True,
                        }
                        return normalized
                original_name = str(telegram_metadata.get("document_file_name") or "telegram_upload").strip()
                safe_name = Path(original_name).name or "telegram_upload"
                upload_root = Path(current_app.instance_path) / "runtime_profit_demo" / "telegram_uploads" / str(organization_id) / str(message.get("external_message_id"))
                source_path = upload_root / safe_name
                try:
                    telegram_connection_service.download_file(file_id=file_id, destination=str(source_path))
                    result = process_files_v4([str(source_path)])
                    package_dir = upload_root / "delivery"
                    export_delivery_package_v4(result, str(package_dir))
                    summary = result.get("summary", {})
                    gate = result.get("readiness_gate", {}).get("status", "UNKNOWN")
                    reply = (
                        "✅ تم استلام المستند وتشغيل Kemet Document Intelligence V4.\n\n"
                        f"الملف: {safe_name}\n"
                        f"السجلات: {summary.get('records_extracted', 0)}\n"
                        f"صالحة: {summary.get('valid_records', 0)}\n"
                        f"تحتاج مراجعة: {summary.get('needs_review', 0)}\n"
                        f"الحالة: {gate}\n\n"
                        "المراجعة البشرية تظل المرجع النهائي."
                    )
                    chat_id = str(message.get("conversation_id") or "")
                    telegram_connection_service.send_message(
                        chat_id=chat_id,
                        text=reply,
                    )
                    delivery_files = [
                        ("clean.xlsx", "📊 ملف Excel المنظّم"),
                        ("clean.csv", "📄 ملف CSV المنظّم"),
                        ("client_report.json", "🧾 تقرير العميل"),
                    ]
                    delivery_sent = []
                    delivery_failures = []
                    for filename, caption in delivery_files:
                        delivery_path = package_dir / filename
                        if not delivery_path.is_file():
                            continue
                        try:
                            telegram_connection_service.send_document(
                                chat_id=chat_id,
                                document_path=str(delivery_path),
                                caption=caption,
                            )
                            delivery_sent.append(filename)
                        except Exception as delivery_exc:
                            delivery_failures.append({
                                "filename": filename,
                                "error": type(delivery_exc).__name__,
                            })
                    if delivery_failures:
                        telegram_connection_service.send_message(
                            chat_id=chat_id,
                            text="⚠️ تمت المعالجة بنجاح، لكن تعذر إرسال بعض ملفات التسليم داخل Telegram. الحزمة محفوظة داخل Kemet للمراجعة.",
                        )
                    normalized["document_intelligence"] = {
                        "status": "processed",
                        "readiness": gate,
                        "summary": summary,
                        "delivery_package": str(package_dir),
                        "delivery_files_sent": delivery_sent,
                        "delivery_failures": delivery_failures,
                    }
                except Exception as exc:
                    telegram_connection_service.send_message(
                        chat_id=str(message.get("conversation_id") or ""),
                        text=f"⚠️ تعذر معالجة الملف الآن: {type(exc).__name__}. أرسل ملف PDF/DOCX/TXT/CSV/XLSX مدعومًا.",
                    )
                    normalized["document_intelligence"] = {"status": "failed_closed", "error": type(exc).__name__}
            if channel == "telegram":
                from app.services.telegram_connection_service import telegram_connection_service
                from app.services.telegram_menu_service import telegram_menu_service
                incoming_text = str(message.get("text") or "").strip()
                telegram_metadata = dict(message.get("metadata") or {})
                if incoming_text == "/start":
                    menu = telegram_menu_service.language_menu()
                    try:
                        telegram_connection_service.send_message(
                            chat_id=str(message.get("conversation_id") or ""),
                            text="مرحبًا بك في Kemet 👋\nWelcome to Kemet 👋\n\nاختر اللغة / Choose your language",
                            reply_markup=menu.get("reply_markup"),
                        )
                        normalized["telegram_reply"] = "language_menu_sent"
                    except Exception as exc:
                        normalized["telegram_reply"] = "send_failed_closed"
                        normalized["telegram_reply_error"] = type(exc).__name__
                elif telegram_metadata.get("telegram_update_kind") == "callback_query":
                    callback_data = str(telegram_metadata.get("callback_data") or incoming_text).strip().lower()
                    callback_result = telegram_menu_service.route_callback(callback_data)
                    callback_query_id = str(telegram_metadata.get("callback_query_id") or "").strip()
                    if callback_query_id:
                        telegram_connection_service.answer_callback_query(callback_query_id=callback_query_id)
                    action = callback_result.get("action")
                    language = callback_result.get("language")
                    if action == "language_menu":
                        menu = telegram_menu_service.language_menu()
                        reply_text = "اختر اللغة / Choose your language:"
                    elif action == "orders_status":
                        menu = telegram_menu_service.submenu("orders", language=language)
                        from app.models.revenue_pipeline import RevenuePipelineRecord
                        chat_id = str(message.get("conversation_id") or "").strip()
                        pipelines = []
                        if chat_id:
                            candidates = RevenuePipelineRecord.query.filter_by(organization_id=int(organization_id)).order_by(RevenuePipelineRecord.updated_at.desc()).limit(20).all()
                            for record in candidates:
                                metadata = record.metadata_json or {}
                                telegram_meta = metadata.get("telegram") or {}
                                if str(telegram_meta.get("chat_id") or "") == chat_id:
                                    pipelines.append(record)
                        if not pipelines:
                            reply_text = (
                                "📋 لا توجد طلبات تجارية مسجلة لهذا الحساب حتى الآن.\n\n"
                                "No commercial requests are registered for this account yet."
                            )
                        else:
                            labels = {
                                "inquiry": "استفسار | Inquiry",
                                "qualified": "مؤهل | Qualified",
                                "proposal": "عرض سعر | Proposal",
                                "awaiting_payment": "بانتظار الدفع | Awaiting payment",
                                "paid": "تم الدفع | Paid",
                                "fulfillment": "قيد التنفيذ | Fulfillment",
                                "delivered": "تم التسليم | Delivered",
                                "closed": "مغلق | Closed",
                                "lost": "مغلق بدون إتمام | Lost",
                                "refunded": "مسترد | Refunded",
                            }
                            lines = ["📋 حالة طلباتك | Your Requests", ""]
                            for record in pipelines[:5]:
                                stage = labels.get(record.stage, record.stage)
                                amount = f"{record.quoted_amount:g} {record.currency}" if record.quoted_amount else "—"
                                lines.append(f"• {record.offer_name or 'Kemet Service'} — {stage} — {amount}")
                            lines.append("\nيمكنك العودة للقائمة أو متابعة التعليمات الظاهرة في الحالة.")
                            reply_text = "\n".join(lines)
                        normalized["telegram_order_status"] = {
                            "count": len(pipelines),
                            "chat_id_present": bool(chat_id),
                        }
                    elif action == "orders_deliveries":
                        menu = telegram_menu_service.submenu("orders", language=language)
                        from app.models.revenue_pipeline import RevenuePipelineRecord
                        chat_id = str(message.get("conversation_id") or "").strip()
                        deliveries = []
                        if chat_id:
                            candidates = RevenuePipelineRecord.query.filter_by(organization_id=int(organization_id)).order_by(RevenuePipelineRecord.delivered_at.desc(), RevenuePipelineRecord.updated_at.desc()).limit(50).all()
                            for record in candidates:
                                metadata = record.metadata_json or {}
                                telegram_meta = metadata.get("telegram") or {}
                                if str(telegram_meta.get("chat_id") or "") == chat_id and record.delivered_at and record.fulfillment_reference:
                                    deliveries.append(record)
                        if not deliveries:
                            reply_text = (
                                "📦 لا توجد تسليمات مكتملة مسجلة لهذا الحساب حتى الآن.\n\n"
                                "No completed deliveries are recorded for this account yet.\n\n"
                                "لن يتم عرض أي ملف أو رابط ما لم يكن التسليم مسجلًا فعليًا في السجل التجاري."
                            )
                        else:
                            lines = ["📦 تسليماتك | Your Deliveries", ""]
                            for record in deliveries[:5]:
                                delivered_at = record.delivered_at.isoformat(timespec="minutes") if record.delivered_at else "—"
                                lines.append(f"• {record.offer_name or 'Kemet Service'}")
                                lines.append(f"  الحالة: تم التسليم | Delivered")
                                lines.append(f"  مرجع التسليم | Delivery reference: {record.fulfillment_reference}")
                                lines.append(f"  التاريخ | Date: {delivered_at} UTC")
                            lines.append("\nهذه البيانات مبنية على سجل التسليم الفعلي فقط.")
                            reply_text = "\n".join(lines)
                        normalized["telegram_deliveries"] = {
                            "count": len(deliveries),
                            "chat_id_present": bool(chat_id),
                            "verified_from_pipeline": True,
                        }
                    elif action == "main_menu":
                        menu = telegram_menu_service.main_menu(language=language)
                        reply_text = menu.get("text") or "اختر ما تريد / Choose what you need:"
                    elif action == "submenu":
                        service = str(callback_result.get("service") or "")
                        menu = telegram_menu_service.submenu(service, language=language)
                        reply_text = menu.get("text") or "اختر ما تريد / Choose what you need:"
                    elif action == "document_upload":
                        menu = None
                        reply_text = (
                            "📤 أرسل المستند الآن | Send the document now.\n\n"
                            "PDF / DOCX / TXT / CSV / XLSX — حتى 25 MB.\n"
                            "Kemet سيستخرج البيانات ويتحقق منها ويحدد ما يحتاج مراجعة بشرية.\n"
                            "Kemet will extract, validate, and flag items for human review."
                        )
                    elif action == "invoice_upload":
                        menu = None
                        reply_text = (
                            "🧾 أرسل الفاتورة الآن | Send the invoice now.\n\n"
                            "Kemet سيحوّلها إلى بيانات منظمة ويجري التحقق."
                        )
                    elif action in {"jobs_browse", "jobs_categories", "jobs_question"}:
                        menu = telegram_menu_service.submenu("jobs", language=language)
                        reply_text = (
                            "💼 الوظائف | Jobs\n\n"
                            "سيعرض Kemet الوظائف التي تمر عبر المصدر المعتمد، مع إزالة التكرار والتحقق من حداثة البيانات.\n"
                            "Kemet shows jobs from authoritative sources, with deduplication and freshness checks.\n\n"
                            "يمكن لاحقًا ربط موقع الوظائف أو مصدر مُصرّح به ليصل المحتوى إلى Telegram وWhatsApp والموقع من نفس النظام."
                        )
                    elif action in {"financing_browse", "financing_request", "financing_info"}:
                        menu = telegram_menu_service.submenu("financing", language=language)
                        reply_text = (
                            "💰 التمويل | Financing\n\n"
                            "سيعرض Kemet فقط عروض التمويل التي تأتي من جهات أو مصادر موثوقة ومصرّح بها.\n"
                            "Kemet will show financing offers only from trusted, authorized sources.\n\n"
                            "أي مبلغ أو نسبة أو مدة سداد ستظهر كما وردت في العرض مع الشروط والرسوم والافتراضات، ولن يخترع Kemet عرضًا أو نتيجة أهلية."
                        )
                    elif action in {"service_document", "service_data", "service_automation"}:
                        menu = telegram_menu_service.submenu("services", language=language)
                        reply_text = (
                            "🛠️ الخدمة | Service\n\n"
                            "اختر من القائمة لعرض التفاصيل أو طلب الخدمة.\n"
                            "Use the buttons to view details or request the service."
                        )
                    elif action in {"products_digital", "products_details"}:
                        menu = telegram_menu_service.submenu("products", language=language)
                        reply_text = (
                            "🛍️ المنتجات | Products\n\n"
                            "المنتجات المتاحة تُعرض من الكتالوج المعتمد فقط.\n"
                            "Only products in the authoritative catalog are shown."
                        )
                    elif action == "pricing":
                        menu = telegram_menu_service.submenu("services", language=language)
                        reply_text = (
                            "💰 الأسعار | Pricing\n\n"
                            "السعر يعتمد على المنتج أو نطاق الخدمة المؤكد.\n"
                            "Pricing depends on the confirmed product or service scope."
                        )
                    elif action in {"document_details", "invoice_details", "data_files", "data_cleaning",
                                    "orders_status", "orders_deliveries", "help", "human_support",
                                    "automation_request", "automation_examples"}:
                        menu = telegram_menu_service.submenu(
                            "support" if action in {"help", "human_support"}
                            else "orders" if action in {"orders_status", "orders_deliveries"}
                            else "automation" if action in {"automation_request", "automation_examples"}
                            else "document" if action == "document_details"
                            else "invoice" if action == "invoice_details"
                            else "data",
                            language=language,
                        )
                        reply_text = (
                            "اختر من الأزرار التالية / Choose from the buttons below.\n\n"
                            "لا يتم تنفيذ إجراء خارجي تلقائيًا من هذه الواجهة.\n"
                            "No external action is executed automatically from this interface."
                        )
                    else:
                        menu = telegram_menu_service.main_menu(language=language)
                        reply_text = "اختر ما تريد / Choose what you need:"
                    chat_id = str(message.get("conversation_id") or "")
                    callback_message_id = str(telegram_metadata.get("callback_message_id") or "").strip()
                    if callback_message_id:
                        try:
                            telegram_connection_service.edit_message(
                                chat_id=chat_id,
                                message_id=callback_message_id,
                                text=reply_text,
                                reply_markup=(menu or {}).get("reply_markup"),
                            )
                            normalized["telegram_reply"] = action
                            normalized["telegram_navigation"] = "edited_in_place"
                        except Exception as exc:
                            telegram_connection_service.send_message(
                                chat_id=chat_id,
                                text=reply_text,
                                reply_markup=(menu or {}).get("reply_markup"),
                            )
                            normalized["telegram_reply"] = action
                            normalized["telegram_navigation"] = "send_fallback"
                            normalized["telegram_navigation_error"] = type(exc).__name__
                    else:
                        telegram_connection_service.send_message(
                            chat_id=chat_id,
                            text=reply_text,
                            reply_markup=(menu or {}).get("reply_markup"),
                        )
                        normalized["telegram_reply"] = action
                        normalized["telegram_navigation"] = "send_message"
                from app.services.channel_webhook_service import channel_webhook_service
                from app.services.revenue_pipeline_service import revenue_pipeline_service
                identity = channel_webhook_service.extract_telegram_commercial_identity(message.get("text", ""))
                from app.services.commercial_qualification_conversation_service import commercial_qualification_conversation_service
                from app.models.revenue_pipeline import RevenuePipelineRecord
                if identity.get("company_name") and identity.get("email"):
                    lead = revenue_pipeline_service.intake_telegram_prospect(
                        organization_id=int(organization_id),
                        telegram_user_id=str(message.get("external_user_id") or ""),
                        telegram_chat_id=str(message.get("conversation_id") or ""),
                        telegram_message_id=str(message.get("external_message_id") or ""),
                        company_name=identity["company_name"],
                        email=identity["email"],
                        message=str(message.get("text") or ""),
                    )
                    normalized["lead"] = lead
                    normalized["lead_intake"] = "created_or_existing"
                    normalized["qualification"] = commercial_qualification_conversation_service.start_or_resume(
                        organization_id=int(organization_id), pipeline_key=lead["pipeline_key"], channel="telegram"
                    )
                else:
                    normalized["lead_intake"] = "awaiting_explicit_company_and_email"
                    chat_id = str(message.get("conversation_id") or "")
                    record = None
                    fallback_record = None
                    best_in_progress = None
                    best_in_progress_score = -1
                    best_qualified = None
                    candidates = RevenuePipelineRecord.query.filter_by(
                        organization_id=int(organization_id), source="telegram"
                    ).order_by(
                        RevenuePipelineRecord.updated_at.desc(),
                        RevenuePipelineRecord.id.desc(),
                    ).all()
                    for candidate in candidates:
                        telegram = dict((candidate.metadata_json or {}).get("telegram") or {})
                        if str(telegram.get("chat_id") or "") != chat_id:
                            continue
                        if fallback_record is None:
                            fallback_record = candidate
                        conversation = dict(
                            (candidate.metadata_json or {}).get("commercial_qualification_conversation") or {}
                        )
                        status = str(conversation.get("status") or "").strip().lower()
                        answers = dict(conversation.get("answers") or {})
                        score = sum(1 for field in commercial_qualification_conversation_service.REQUIRED
                                    if str(answers.get(field) or "").strip())
                        if status == "qualified":
                            best_qualified = candidate
                        elif status == "qualification_in_progress" and score > best_in_progress_score:
                            best_in_progress = candidate
                            best_in_progress_score = score
                    # Keep one canonical conversation per Telegram chat: prefer a completed
                    # qualification, otherwise the in-progress record with the most answers.
                    record = best_qualified or best_in_progress or fallback_record
                    if record:
                        normalized["lead"] = revenue_pipeline_service.snapshot(record)
                        normalized["qualification"] = commercial_qualification_conversation_service.ingest_answer(
                            organization_id=int(organization_id), pipeline_key=record.pipeline_key,
                            text=str(message.get("text") or ""),
                            external_message_id=str(message.get("external_message_id") or ""), channel="telegram"
                        )
                qualification_result = normalized.get("qualification") or {}
                if qualification_result.get("status") == "qualified":
                    # Qualification completion creates an internal Draft Offer only.
                    # The quoted amount is a draft based on the first-customer pilot range;
                    # external offer sending remains human-approval gated.
                    try:
                        from app.services.commercial_offer_service import commercial_offer_service
                        answers = dict(qualification_result.get("qualification", {}).get("qualification") or {})
                        draft = commercial_offer_service.draft_offer(
                            organization_id=int(organization_id),
                            pipeline_key=str((normalized.get("lead") or {}).get("pipeline_key") or ""),
                            offer_name="Kemet Document Intelligence — Pilot",
                            offer_description=(
                                "Pilot document-automation service: PDF/images/business documents to "
                                "clean Excel/CSV with validation, duplicate detection, review queue and client report. "
                                f"Requested scope: {answers.get('scope', '')}. Deadline: {answers.get('target_deadline', '')}."
                            ),
                            quoted_amount=400,
                            currency="EGP",
                        )
                        normalized["draft_offer"] = draft
                    except Exception as exc:
                        normalized["draft_offer"] = {"status": "draft_creation_failed_closed", "error": type(exc).__name__}
                if qualification_result.get("question"):
                    try:
                        telegram_connection_service.send_message(
                            chat_id=str(message.get("conversation_id") or ""),
                            text=str(qualification_result["question"]),
                        )
                        normalized["qualification_reply"] = "question_sent"
                    except Exception as exc:
                        normalized["qualification_reply"] = "send_failed_closed"
                        normalized["qualification_reply_error"] = type(exc).__name__
                elif qualification_result.get("status") == "qualified":
                    # Qualification completion is recorded internally; do not send a
                    # redundant confirmation message to the Telegram user.
                    normalized["qualification_reply"] = "qualification_complete_ack_suppressed"
                normalized["owner_notification"] = _notify_video_lead_owner(
                    organization_id=int(organization_id),
                    message=message,
                    lead=normalized.get("lead"),
                    qualification=normalized.get("qualification"),
                )
            normalized["ingress"] = {"record_id": event.get("record_id"), "status": event.get("status"), "intents": event.get("intents", [])}
            normalized["status"] = "deduplicated" if deduplicated else normalized.get("status", "accepted")
            accepted.append(normalized)
        except ValueError as exc:
            rejected.append({"error": str(exc)})
    return jsonify({"success": True, "channel": channel, "organization_id": organization_id, "accepted": accepted, "rejected": rejected, "governance": {"verified_ingress": True, "durable_ingress": True, "external_execution": False, "database_mutation": True, "auto_execute": False, "human_approval_required_for_actions": True}}), 200


@bos_command_bp.post("/agentic/contract")
@login_required
def bos_agentic_contract():
    organization_id = getattr(current_user, "organization_id", None)
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    guard = monetization_guard.feature(organization_id, "bos")
    if not guard.get("allowed"):
        return jsonify(guard), 403
    data = request.get_json(silent=True) or {}
    try:
        result = agentic_engineering_service.contract(
            agent_id=data.get("agent_id"),
            provider_id=data.get("provider_id", "kemet"),
            kind=data.get("kind", "business"),
            capabilities=data.get("capabilities", []),
            authority=data.get("authority", "governed_submission"),
            execution_authority=bool(data.get("execution_authority", False)),
            supports_async=bool(data.get("supports_async", False)),
            metadata={"organization_id": organization_id},
        )
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 422
    return jsonify({"success": True, "contract": result}), 200


@bos_command_bp.post("/agentic/context")
@login_required
def bos_agentic_context():
    organization_id = getattr(current_user, "organization_id", None)
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    guard = monetization_guard.feature(organization_id, "bos")
    if not guard.get("allowed"):
        return jsonify(guard), 403
    data = request.get_json(silent=True) or {}
    try:
        result = evidence_backed_context_service.build(
            organization_id=organization_id,
            query=data.get("query"),
            task_id=data.get("task_id"),
            limit=data.get("limit", 5),
            policy=data.get("policy"),
            routing=data.get("routing"),
            project_context_hash=data.get("project_context_hash"),
            source_metadata=data.get("source_metadata"),
        )
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 422
    return jsonify({"success": True, "context": result}), 200


@bos_command_bp.post("/agentic/evaluate")
@login_required
def bos_agentic_evaluate():
    organization_id = getattr(current_user, "organization_id", None)
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    guard = monetization_guard.feature(organization_id, "bos")
    if not guard.get("allowed"):
        return jsonify(guard), 403
    data = request.get_json(silent=True) or {}
    lifecycle = dict(data.get("lifecycle") or {})
    lifecycle["organization_id"] = organization_id
    result = agentic_engineering_service.observability(lifecycle=lifecycle)
    return jsonify({"success": True, "observability": result}), 200


_kemet_command_center = KemetCommandCenterWiring()
_kemet_decision_engine = DecisionEngine()
@bos_command_bp.get("/saas-control")
@login_required
def bos_saas_control():
    organization_id = getattr(current_user, "organization_id", None)
    result = saas_control_plane.overview(organization_id)
    return jsonify(result), 200 if result.get("success") else 400


@bos_command_bp.post("/plan")
@login_required
def bos_command_plan():
    data = request.get_json(silent=True) or {}
    command = str(data.get("command") or data.get("instruction") or "").strip()
    if not command:
        return jsonify({"success": False, "error": "command_required"}), 400
    try:
        plan = orchestrator.plan(command)
        return jsonify(plan), 200
    except ValueError as exc:
        return jsonify({
            "success": False,
            "status": "unmapped",
            "error": "command_not_mapped",
            "message": str(exc),
        }), 422
    except Exception:
        return jsonify({
            "success": False,
            "error": "planner_error",
            "message": "Planner could not safely create a plan.",
        }), 500


@bos_command_bp.post("/command")
@login_required
def bos_command():
    # Kemet advisory intelligence layer.
    # Existing orchestrator execution remains intact and governed.
    kemet_center = KemetCommandCenterWiring()

    data = request.get_json(silent=True) or {}

    command = str(
        data.get("command")
        or data.get("instruction")
        or ""
    ).strip()

    if not command:
        return jsonify({
            "success": False,
            "error": "command_required",
        }), 400

    organization_id = getattr(
        current_user,
        "organization_id",
        None,
    )

    user_id = getattr(
        current_user,
        "id",
        None,
    )

    if not organization_id:
        return jsonify({
            "success": False,
            "error": "organization_required",
        }), 400

    # Kemet live business context.
    # Tenant identity is derived from the authenticated user.
    live_command_context = _kemet_command_center.build_command_context(
        organization_id=organization_id,
        user_id=user_id,
        message=command,
    )

    # Kemet Decision Engine consumes the live tenant context.
    live_decision = _kemet_decision_engine.decide(
        command=command,
        live_context=live_command_context,
    )

    try:
        result = orchestrator.execute(
            command,
            organization_id=organization_id,
            user_id=user_id,
        )

        status = result.get("status", "unknown")

        if not result.get("success", False):
            if status in {
                "waiting_approval",
                "pending",
            }:
                http_status = 200
            else:
                http_status = 422
        else:
            http_status = 200

        return jsonify({
            "success": result.get("success", False),
            "status": status,
            "command": command,
            "organization_id": organization_id,
            "user_id": user_id,
            "intent": result.get("intent"),
            "action": result.get("action"),
            "parameters": result.get("parameters", {}),
            "confidence": result.get("confidence"),
            "requires_approval": result.get(
                "requires_approval",
                False,
            ),
            "workflow_id": result.get("workflow_id"),
            "workflow_name": result.get("workflow_name"),
            "result": result.get("result"),
            "live_context": live_command_context,
            "decision": live_decision,
            "dispatch": result.get("dispatch"),
            "reason": result.get("reason"),
            "message": result.get("message"),
        }), http_status

    except Exception as exc:
        return jsonify({
            "success": False,
            "error": "orchestrator_error",
            "message": str(exc),
        }), 500


@bos_command_bp.get("/capabilities/analytics")
@login_required
def bos_capability_analytics():
    from app.services.capability_analytics import capability_analytics
    organization_id = getattr(current_user, "organization_id", None)
    gate = monetization_guard.feature(organization_id, "advanced_analytics")
    if not gate.get("allowed"):
        return jsonify({"success": False, "error": "feature_not_entitled", "reason": gate.get("reason"), "plan": gate.get("plan")}), 403
    return jsonify(capability_analytics.summary(organization_id)), 200


@bos_command_bp.get("/capabilities")
@login_required
def bos_capabilities():
    organization_id = getattr(current_user, "organization_id", None)
    gate = monetization_guard.feature(organization_id, "bos")
    if not gate.get("allowed"):
        return jsonify({"success": False, "error": "feature_not_entitled", "reason": gate.get("reason"), "plan": gate.get("plan")}), 403
    from app.services.capability_registry import capability_registry
    lifecycle = request.args.get("lifecycle")
    try:
        data = capability_registry.catalog(lifecycle=lifecycle)
    except ValueError:
        return jsonify({"success": False, "error": "invalid_lifecycle"}), 400
    return jsonify({"success": True, "engine": "kemet_capability_registry", "version": capability_registry.VERSION, "data": data}), 200


@bos_command_bp.get("/capabilities/<path:capability_id>")
@login_required
def bos_capability(capability_id):
    organization_id = getattr(current_user, "organization_id", None)
    gate = monetization_guard.capability(organization_id, capability_id)
    if not gate.get("allowed"):
        return jsonify({"success": False, "error": "feature_not_entitled", "reason": gate.get("reason"), "capability_id": capability_id, "plan": gate.get("plan")}), 403
    from app.services.capability_registry import capability_registry
    definition = capability_registry.get(capability_id)
    if not definition:
        return jsonify({"success": False, "error": "capability_not_found"}), 404
    return jsonify({"success": True, "engine": "kemet_capability_registry", "version": capability_registry.VERSION, "data": definition}), 200


@bos_command_bp.post("/capabilities/<path:capability_id>/plan")
@login_required
def bos_capability_plan(capability_id):
    organization_id = getattr(current_user, "organization_id", None)
    gate = monetization_guard.capability(organization_id, capability_id)
    if not gate.get("allowed"):
        return jsonify({"success": False, "error": "feature_not_entitled", "reason": gate.get("reason"), "capability_id": capability_id, "plan": gate.get("plan")}), 403
    from app.services.capability_registry import capability_registry
    data = request.get_json(silent=True) or {}
    try:
        result = capability_registry.plan(capability_id, data.get("parameters") or {})
        return jsonify(result), 200
    except ValueError:
        return jsonify({"success": False, "error": "capability_unavailable"}), 422


@bos_command_bp.get("/playbooks")
@login_required
def bos_playbooks():
    from app.automation.playbook_engine import playbook_engine
    return jsonify({
        "success": True,
        "engine": "kemet_playbook_catalog",
        "version": playbook_engine.VERSION,
        "governance": {"advisory": True, "approval_required": True, "external_execution": False},
        "data": playbook_engine.catalog(),
    }), 200


@bos_command_bp.get("/playbooks/<action>")
@login_required
def bos_playbook(action):
    from app.automation.playbook_engine import playbook_engine
    definition = playbook_engine.get_definition(action)
    if not definition:
        return jsonify({"success": False, "error": "playbook_not_found"}), 404
    return jsonify({
        "success": True,
        "engine": "kemet_playbook_catalog",
        "version": playbook_engine.VERSION,
        "data": definition,
        "governance": {"advisory": True, "approval_required": True, "external_execution": False},
    }), 200


@bos_command_bp.post("/capabilities/<path:capability_id>/attribution")
@login_required
def bos_capability_attribution(capability_id):
    organization_id = getattr(current_user, "organization_id", None)
    data = request.get_json(silent=True) or {}
    from app.services.business_outcome_attribution import BusinessOutcomeAttribution
    result = BusinessOutcomeAttribution.build(
        organization_id, capability_id, data.get("before") or {}, data.get("after") or {}
    )
    return jsonify(result), 200 if result.get("success") else (400 if result.get("error") == "organization_required" else 404)


@bos_command_bp.post("/outcome-decision-loop")
@login_required
def outcome_decision_loop():
    """Read-only feedback loop: observed outcomes re-rank pending decisions."""
    try:
        organization_id = getattr(current_user, "organization_id", None)
        if not organization_id:
            return jsonify({"success": False, "error": "organization_required"}), 400
        payload = request.get_json(silent=True) or {}
        period = payload.get("period", "30d")
        decisions = payload.get("decisions")
        if decisions is None:
            decisions = BOSIntelligenceService.get_decisions(organization_id, limit=10)
        ranked = OutcomePriorityService.rank(organization_id, decisions, period=period)
        return jsonify({
            "success": True,
            "engine": "kemet_outcome_decision_loop",
            "version": "1.0",
            "organization_id": organization_id,
            "period": period,
            "items": ranked.get("decisions", ranked.get("items", [])),
            "count": len(ranked.get("decisions", ranked.get("items", []))),
            "feedback": {"observed_outcomes": True, "re_ranking": True, "causal_claim": False, "roi_claim": False},
            "governance": {"read_only": True, "advisory": True, "external_execution": False, "database_mutation": False, "approval_required_for_execution": True},
        }), 200
    except Exception:
        current_app.logger.exception("outcome_decision_loop_unavailable")
        return jsonify({"success": False, "error": "outcome_decision_loop_unavailable"}), 500


@bos_command_bp.post("/outcome-priority")
@login_required
def bos_outcome_priority():
    from app.services.outcome_priority import outcome_priority
    organization_id = getattr(current_user, "organization_id", None)
    data = request.get_json(silent=True) or {}
    period = str(data.get("period") or "30d").strip()
    decisions = data.get("decisions") or []
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    try:
        result = outcome_priority.rank(organization_id, decisions, period)
        return jsonify(result), 200 if result.get("success") else 400
    except Exception:
        return jsonify({"success": False, "error": "outcome_priority_unavailable", "message": "Kemet could not safely rank outcome priorities."}), 500


@bos_command_bp.post("/decision-learning")
@login_required
def bos_decision_learning():
    organization_id = getattr(current_user, "organization_id", None)
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    data = request.get_json(silent=True) or {}
    period = str(data.get("period") or "30d").strip()
    decisions = data.get("decisions") or []
    try:
        result = decision_learning.enrich(organization_id, decisions, period=period)
        return jsonify(result), 200 if result.get("success") else 400
    except Exception:
        return jsonify({"success": False, "error": "decision_learning_unavailable", "message": "Kemet could not safely build decision learning signals."}), 500


@bos_command_bp.get("/decision-learning")
@login_required
def bos_decision_learning_summary():
    organization_id = getattr(current_user, "organization_id", None)
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    period = str(request.args.get("period") or "30d").strip()
    try:
        decisions = BOSIntelligenceService.get_decisions(organization_id, limit=10)
        result = decision_learning.build(organization_id, decisions, period=period)
        return jsonify(result), 200 if result.get("success") else 400
    except Exception:
        return jsonify({"success": False, "error": "decision_learning_unavailable", "message": "Kemet could not safely build decision learning signals."}), 500


@bos_command_bp.post("/provider-decision-review")
@login_required
def bos_provider_decision_review():
    organization_id = getattr(current_user, "organization_id", None)
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    data = request.get_json(silent=True) or {}
    business_intelligence = data.get("business_intelligence")
    if not isinstance(business_intelligence, dict):
        return jsonify({"success": False, "error": "business_intelligence_required"}), 422
    try:
        from app.services.provider_decision_intelligence_service import provider_decision_intelligence
        result = provider_decision_intelligence.analyze(
            business_intelligence,
            organization_id=organization_id,
            preferred=data.get("preferred_provider"),
            model=data.get("model"),
        )
        return jsonify({"success": True, "result": result}), 200
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 422
    except Exception:
        current_app.logger.exception("provider_decision_review_unavailable")
        return jsonify({"success": False, "error": "provider_decision_review_unavailable"}), 503


@bos_command_bp.get("/ml-decision-review")
@login_required
def bos_ml_decision_review():
    organization_id = getattr(current_user, "organization_id", None)
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    try:
        from app.services.ml_decision_review_service import ml_decision_review_service
        review = ml_decision_review_service.build_empty_review(organization_id=int(organization_id))
        return jsonify({"success": True, "review": review}), 200
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception:
        current_app.logger.exception("ml_decision_review_unavailable")
        return jsonify({"success": False, "error": "ml_decision_review_unavailable"}), 503


@bos_command_bp.get("/ml-evaluation-readiness")
@login_required
def bos_ml_evaluation_readiness():
    organization_id = getattr(current_user, "organization_id", None)
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    try:
        from app.services.ml_evaluation_capability import ml_evaluation_capability
        snapshot = ml_evaluation_capability.snapshot()
        return jsonify({
            "success": True,
            "organization_id": int(organization_id),
            "capability": snapshot,
            "decision_review": {
                "status": "review_required",
                "dataset_authorization": "required",
                "authorized_dataset_present": False,
                "benchmark_status": "blocked_until_authorized_dataset",
                "evidence_completion_status": "not_available_until_authorized_dataset",
                "evidence_completion_digest": None,
                "execution_authority": "none",
                "human_review_required": True,
            },
            "governance": {
                "advisory": True,
                "read_only": True,
                "external_execution": False,
                "auto_train": False,
                "auto_deploy": False,
                "policy_mutation": False,
            },
        }), 200
    except Exception:
        current_app.logger.exception("ml_evaluation_readiness_unavailable")
        return jsonify({"success": False, "error": "ml_evaluation_readiness_unavailable"}), 503


@bos_command_bp.get("/decision-intelligence")
@login_required
def bos_decision_intelligence():
    organization_id = getattr(current_user, "organization_id", None)
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    period = str(request.args.get("period") or "30d").strip()
    try:
        decisions = BOSIntelligenceService.get_decisions(organization_id, limit=10)
        from app.services.decision_intelligence import decision_intelligence
        result = decision_intelligence.build(organization_id, decisions, period=period)
        return jsonify(result), 200 if result.get("success") else 400
    except Exception:
        return jsonify({"success": False, "error": "decision_intelligence_unavailable", "message": "Kemet could not safely build decision intelligence."}), 500


@bos_command_bp.get("/outcome-intelligence")
@login_required
def bos_outcome_intelligence():
    from app.services.outcome_intelligence import outcome_intelligence
    organization_id = getattr(current_user, "organization_id", None)
    period = str(request.args.get("period") or "30d").strip()
    capability_id = request.args.get("capability_id")
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    try:
        if capability_id:
            result = outcome_intelligence.build(organization_id, capability_id, period)
        else:
            result = outcome_intelligence.summary(organization_id, period=period)
        return jsonify(result), 200 if result.get("success") else 404
    except Exception:
        return jsonify({"success": False, "error": "outcome_intelligence_unavailable", "message": "Kemet could not safely build outcome intelligence."}), 500


@bos_command_bp.post("/channels/<channel>/ingest")
@login_required
def bos_channel_ingest(channel):
    """Normalize an inbound channel message into the single Kemet core request contract."""
    organization_id = getattr(current_user, "organization_id", None)
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    gate = monetization_guard.feature(organization_id, "bos")
    if not gate.get("allowed"):
        return jsonify({"success": False, "error": "feature_not_entitled", "reason": gate.get("reason"), "plan": gate.get("plan")}), 403
    data = request.get_json(silent=True) or {}
    from app.services.channel_adapter_service import channel_adapter_service
    try:
        result = channel_adapter_service.ingest(channel=channel, organization_id=int(organization_id), payload=data)
        return jsonify(result), 200
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 422


@bos_command_bp.post("/channels/<channel>/response-plan")
@login_required
def bos_channel_response_plan(channel):
    """Create a read-only outbound proposal; actual delivery remains approval-gated and provider-neutral."""
    organization_id = getattr(current_user, "organization_id", None)
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    gate = monetization_guard.feature(organization_id, "bos")
    if not gate.get("allowed"):
        return jsonify({"success": False, "error": "feature_not_entitled", "reason": gate.get("reason"), "plan": gate.get("plan")}), 403
    data = request.get_json(silent=True) or {}
    from app.services.channel_adapter_service import channel_adapter_service
    try:
        result = channel_adapter_service.response_plan(
            channel=channel,
            organization_id=int(organization_id),
            content=data.get("content", ""),
            requires_approval=bool(data.get("requires_approval", False)),
        )
        return jsonify(result), 200
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 422


@bos_command_bp.post("/voice/commercial-context")
@login_required
def bos_voice_commercial_context():
    """Return a read-only commercial bridge for a completed voice interaction."""
    organization_id = getattr(current_user, "organization_id", None)
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    gate = monetization_guard.feature(organization_id, "bos")
    if not gate.get("allowed"):
        return jsonify({"success": False, "error": "feature_not_entitled", "reason": gate.get("reason"), "plan": gate.get("plan")}), 403
    data = request.get_json(silent=True) or {}
    from app.services.voice_call_service import voice_call_service
    try:
        event = voice_call_service.normalize(
            organization_id=int(organization_id),
            external_call_id=data.get("external_call_id", ""),
            caller_id=data.get("caller_id", ""),
            state=data.get("state", ""),
            text=data.get("text", ""),
            language=data.get("language"),
            intent=data.get("intent"),
            metadata=data.get("metadata"),
        )
        context = voice_call_service.commercial_context(
            event,
            execution_key=data.get("execution_key"),
        )
        if context["execution_link"]["execution_key"]:
            from app.services.commercial_outcome_trace import commercial_outcome_trace
            trace = commercial_outcome_trace.get(
                organization_id=int(organization_id),
                execution_key=context["execution_link"]["execution_key"],
            )
            context["execution_link"]["status"] = "linked" if trace is not None else "not_found"
            context["trace_available"] = trace is not None
        else:
            context["trace_available"] = False
        return jsonify({
            "success": True,
            "engine": "kemet_voice_callops_bridge",
            "version": voice_call_service.VERSION,
            "context": context,
            "governance": {
                "read_only": True,
                "external_execution": False,
                "database_mutation": False,
                "human_approval_required": True,
            },
        }), 200
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 422


@bos_command_bp.post("/commerce/creative-brief")
@login_required
def bos_commerce_creative_brief():
    """Build a read-only commerce creative brief inside Kemet."""
    organization_id = getattr(current_user, "organization_id", None)
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    gate = monetization_guard.feature(organization_id, "bos")
    if not gate.get("allowed"):
        return jsonify({"success": False, "error": "feature_not_entitled", "reason": gate.get("reason"), "plan": gate.get("plan")}), 403
    data = request.get_json(silent=True) or {}
    from app.services.ecommerce_creative_service import ecommerce_creative_service
    try:
        result = ecommerce_creative_service.build_brief(
            data.get("product") or {},
            objective=data.get("objective", "sales"),
            audience=data.get("audience", ""),
            channel=data.get("channel", "web"),
            output_type=data.get("output_type", "product_showcase"),
            language=data.get("language", "ar"),
            style=data.get("style", ""),
        )
        result["organization_id"] = int(organization_id)
        return jsonify(result), 200
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 422


@bos_command_bp.post("/workforce/revenue-contract")
@login_required
def bos_revenue_workforce_contract():
    """Build a read-only Revenue Workforce Contract v1."""
    organization_id = getattr(current_user, "organization_id", None)
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    gate = monetization_guard.feature(organization_id, "bos")
    if not gate.get("allowed"):
        return jsonify({"success": False, "error": "feature_not_entitled", "reason": gate.get("reason"), "plan": gate.get("plan")}), 403
    data = request.get_json(silent=True) or {}
    from app.services.revenue_workforce_contract import revenue_workforce_contract
    try:
        result = revenue_workforce_contract.build(
            organization_id=int(organization_id), product=data.get("product") or {},
            qualification=data.get("qualification") or {}, lead_id=data.get("lead_id"),
            customer_id=data.get("customer_id"), channel=data.get("channel", "web"),
            audience=data.get("audience", ""), style=data.get("style", ""),
            language=data.get("language", "ar"),
            context_query=data.get("context_query"),
            task_id=data.get("task_id"),
            context_limit=data.get("context_limit", 5),
        )
        return jsonify(result), 200
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 422


@bos_command_bp.post("/voice/qualification")
@login_required
def bos_voice_qualification():
    """Build a read-only qualification plan from a completed voice event."""
    organization_id = getattr(current_user, "organization_id", None)
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    gate = monetization_guard.feature(organization_id, "bos")
    if not gate.get("allowed"):
        return jsonify({"success": False, "error": "feature_not_entitled", "reason": gate.get("reason"), "plan": gate.get("plan")}), 403
    data = request.get_json(silent=True) or {}
    from app.services.voice_call_service import voice_call_service
    from app.services.voice_qualification_service import voice_qualification_service
    try:
        event = voice_call_service.normalize(
            organization_id=int(organization_id),
            external_call_id=data.get("external_call_id", ""),
            caller_id=data.get("caller_id", ""),
            state=data.get("state", ""),
            text=data.get("text", ""),
            language=data.get("language"),
            intent=data.get("intent"),
            metadata=data.get("metadata"),
        )
        result = voice_qualification_service.qualify(
            event,
            signals=data.get("signals"),
        )
        return jsonify({
            "success": True,
            "engine": "kemet_voice_callops_qualification",
            "version": voice_qualification_service.VERSION,
            "result": result,
        }), 200
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 422


@bos_command_bp.post("/commerce/follow-up-plan")
@login_required
def bos_commerce_follow_up_plan():
    """Build a read-only governed follow-up proposal for a qualified lead."""
    organization_id = getattr(current_user, "organization_id", None)
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    gate = monetization_guard.feature(organization_id, "bos")
    if not gate.get("allowed"):
        return jsonify({"success": False, "error": "feature_not_entitled", "reason": gate.get("reason"), "plan": gate.get("plan")}), 403
    data = request.get_json(silent=True) or {}
    from app.services.governed_followup_service import governed_followup_service
    try:
        result = governed_followup_service.build_plan(
            organization_id=int(organization_id),
            qualification=data.get("qualification") or {},
            channel=data.get("channel", "web"),
            customer_id=data.get("customer_id"),
            lead_id=data.get("lead_id"),
            message_goal=data.get("message_goal", "sales_follow_up"),
        )
        return jsonify(result), 200
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 422


@bos_command_bp.post("/commerce/revenue-evidence")
@login_required
def bos_commerce_revenue_evidence():
    """Verify recorded payment evidence against an existing commercial trace."""
    organization_id = getattr(current_user, "organization_id", None)
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    gate = monetization_guard.feature(organization_id, "bos")
    if not gate.get("allowed"):
        return jsonify({"success": False, "error": "feature_not_entitled", "reason": gate.get("reason"), "plan": gate.get("plan")}), 403
    data = request.get_json(silent=True) or {}
    from app.services.commerce_revenue_evidence_service import commerce_revenue_evidence_service
    try:
        result = commerce_revenue_evidence_service.verify(
            organization_id=int(organization_id),
            execution_key=str(data.get("execution_key") or ""),
            payment_id=data.get("payment_id"),
        )
        return jsonify(result), 200 if result.get("success") else 422
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 422


@bos_command_bp.post("/commerce/revenue-workflow-plan")
@login_required
def bos_commerce_revenue_workflow_plan():
    """Build a read-only end-to-end commerce revenue workflow plan."""
    organization_id = getattr(current_user, "organization_id", None)
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    gate = monetization_guard.feature(organization_id, "bos")
    if not gate.get("allowed"):
        return jsonify({"success": False, "error": "feature_not_entitled", "reason": gate.get("reason"), "plan": gate.get("plan")}), 403
    data = request.get_json(silent=True) or {}
    from app.services.commerce_revenue_workflow_service import commerce_revenue_workflow_service
    try:
        result = commerce_revenue_workflow_service.build_plan(
            organization_id=int(organization_id),
            product=data.get("product") or {},
            qualification=data.get("qualification") or {},
            lead_id=data.get("lead_id"),
            customer_id=data.get("customer_id"),
            channel=data.get("channel", "web"),
            audience=data.get("audience", ""),
            style=data.get("style", ""),
            language=data.get("language", "ar"),
        )
        return jsonify(result), 200
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 422


@bos_command_bp.post("/commerce/follow-up-submit")
@login_required
def bos_commerce_follow_up_submit():
    """Submit a governed follow-up proposal into the existing approval workflow."""
    organization_id = getattr(current_user, "organization_id", None)
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    gate = monetization_guard.feature(organization_id, "bos")
    if not gate.get("allowed"):
        return jsonify({"success": False, "error": "feature_not_entitled", "reason": gate.get("reason"), "plan": gate.get("plan")}), 403
    data = request.get_json(silent=True) or {}
    proposal = data.get("proposal") or data
    if proposal.get("status") != "approval_required" or proposal.get("action") != "sales_follow_up":
        return jsonify({"success": False, "error": "invalid_follow_up_proposal"}), 422
    try:
        proposal_organization_id = int(proposal.get("organization_id") or 0)
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "invalid_proposal_organization"}), 422
    if proposal_organization_id != int(organization_id):
        return jsonify({"success": False, "error": "proposal_not_in_organization"}), 403
    try:
        lead_id = int(proposal.get("lead_id"))
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "lead_id_required"}), 422
    from app.services.bos_runtime import bos_runtime
    result = bos_runtime.operate(
        f"follow up customer #{lead_id}",
        organization_id=int(organization_id),
        user_id=getattr(current_user, "id", None),
    )
    result["proposal_key"] = proposal.get("proposal_key")
    return jsonify(result), 200


@bos_command_bp.get("/execution-trace/<path:execution_key>")
@login_required
def bos_execution_trace(execution_key):
    organization_id = getattr(current_user, "organization_id", None)
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    gate = monetization_guard.feature(organization_id, "bos")
    if not gate.get("allowed"):
        return jsonify({"success": False, "error": "feature_not_entitled", "reason": gate.get("reason"), "plan": gate.get("plan")}), 403
    from app.services.commercial_outcome_trace import commercial_outcome_trace
    result = commercial_outcome_trace.get(
        organization_id=int(organization_id),
        execution_key=str(execution_key),
    )
    if result is None:
        return jsonify({"success": False, "error": "execution_trace_not_found"}), 404
    return jsonify({
        "success": True,
        "engine": "kemet_unified_execution_trace",
        "version": result.get("version", "1.0"),
        "trace": result,
        "lifecycle": ["ASK", "PLAN", "ROUTE", "SIMULATE", "APPROVE", "EXECUTE", "REVIEW", "MEASURE", "LEARN", "REPLAY"],
        "governance": {"read_only": True, "external_execution": False, "database_mutation": False},
    }), 200


@bos_command_bp.get("/throughput")
@login_required
def bos_throughput():
    organization_id = getattr(current_user, "organization_id", None)
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    gate = monetization_guard.feature(organization_id, "bos")
    if not gate.get("allowed"):
        return jsonify({"success": False, "error": "feature_not_entitled", "reason": gate.get("reason"), "plan": gate.get("plan")}), 403
    period = str(request.args.get("period") or "30d").strip()
    from app.services.business_throughput_service import business_throughput_service
    result = business_throughput_service.build(organization_id, period=period)
    return jsonify(result), 200 if result.get("success") else 400


@bos_command_bp.get("/outcome")
@login_required
def bos_outcome():
    data = request.args
    organization_id = getattr(current_user, "organization_id", None)
    period = str(data.get("period") or "30d").strip()
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    try:
        from app.services.business_outcome_service import business_outcome_service
        result = business_outcome_service.build(organization_id, period=period)
        return jsonify(result), 200
    except Exception:
        return jsonify({
            "success": False,
            "error": "outcome_unavailable",
            "message": "Kemet could not safely build the business outcome snapshot.",
        }), 500


@bos_command_bp.post("/operate")
@login_required
def bos_operate():
    data = request.get_json(silent=True) or {}
    command = str(data.get("command") or data.get("instruction") or "").strip()
    organization_id = getattr(current_user, "organization_id", None)
    if not command:
        return jsonify({"success": False, "error": "command_required"}), 400
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    gate = monetization_guard.feature(organization_id, "bos")
    if not gate.get("allowed"):
        return jsonify({"success": False, "error": "feature_not_entitled", "reason": gate.get("reason"), "plan": gate.get("plan")}), 403
    try:
        from app.services.bos_runtime import bos_runtime
        result = bos_runtime.operate(command, organization_id, getattr(current_user, "id", None))
        http_status = 200 if result.get("success") or result.get("status") == "waiting_approval" else 422
        return jsonify({"success": result.get("success", False), "status": result.get("status", "operated"), **result}), http_status
    except ValueError as exc:
        return jsonify({"success": False, "status": "unmapped", "error": "command_not_mapped", "message": str(exc)}), 422
    except Exception:
        return jsonify({"success": False, "status": "blocked", "error": "operation_not_safe", "message": "Kemet stopped before unsafe execution."}), 500


@bos_command_bp.post("/approvals/<int:approval_id>/approve")
@login_required
def bos_approve(approval_id):
    organization_id = getattr(current_user, "organization_id", None)
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    if getattr(current_user, "role", None) != "admin":
        return jsonify({"success": False, "error": "admin_approval_required"}), 403
    from app.services.bos_runtime import bos_runtime
    result = bos_runtime.approve(approval_id, organization_id, current_user.id)
    return jsonify(result), 200 if result.get("success") else 422


@bos_command_bp.post("/approvals/<int:approval_id>/reject")
@login_required
def bos_reject(approval_id):
    organization_id = getattr(current_user, "organization_id", None)
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    if getattr(current_user, "role", None) != "admin":
        return jsonify({"success": False, "error": "admin_approval_required"}), 403
    data = request.get_json(silent=True) or {}
    from app.services.bos_runtime import bos_runtime
    result = bos_runtime.reject(approval_id, organization_id, current_user.id, data.get("reason"))
    return jsonify(result), 200 if result.get("success") else 422


@bos_command_bp.route("/business-control-loop/feedback-summary", methods=["GET"])
@login_required
def bos_business_feedback_summary():
    try:
        organization_id = getattr(current_user, "organization_id", None)
        if not organization_id:
            return jsonify({"success": False, "error": "organization_required"}), 400
        decisions = BOSIntelligenceService.get_decisions(organization_id, limit=10)
        items = []
        for decision in decisions or []:
            feedback = decision.get("feedback") or {}
            if feedback:
                feedback["decision_id"] = decision.get("decision_id") or decision.get("id")
                feedback["capability_id"] = decision.get("capability_id") or decision.get("action")
                items.append(feedback)
        result = decision_feedback_loop.build(items)
        result["organization_id"] = organization_id
        result["review_queue"] = {"count": len(decisions or []), "approval_required": True, "auto_execute": False}
        return jsonify(result), 200
    except Exception:
        return jsonify({"success": False, "error": "business_feedback_summary_unavailable"}), 500


@bos_command_bp.route("/business-control-loop/feedback", methods=["POST"])
@login_required
def bos_business_control_loop_feedback():
    try:
        organization_id = getattr(current_user, "organization_id", None)
        payload = request.get_json(silent=True) or {}
        result = business_feedback.build(
            organization_id,
            decision_id=payload.get("decision_id"),
            capability_id=payload.get("capability_id"),
            signal=payload.get("signal", "neutral"),
            note=payload.get("note", ""),
            period=payload.get("period", "30d"),
        )
        return jsonify(result), 200 if result.get("success") else 400
    except Exception:
        return jsonify({"success": False, "error": "business_control_loop_feedback_unavailable"}), 500


@bos_command_bp.route("/business-control-loop", methods=["GET", "POST"])
@login_required
def bos_business_control_loop():
    try:
        organization_id = getattr(current_user, "organization_id", None)
        if not organization_id:
            return jsonify({"success": False, "error": "organization_required"}), 400
        if request.method == "GET":
            decisions = BOSIntelligenceService.get_decisions(organization_id, limit=10)
            period = str(request.args.get("period") or "30d").strip()
            raw_execution_keys = request.args.getlist("execution_key")
            execution_keys = [str(key).strip() for key in raw_execution_keys if str(key).strip()]
            revenue_intelligence = None
        else:
            payload = request.get_json(silent=True) or {}
            decisions = payload.get("decisions") or []
            period = payload.get("period", "30d")
            raw_execution_keys = payload.get("execution_keys") or []
            execution_keys = [str(key).strip() for key in raw_execution_keys if str(key).strip()]
            revenue_intelligence = payload.get("revenue_intelligence") if isinstance(payload.get("revenue_intelligence"), dict) else None
        result = BusinessControlLoopService.build(
            organization_id,
            decisions=decisions,
            period=period,
            execution_keys=execution_keys,
            revenue_intelligence=revenue_intelligence,
        )
        return jsonify(result), 200 if result.get("success") else 400
    except Exception:
        return jsonify({"success": False, "error": "business_control_loop_unavailable"}), 500





@bos_command_bp.post("/commerce/fulfillment-plan")
@login_required
def bos_commerce_fulfillment_plan():
    """Build a read-only fulfillment proposal from an existing commerce order reference."""
    organization_id = getattr(current_user, "organization_id", None)
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    gate = monetization_guard.feature(organization_id, "bos")
    if not gate.get("allowed"):
        return jsonify({"success": False, "error": "feature_not_entitled", "reason": gate.get("reason"), "plan": gate.get("plan")}), 403
    data = request.get_json(silent=True) or {}
    from app.services.commerce_fulfillment_service import commerce_fulfillment_service
    try:
        result = commerce_fulfillment_service.build_plan(
            organization_id=int(organization_id),
            business_reference=data.get("business_reference", ""),
            customer=data.get("customer") or {},
            shipping_address=data.get("shipping_address") or {},
            cod=data.get("cod", 0),
            items=data.get("items") or [],
            package_type=data.get("package_type", "Small"),
            package_description=data.get("package_description", ""),
            webhook_url=data.get("webhook_url"),
        )
        return jsonify(result), 200
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 422

@bos_command_bp.post("/commerce/salla/webhook/<int:organization_id>")
def bos_salla_webhook(organization_id):
    from app.services.salla_connector_service import salla_connector_service
    from app.core.automation_queue import automation_queue

    if not salla_connector_service.verify_webhook(organization_id=int(organization_id), headers=request.headers):
        return jsonify({"success": False, "error": "webhook_authentication_failed"}), 403
    payload = request.get_json(silent=True) or {}
    try:
        event = salla_connector_service.normalize_webhook(
            organization_id=int(organization_id), payload=payload
        )
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    try:
        result = salla_connector_service.materialize_webhook_workflow(
            organization_id=int(organization_id), event=event, requested_by=None
        )
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 422
    status_code = 202 if result.get("success") else 422
    return jsonify(result), status_code

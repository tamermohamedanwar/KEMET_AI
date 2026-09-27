from decimal import Decimal
import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models.chat import ChatMessage
from app.models.conversation import Conversation
from app.models.subscription import Subscription
from app import csrf
from app.core.rate_limit import limiter

main = Blueprint("main", __name__)


@main.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(url_for("command_center.index"))

    return redirect(url_for("auth.login"))


@main.route("/document-automation")
@login_required
def document_automation_page():
    return render_template("document_automation.html", user=current_user)


@main.route("/history")
@login_required
def history():

    messages = (
        ChatMessage.query
        .filter(
            ChatMessage.user_id == current_user.id
        )
        .order_by(
            ChatMessage.id.desc()
        )
        .all()
    )

    return render_template(
        "history.html",
        messages=messages
    )


@main.route("/chat")
@login_required
def chat_page():
    conversation_id = request.args.get("conversation_id")

    conversations = (
        Conversation.query
        .filter(
            Conversation.user_id == current_user.id,
            Conversation.organization_id == current_user.organization_id,
        )
        .order_by(
            Conversation.updated_at.desc()
        )
        .all()
    )

    messages = []

    if conversation_id:
        conversation = (
            Conversation.query
            .filter(
                Conversation.id == conversation_id,
                Conversation.user_id == current_user.id,
                Conversation.organization_id == current_user.organization_id,
            )
            .first_or_404()
        )

        messages = (
            ChatMessage.query
            .filter(
                ChatMessage.conversation_id == conversation.id,
                ChatMessage.user_id == current_user.id,
            )
            .order_by(
                ChatMessage.id.asc()
            )
            .all()
        )

    return render_template(
        "chat.html",
        user=current_user,
        conversation_id=conversation_id,
        conversations=conversations,
        messages=messages
    )


@main.route("/profile")
@login_required
def profile():
    return render_template("profile.html", user=current_user)


from flask import render_template
from app.config.plans import PLAN_DETAILS, PAID_PLANS, is_paid_plan

@main.route("/landing")
def landing():
    return render_template("landing.html")


@main.route("/pricing")
def pricing():
    from app.services.payment_service import PLAN_PRICES
    from app.services.exchange_rate_service import get_usd_to_egp

    fx = get_usd_to_egp()

    pricing_data = {}

    for plan, usd_price in PLAN_PRICES.items():
        if usd_price is None:
            pricing_data[plan] = {
                "usd": None,
                "egp": None,
            }
            continue

        egp_price = (usd_price * fx["rate"]).quantize(Decimal("0.01"))

        pricing_data[plan] = {
            "usd": usd_price,
            "egp": egp_price,
        }

    return render_template(
        "pricing.html",
        pricing=pricing_data,
        exchange_rate=fx["rate"],
        exchange_rate_source=fx["source"],
        exchange_rate_date=fx["provider_date"],
        exchange_rate_fallback=fx["fallback"],
    )


@main.route("/pricing/select/<plan>")
@login_required
def select_plan(plan):
    from flask import flash
    from app import db
    from app.models.subscription import Subscription
    from app.services.payment_service import create_checkout

    plan = (plan or "").lower()

    allowed_plans = {"free", "starter", "business", "enterprise"}

    if plan not in allowed_plans:
        flash("Invalid plan")
        return redirect(url_for("main.pricing"))

    subscription = Subscription.query.filter_by(
        organization_id=current_user.organization_id
    ).first()

    if not subscription:
        flash("Subscription not found")
        return redirect(url_for("main.pricing"))

    if plan == "free":
        subscription.plan = "free"
        subscription.status = "active"
        db.session.commit()
        flash("Free plan activated")
        return redirect(url_for("billing.pricing"))

    try:
        result = create_checkout(
            current_user.organization_id,
            plan
        )
    except Exception as exc:
        flash(f"Payment setup failed: {exc}")
        return redirect(url_for("main.pricing"))

    if result["status"] == "contact_sales":
        return redirect(url_for("main.demo"))

    return redirect(result["checkout_url"])

@main.route("/demo", methods=["GET", "POST"])
@limiter.limit("5 per hour", methods=["POST"])
def demo():
    from datetime import datetime, timedelta
    import re
    from app import db
    from app.models.demo_lead import DemoLead
    from app.models.lead_activity import LeadActivity
    from app.services.lead_scoring_service import score_lead

    if request.method == "POST":
        company = " ".join((request.form.get("company") or "").split())
        email = (request.form.get("email") or "").strip().lower()
        phone = (request.form.get("phone") or "").strip()
        message = (request.form.get("message") or "").strip()
        website = (request.form.get("website") or "").strip()

        if website:
            flash("تم استلام الطلب.", "success")
            return redirect(url_for("main.demo"))

        errors = []
        if not company or len(company) < 2 or len(company) > 150:
            errors.append("اسم الشركة مطلوب.")
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) or len(email) > 150:
            errors.append("يرجى إدخال بريد إلكتروني صحيح.")
        if len(phone) > 50:
            errors.append("رقم الهاتف غير صالح.")
        if len(message) > 4000:
            errors.append("الرسالة طويلة جدًا.")

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("demo.html", form=request.form), 400

        organization_id = (
            current_user.organization_id
            if current_user.is_authenticated
            else None
        )

        duplicate_query = DemoLead.query.filter(
            db.func.lower(DemoLead.email) == email,
            DemoLead.organization_id == organization_id,
        )
        duplicate = duplicate_query.order_by(DemoLead.created_at.desc()).first()
        if duplicate and duplicate.created_at:
            created_at = duplicate.created_at
            if created_at >= datetime.utcnow() - timedelta(hours=24):
                flash("تم استلام طلبك بالفعل وسنتواصل معك قريبًا.", "info")
                return redirect(url_for("main.demo"))

        lead = DemoLead(
            company_name=company,
            email=email,
            phone=phone or None,
            message=message or None,
            organization_id=organization_id,
            tenant_id=organization_id,
            source="website",
            provenance={"source": "website", "method": "demo_form", "trusted": True},
            status="new",
        )

        db.session.add(lead)
        db.session.flush()
        score_lead(lead, persist=True) if organization_id is not None else setattr(lead, "lead_score", 0)

        db.session.add(LeadActivity(
            organization_id=organization_id,
            lead_id=lead.id,
            user_id=current_user.id if current_user.is_authenticated else None,
            activity_type="follow_up",
            subject="New demo request",
            content="Website demo request received; review and contact the prospect.",
            due_at=datetime.utcnow() + timedelta(days=1),
        ))
        lead.next_follow_up_at = datetime.utcnow() + timedelta(days=1)

        db.session.commit()
        flash("تم إرسال طلبك بنجاح. سنراجع احتياجك ونتواصل معك قريبًا.", "success")
        return redirect(url_for("main.demo"))

    return render_template("demo.html", form={})

@main.route("/payment/checkout/<int:payment_id>")
@login_required
def payment_checkout(payment_id):
    from app.models.payment import Payment

    payment = Payment.query.get_or_404(payment_id)

    if payment.organization_id != current_user.organization_id:
        flash("Unauthorized payment")
        return redirect(url_for("main.pricing"))

    if payment.status == "paid":
        return redirect(url_for("main.pricing"))

    integration_id = os.getenv("PAYMOB_INTEGRATION_ID", "").strip()

    checkout_url = None
    from app.core.payment_secret import get_payment_token
    payment_token = get_payment_token(payment) if (getattr(payment, "client_secret_encrypted", None) or getattr(payment, "client_secret", None)) else ""
    if payment_token and integration_id:
        checkout_url = (
            f"https://accept.paymob.com/api/acceptance/iframes/"
            f"{integration_id}?payment_token={payment_token}"
        )

    return render_template(
        "payment_checkout.html",
        payment=payment,
        checkout_url=checkout_url
    )


@main.route("/payment/start/<plan>")
@login_required
def payment_start(plan):
    from app.services.payment_service import create_checkout

    try:
        result = create_checkout(
            current_user.organization_id,
            plan
        )
    except Exception as exc:
        flash(f"Payment setup failed: {exc}")
        return redirect(url_for("main.pricing"))

    if result.get("status") == "contact_sales":
        return redirect(url_for("main.demo"))

    return redirect(
        url_for(
            "main.payment_checkout",
            payment_id=result["payment_id"]
        )
    )


@main.route("/payment/mock/<int:payment_id>")
@login_required
def mock_payment(payment_id):
    # Mock payments are strictly for local development/testing.
    # Never allow them in production.
    if os.getenv("PAYMENT_MODE", "paymob").strip().lower() != "mock":
        return jsonify({"error": "mock_payment_disabled"}), 403

    from app import db
    from app.models.payment import Payment
    from app.models.subscription import Subscription

    payment = Payment.query.get_or_404(payment_id)

    if payment.organization_id != current_user.organization_id:
        return jsonify({"error": "unauthorized"}), 403

    # Mock payments must still have a transaction identifier.
    # This keeps payment-state invariants identical to provider payments.
    if not payment.provider_transaction_id:
        payment.provider_transaction_id = f"MOCK_TX_{payment.id}"

    payment.status = "paid"

    subscription = Subscription.query.filter_by(
        organization_id=payment.organization_id
    ).first()

    if not subscription:
        subscription = Subscription(
            organization_id=payment.organization_id,
            plan=payment.plan,
            status="active",
        )
        db.session.add(subscription)
    else:
        subscription.plan = payment.plan
        subscription.status = "active"

    db.session.commit()

    flash(f"Payment {payment.id} completed successfully.")
    return redirect(url_for("billing.pricing"))


@main.route("/payment/paymob/callback", methods=["POST"])
@csrf.exempt
def paymob_callback():
    import os

    from flask import jsonify, request
    from app import db
    from app.models.payment import Payment
    from app.models.subscription import Subscription
    from app.services.paymob_webhook import amount_cents, verify_transaction_callback

    data = request.get_json(silent=True) or {}
    obj = data.get("obj") or {}
    order = obj.get("order") or {}
    received_hmac = (request.args.get("hmac") or "").strip().lower()
    secret = os.getenv("PAYMOB_HMAC_SECRET", "").strip()

    if not secret or not received_hmac:
        return jsonify({"status": "invalid"}), 403

    if not verify_transaction_callback(obj, received_hmac, secret):
        return jsonify({"status": "invalid_hmac"}), 403

    configured_integration_id = os.getenv("PAYMOB_INTEGRATION_ID", "").strip()
    callback_integration_id = str(obj.get("integration_id") or "").strip()
    if not configured_integration_id:
        return jsonify({"status": "integration_not_configured"}), 503
    if not callback_integration_id or callback_integration_id != configured_integration_id:
        return jsonify({"status": "integration_mismatch"}), 409

    order_id = order.get("id")
    transaction_id = obj.get("id")

    if not order_id or not transaction_id:
        return jsonify({"status": "missing_transaction_data"}), 400

    payment = Payment.query.filter_by(
        checkout_id=str(order_id)
    ).first()

    if not payment:
        payment = Payment.query.filter_by(
            provider_order_id=str(order_id)
        ).first()

    if not payment:
        return jsonify({"status": "payment_not_found"}), 404

    if str(payment.provider or "").lower() != "paymob":
        return jsonify({"status": "payment_provider_mismatch"}), 409

    existing_order_id = str(payment.provider_order_id or "").strip()
    existing_transaction_id = str(payment.provider_transaction_id or "").strip()
    callback_order_id = str(order_id).strip()
    callback_transaction_id = str(transaction_id).strip()

    if existing_order_id and existing_order_id != callback_order_id:
        return jsonify({"status": "provider_order_mismatch"}), 409

    if existing_transaction_id and existing_transaction_id != callback_transaction_id:
        return jsonify({"status": "provider_transaction_mismatch"}), 409

    conflicting_payment = Payment.query.filter(
        Payment.provider_transaction_id == callback_transaction_id,
        Payment.id != payment.id,
    ).first()
    if conflicting_payment is not None:
        return jsonify({"status": "provider_transaction_conflict"}), 409

    if payment.status == "paid":
        return jsonify({"status": "already_paid"}), 200

    callback_amount_cents = amount_cents(obj)
    expected_amount_cents = int(round(float(payment.amount) * 100))

    currency = str(obj.get("currency") or "").upper()
    expected_currency = str(payment.currency or "").upper()

    payment.provider_order_id = str(order_id)
    payment.provider_transaction_id = str(transaction_id)

    if (
        obj.get("success") is True
        and obj.get("pending") is False
        and obj.get("is_refunded") is False
        and obj.get("is_voided") is False
        and callback_amount_cents == expected_amount_cents
        and currency == expected_currency
        and bool(str(transaction_id).strip())
    ):
        payment.status = "paid"

        subscription = Subscription.query.filter_by(
            organization_id=payment.organization_id
        ).first()

        if not subscription:
            subscription = Subscription(
                organization_id=payment.organization_id,
                plan=payment.plan,
                status="active",
            )
            db.session.add(subscription)
        else:
            subscription.plan = payment.plan
            subscription.status = "active"

        db.session.commit()

        return jsonify({
            "status": "paid",
            "payment_id": payment.id,
            "transaction_id": str(transaction_id),
        }), 200

    payment.status = "failed"
    db.session.commit()

    return jsonify({
        "status": "failed",
        "payment_id": payment.id,
        "transaction_id": str(transaction_id),
    }), 200

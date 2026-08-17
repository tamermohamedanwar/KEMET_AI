from decimal import Decimal
import os
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models.chat import ChatMessage
from app.models.conversation import Conversation
from app.models.subscription import Subscription
from app import csrf

main = Blueprint("main", __name__)


@main.route("/")
def home():
    if current_user.is_authenticated:
        return render_template(
            "dashboard.html",
            user=current_user
        )

    return render_template("landing.html")


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
        return redirect(url_for("billing.billing"))

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
def demo():
    from flask import request, flash
    from app import db
    from app.models.demo_lead import DemoLead

    if request.method == "POST":
        company = request.form.get("company")
        email = request.form.get("email")
        message = request.form.get("message")

        lead = DemoLead(
            company=company,
            email=email,
            message=message
        )

        db.session.add(lead)
        db.session.commit()

        flash("تم إرسال طلب التجربة بنجاح، سنتواصل معك قريبًا.")

        return redirect(url_for("main.demo"))

    return render_template("demo.html")

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
    if getattr(payment, "client_secret", None) and integration_id:
        checkout_url = (
            f"https://accept.paymob.com/api/acceptance/iframes/"
            f"{integration_id}?payment_token={payment.client_secret}"
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
    return redirect(url_for("billing.billing"))


@main.route("/payment/paymob/callback", methods=["POST"])
@csrf.exempt
def paymob_callback():
    import hashlib
    import hmac
    import os

    from flask import jsonify, request
    from app import db
    from app.models.payment import Payment
    from app.models.subscription import Subscription

    data = request.get_json(silent=True) or {}
    obj = data.get("obj") or {}
    received_hmac = (request.args.get("hmac") or "").strip().lower()
    secret = os.getenv("PAYMOB_HMAC_SECRET", "").strip()

    if not secret or not received_hmac:
        return jsonify({"status": "invalid"}), 403

    def hmac_value(value):
        if value is None:
            return ""
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, dict):
            if "id" in value:
                return str(value["id"])
            return ""
        return str(value)

    source_data = obj.get("source_data") or {}
    order = obj.get("order") or {}

    values = [
        obj.get("amount_cents"),
        obj.get("created_at"),
        obj.get("currency"),
        obj.get("error_occured"),
        obj.get("has_parent_transaction"),
        obj.get("id"),
        obj.get("integration_id"),
        obj.get("is_3d_secure"),
        obj.get("is_auth"),
        obj.get("is_capture"),
        obj.get("is_refunded"),
        obj.get("is_standalone_payment"),
        obj.get("is_voided"),
        order.get("id"),
        obj.get("owner"),
        obj.get("pending"),
        source_data.get("pan"),
        source_data.get("sub_type"),
        source_data.get("type"),
        obj.get("success"),
    ]

    message = "".join(hmac_value(value) for value in values)

    calculated_hmac = hmac.new(
        secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha512,
    ).hexdigest().lower()

    if not hmac.compare_digest(calculated_hmac, received_hmac):
        return jsonify({"status": "invalid_hmac"}), 403

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

    if payment.status == "paid":
        return jsonify({"status": "already_paid"}), 200

    amount_cents = int(obj.get("amount_cents") or 0)
    expected_amount_cents = int(payment.amount * 100)

    currency = str(obj.get("currency") or "").upper()
    expected_currency = str(payment.currency or "").upper()

    payment.provider_order_id = str(order_id)
    payment.provider_transaction_id = str(transaction_id)

    if (
        obj.get("success") is True
        and obj.get("pending") is False
        and obj.get("is_refunded") is False
        and obj.get("is_voided") is False
        and amount_cents == expected_amount_cents
        and currency == expected_currency
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

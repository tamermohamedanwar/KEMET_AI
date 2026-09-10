from flask import request, Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user

from app.services.billing_service import BillingService
from app.services.billing_context_service import BillingContextService
from app.services.subscription_service import SubscriptionService


billing_bp = Blueprint(
    "billing",
    __name__,
    url_prefix="/billing",
)


@billing_bp.route("/pricing")
@login_required
def pricing():
    plans = BillingService.get_available_plans()

    return render_template(
        "billing/pricing.html",
        plans=plans,
    )





@billing_bp.route("/payment/prepare/<plan>")
@login_required
def prepare_payment(plan):
    plans = BillingService.get_available_plans()

    selected_plan = None

    for item in plans:
        if isinstance(item, dict):
            if (
                item.get("slug") == plan
                or str(item.get("id")) == str(plan)
            ):
                selected_plan = item
                break
        else:
            item_slug = getattr(item, "slug", None)
            item_id = getattr(item, "id", None)

            if (
                item_slug == plan
                or str(item_id) == str(plan)
            ):
                selected_plan = item
                break

    if selected_plan is None:
        flash("Selected plan is not available.", "error")
        return redirect(url_for("billing.pricing"))

    organization_id = getattr(
        current_user,
        "organization_id",
        None,
    )

    billing_context = BillingContextService.build_context(
        selected_plan,
        organization_id=organization_id,
        payment_provider="paymob",
    )

    return render_template(
        "billing/payment_prepare.html",
        plan=selected_plan,
        organization_id=organization_id,
        payment_provider=billing_context["payment_provider"],
        payment_executed=billing_context["payment_executed"],
        payment_ready=billing_context["payment_ready"],
        billing_context=billing_context,
        payment_intent=billing_context["payment_intent"],
    )


@billing_bp.route("/checkout/<plan>", methods=["GET", "POST"])
@login_required
def checkout(plan):
    plans = BillingService.get_available_plans()

    selected_plan = None

    for item in plans:
        if isinstance(item, dict):
            item_slug = item.get("slug")
            item_id = item.get("id")

            if (
                item_slug == plan
                or str(item_id) == str(plan)
            ):
                selected_plan = item
                break
        else:
            item_slug = getattr(item, "slug", None)
            item_id = getattr(item, "id", None)

            if (
                item_slug == plan
                or str(item_id) == str(plan)
            ):
                selected_plan = item
                break

    if selected_plan is None:
        flash("Selected plan is not available.", "error")
        return redirect(url_for("billing.pricing"))

    organization_id = getattr(
        current_user,
        "organization_id",
        None,
    )

    if not organization_id:
        flash("Organization is required for checkout.", "error")
        return redirect(url_for("billing.pricing"))

    plan_slug = (
        selected_plan.get("slug")
        if isinstance(selected_plan, dict)
        else getattr(selected_plan, "slug", None)
    )

    if not plan_slug:
        flash("Invalid billing plan.", "error")
        return redirect(url_for("billing.pricing"))

    # POST performs the actual payment initialization.
    if request.method == "POST":
        from app.services.payment_service import create_checkout

        try:
            result = create_checkout(
                organization_id,
                plan_slug,
            )
        except Exception as exc:
            flash(f"Payment setup failed: {exc}", "error")
            return redirect(
                url_for(
                    "billing.subscribe",
                    plan=plan_slug,
                )
            )

        if result.get("status") == "contact_sales":
            return redirect(url_for("main.demo"))

        if result.get("status") == "mock":
            return redirect(result["checkout_url"])

        if result.get("status") == "ready":
            return redirect(
                url_for(
                    "main.payment_checkout",
                    payment_id=result["payment_id"],
                )
            )

        flash("Payment could not be initialized.", "error")
        return redirect(
            url_for(
                "billing.subscribe",
                plan=plan_slug,
            )
        )

    billing_context = BillingContextService.build_context(
        selected_plan,
        organization_id=organization_id,
        payment_provider="paymob",
    )

    return render_template(
        "billing/checkout.html",
        plan=selected_plan,
        organization_id=organization_id,
        payment_provider=billing_context["payment_provider"],
        payment_ready=billing_context["payment_ready"],
        payment_executed=billing_context["payment_executed"],
        billing_context=billing_context,
        payment_intent=billing_context["payment_intent"],
        plan_slug=plan_slug,
    )


@billing_bp.route("/subscribe/<plan>")
@login_required
def subscribe(plan):
    plans = BillingService.get_available_plans()

    selected_plan = None

    for item in plans:
        if isinstance(item, dict):
            if item.get("slug") == plan or item.get("id") == plan:
                selected_plan = item
                break
        else:
            item_slug = getattr(item, "slug", None)
            item_id = getattr(item, "id", None)

            if item_slug == plan or str(item_id) == str(plan):
                selected_plan = item
                break

    if selected_plan is None:
        flash("Selected plan is not available.", "error")
        return redirect(url_for("billing.pricing"))

    organization_id = getattr(
        current_user,
        "organization_id",
        None,
    )

    billing_context = BillingContextService.build_context(
        selected_plan,
        organization_id=organization_id,
        payment_provider="paymob",
    )

    return render_template(
        "billing/checkout.html",
        plan=selected_plan,
        organization_id=organization_id,
        payment_provider=billing_context["payment_provider"],
        payment_ready=billing_context["payment_ready"],
        payment_executed=billing_context["payment_executed"],
        billing_context=billing_context,
        payment_intent=billing_context["payment_intent"],
    )


@billing_bp.route("/subscription")
@login_required
def subscription():
    organization_id = getattr(
        current_user,
        "organization_id",
        None,
    )

    subscription = None
    current_plan = "free"
    is_active = False

    if organization_id:
        subscription = SubscriptionService.get_subscription(
            organization_id
        )
        current_plan = SubscriptionService.get_current_plan(
            organization_id
        )
        is_active = SubscriptionService.is_active(
            organization_id
        )

    return render_template(
        "billing/subscription.html",
        subscription=subscription,
        current_plan=current_plan,
        is_active=is_active,
    )

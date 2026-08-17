
from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required, current_user

from app import db
from app.models.ticket import Ticket
from app.models.ticket_reply import TicketReply
from app.services.ai_service import ask_ai
from app.services.ai_usage_service import check_limit, record_usage
from app.admin.decorators import admin_required


admin_support = Blueprint("admin_support", __name__)


@admin_support.route("/admin/support")
@admin_required
def support_dashboard():

    q = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    priority = request.args.get("priority", "").strip()

    tickets_query = Ticket.query.filter(
        Ticket.organization_id == current_user.organization_id
    )

    if q:
        tickets_query = (
            tickets_query
            .outerjoin(TicketReply)
            .filter(
                db.or_(
                    Ticket.title.ilike(f"%{q}%"),
                    TicketReply.message.ilike(f"%{q}%")
                )
            )
            .distinct()
        )

    if status:
        tickets_query = tickets_query.filter(
            Ticket.status == status
        )

    if priority:
        tickets_query = tickets_query.filter(
            Ticket.priority == priority
        )

    tickets = tickets_query.order_by(
        Ticket.id.desc()
    ).all()

    return render_template(
        "admin_support.html",
        tickets=tickets
    )



@admin_support.route("/admin/support/ticket/<int:ticket_id>", methods=["GET","POST"])
@admin_required
def admin_ticket_detail(ticket_id):

    ticket = Ticket.query.filter_by(
        id=ticket_id,
        organization_id=current_user.organization_id
    ).first_or_404()


    if request.method == "POST":

        ticket.priority = request.form.get("priority", ticket.priority)

        assigned = request.form.get("assigned_to_id")
        if assigned:
            from app.models.user import User

            assigned_user = (
                User.query
                .filter(
                    User.id == int(assigned),
                    User.organization_id == current_user.organization_id,
                )
                .first()
            )

            if not assigned_user:
                return {"error": "invalid_assignee"}, 403

            ticket.assigned_to_id = assigned_user.id

        ticket.status = request.form.get("status", ticket.status)

        message = request.form.get("message")
        is_ai = request.form.get("is_ai") == "1"

        if request.form.get("send_ai_reply") == "1":
            is_ai = True

        if message:

            reply = TicketReply(
                ticket_id=ticket.id,
                user_id=current_user.id,
                message=message,
                is_staff=True,
                is_ai=is_ai
            )

            db.session.add(reply)

            ticket.status = "Pending"

            db.session.commit()


        return redirect(
            url_for(
                "admin_support.admin_ticket_detail",
                ticket_id=ticket.id
            )
        )


    return render_template(
        "ticket_detail.html",
        ticket=ticket
    )



@admin_support.route("/admin/support/ticket/<int:ticket_id>/ai-suggest")
@admin_required
def ai_suggest(ticket_id):

    ticket = Ticket.query.filter_by(
        id=ticket_id,
        organization_id=current_user.organization_id
    ).first_or_404()

    context = ""

    for reply in ticket.replies:
        role = "Customer" if not reply.is_staff else "Support"
        context += f"{role}: {reply.message}\n"


    prompt = f"""
أنت وكيل دعم عملاء خبير يعمل داخل منصة Kemet AI.

اكتب ردًا جاهزًا للإرسال للعميل.

قواعد الرد:
- افهم مشكلة العميل قبل كتابة الرد.
- قدم حلًا أو خطوات عملية مرتبطة بالمشكلة.
- لا تستخدم مقدمات عامة متكررة.
- إذا كانت المعلومات ناقصة، اسأل سؤالًا واحدًا محددًا.
- اجعل الرد مختصرًا واحترافيًا.
- لا تذكر أنك ذكاء اصطناعي.
- اكتب نص الرد فقط.

عنوان المشكلة:
{ticket.title}

حالة التذكرة:
{ticket.status}

الأولوية:
{ticket.priority}

تفاصيل المحادثة:
{context}
"""


    usage = check_limit(current_user.organization_id)

    if not usage["allowed"]:
        return {
            "suggestion": "تم الوصول إلى الحد الشهري لاستخدام الذكاء الاصطناعي في خطتك الحالية.",
            "usage_limit": True,
            "plan": usage["plan"],
            "remaining": usage["remaining"]
        }, 429

    suggestion = ask_ai(
        prompt,
        context
    )

    record_usage(
        current_user.organization_id
    )

    return {
        "suggestion": suggestion,
        "usage_limit": False,
        "plan": usage["plan"],
        "remaining": max(usage["remaining"] - 1, 0)
    }


@admin_support.route("/admin/support/analytics")
@admin_required
def analytics():

    from app.models.ticket import Ticket
    from app.models.ticket_reply import TicketReply

    total = Ticket.query.filter_by(organization_id=current_user.organization_id).count()
    open_count = Ticket.query.filter_by(organization_id=current_user.organization_id, status="open").count()
    pending_count = Ticket.query.filter_by(organization_id=current_user.organization_id, status="Pending").count()
    closed_count = Ticket.query.filter_by(organization_id=current_user.organization_id, status="closed").count()

    ai_replies = (
        TicketReply.query
        .join(Ticket, TicketReply.ticket_id == Ticket.id)
        .filter(
            Ticket.organization_id == current_user.organization_id,
            TicketReply.is_ai.is_(True),
        )
        .count()
    )

    staff_replies = (
        TicketReply.query
        .join(Ticket, TicketReply.ticket_id == Ticket.id)
        .filter(
            Ticket.organization_id == current_user.organization_id,
            TicketReply.is_staff.is_(True),
        )
        .count()
    )

    total_replies = ai_replies + staff_replies

    ai_percentage = 0
    if total_replies:
        ai_percentage = round((ai_replies / total_replies) * 100)

    ai_tickets = Ticket.query.join(
        TicketReply
    ).filter(
        Ticket.organization_id == current_user.organization_id,
        TicketReply.is_ai == True
    ).distinct().count()

    ai_resolution_rate = 0
    if total:
        ai_resolution_rate = round((ai_tickets / total) * 100)

    response_times = []

    for ticket in Ticket.query.filter_by(
        organization_id=current_user.organization_id
    ).all():
        if ticket.replies:
            first_reply = min(
                ticket.replies,
                key=lambda reply: reply.created_at
            )

            seconds = (
                first_reply.created_at - ticket.created_at
            ).total_seconds()

            if seconds >= 0:
                response_times.append(seconds)

    avg_response_time = 0
    if response_times:
        avg_response_time = round(
            sum(response_times) / len(response_times) / 60
        )

    return render_template(
        "admin_analytics.html",
        total=total,
        open_count=open_count,
        pending_count=pending_count,
        closed_count=closed_count,
        ai_replies=ai_replies,
        staff_replies=staff_replies,
        total_replies=total_replies,
        ai_percentage=ai_percentage,
        ai_resolution_rate=ai_resolution_rate,
        avg_response_time=avg_response_time
    )


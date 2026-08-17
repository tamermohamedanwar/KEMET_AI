from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required, current_user

from app import db
from app.models.ticket import Ticket
from app.models.ticket_reply import TicketReply
from app.automation.engine import engine


tickets = Blueprint("tickets", __name__)


def _extract_ai_replies(automation_result):
    replies = []

    if not isinstance(automation_result, list):
        return replies

    for workflow_result in automation_result:
        if not isinstance(workflow_result, dict):
            continue

        for action_result in workflow_result.get("actions", []):
            if not isinstance(action_result, dict):
                continue

            result = action_result.get("result", {})

            if not isinstance(result, dict):
                continue

            action_type = action_result.get("action_type")

            if action_type != "generate_ai_reply":
                continue

            candidate = result.get("reply")

            if candidate:
                replies.append(str(candidate))

    return replies


def _run_ticket_message_automation(ticket, message):
    try:
        automation_result = engine.execute(
            event="ticket_message_created",
            data={
                "user_id": current_user.id,
                "organization_id": current_user.organization_id,
                "ticket_id": ticket.id,
                "message": message,
                "title": ticket.title,
            },
            organization_id=current_user.organization_id,
        )

        print(
            "CUSTOMER MESSAGE AUTOMATION:",
            automation_result,
        )

        return automation_result

    except Exception as exc:
        db.session.rollback()

        print(
            "CUSTOMER MESSAGE AUTOMATION ERROR:",
            exc,
        )

        return {
            "status": "failed",
            "error": str(exc),
        }

@tickets.route("/tickets")
@login_required
def list_tickets():
    user_tickets = (
        Ticket.query
        .filter(
            Ticket.user_id == current_user.id,
            Ticket.organization_id == current_user.organization_id,
        )
        .order_by(Ticket.id.desc())
        .all()
    )

    return render_template(
        "tickets.html",
        tickets=user_tickets,
    )


@tickets.route("/tickets/create", methods=["GET", "POST"])
@login_required
def create_ticket():
    if request.method == "POST":
        title = request.form.get(
            "title",
            "طلب دعم جديد",
        ).strip()

        ticket = Ticket(
            user_id=current_user.id,
            organization_id=current_user.organization_id,
            title=title,
            status="open",
        )

        db.session.add(ticket)
        db.session.commit()

        print(
            "TICKET CREATED:",
            ticket.id,
            ticket.title,
        )

        # Trigger automation specifically for ticket creation.
        try:
            automation_result = engine.execute(
                event="ticket_created",
                data={
                    "user_id": current_user.id,
                    "organization_id": current_user.organization_id,
                    "ticket_id": ticket.id,
                    "title": ticket.title,
                    "message": ticket.title,
                },
                organization_id=current_user.organization_id,
            )

            print(
                "TICKET CREATED AUTOMATION:",
                automation_result,
            )

        except Exception as exc:
            db.session.rollback()

            print(
                "TICKET AUTOMATION ERROR:",
                exc,
            )

        return redirect(
            url_for("tickets.list_tickets")
        )

    return render_template("create_ticket.html")


@tickets.route(
    "/tickets/<int:ticket_id>",
    methods=["GET", "POST"],
)
@login_required
def ticket_detail(ticket_id):
    ticket = (
        Ticket.query
        .filter(
            Ticket.id == ticket_id,
            Ticket.user_id == current_user.id,
            Ticket.organization_id == current_user.organization_id,
        )
        .first_or_404()
    )

    if request.method == "POST":
        message = request.form.get(
            "message",
            "",
        ).strip()

        if message:
            reply = TicketReply(
                ticket_id=ticket.id,
                user_id=current_user.id,
                message=message,
                is_staff=False,
                is_ai=False,
            )

            db.session.add(reply)
            db.session.commit()

            print(
                "CUSTOMER MESSAGE SAVED:",
                ticket.id,
                reply.id,
            )

            # Run the production automation flow
            # only after a real customer message exists.
            _run_ticket_message_automation(
                ticket,
                message,
            )

        return redirect(
            url_for(
                "tickets.ticket_detail",
                ticket_id=ticket.id,
            )
        )

    return render_template(
        "ticket_detail.html",
        ticket=ticket,
    )

from datetime import datetime

from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user

from app import db
from app.admin.decorators import admin_required
from app.models.demo_lead import DemoLead
from app.services.lead_scoring_service import score_lead


admin_leads = Blueprint(
    "admin_leads",
    __name__,
)


PIPELINE_STATUSES = {
    "new": "New",
    "contacted": "Contacted",
    "qualified": "Qualified",
    "proposal": "Proposal",
    "won": "Won",
    "lost": "Lost",
}


def organization_leads_query():
    organization_id = getattr(current_user, "organization_id", None)

    query = DemoLead.query

    if organization_id is not None:
        query = query.filter(
            DemoLead.organization_id == organization_id
        )

    return query


@admin_leads.route("/admin/leads")
@admin_required
def leads():
    status = request.args.get(
        "status",
        "",
    ).strip().lower()

    temperature = request.args.get(
        "temperature",
        "",
    ).strip().lower()

    search = request.args.get(
        "q",
        "",
    ).strip()

    query = organization_leads_query()

    if status in PIPELINE_STATUSES:
        query = query.filter(
            DemoLead.status == status
        )

    if search:
        search_pattern = f"%{search}%"

        query = query.filter(
            db.or_(
                DemoLead.company_name.ilike(search_pattern),
                DemoLead.email.ilike(search_pattern),
                DemoLead.phone.ilike(search_pattern),
            )
        )

    leads = (
        query
        .order_by(
            DemoLead.lead_score.desc(),
            DemoLead.created_at.desc(),
        )
        .all()
    )

    filtered_leads = []

    for lead in leads:
        result = score_lead(lead)

        if (
            temperature
            and result["temperature"] != temperature
        ):
            continue

        filtered_leads.append(
            {
                "lead": lead,
                "score": result["score"],
                "temperature": result["temperature"],
            }
        )

    pipeline_counts = {}

    for pipeline_status in PIPELINE_STATUSES:
        pipeline_counts[pipeline_status] = (
            organization_leads_query()
            .filter(
                DemoLead.status == pipeline_status
            )
            .count()
        )

    total_leads = sum(pipeline_counts.values())

    hot_count = sum(
        1
        for item in filtered_leads
        if item["temperature"] == "hot"
    )

    warm_count = sum(
        1
        for item in filtered_leads
        if item["temperature"] == "warm"
    )

    cold_count = sum(
        1
        for item in filtered_leads
        if item["temperature"] == "cold"
    )

    return render_template(
        "admin/leads.html",
        leads=filtered_leads,
        pipeline_statuses=PIPELINE_STATUSES,
        selected_status=status,
        selected_temperature=temperature,
        search=search,
        pipeline_counts=pipeline_counts,
        total_leads=total_leads,
        hot_count=hot_count,
        warm_count=warm_count,
        cold_count=cold_count,
    )


@admin_leads.route(
    "/admin/leads/<int:lead_id>/status",
    methods=["POST"],
)
@admin_required
def update_status(lead_id):
    lead = (
        organization_leads_query()
        .filter(DemoLead.id == lead_id)
        .first_or_404()
    )

    status = request.form.get(
        "status",
        "",
    ).strip().lower()

    if status not in PIPELINE_STATUSES:
        flash(
            "Invalid lead status.",
            "error",
        )
        return redirect(
            url_for("admin_leads.leads")
        )

    previous_status = (
        (lead.status or "new")
        .strip()
        .lower()
    )

    lead.status = status

    if status == "won":
        if previous_status != "won" or lead.converted_at is None:
            lead.converted_at = datetime.utcnow()

    else:
        # A lead that leaves Won is no longer considered converted.
        lead.converted_at = None

    if status == "lost":
        lead.lost_reason = request.form.get(
            "lost_reason",
            "",
        ).strip() or lead.lost_reason

    else:
        # Clear stale loss metadata when the lead returns
        # to an active pipeline stage.
        lead.lost_reason = None

    score_lead(lead, persist=True)

    db.session.commit()

    flash(
        f"Lead {lead.company_name} moved to "
        f"{PIPELINE_STATUSES[status]}.",
        "success",
    )

    return redirect(
        url_for("admin_leads.leads")
    )


@admin_leads.route(
    "/admin/leads/<int:lead_id>/score",
    methods=["POST"],
)
@admin_required
def rescore_lead(lead_id):
    lead = (
        organization_leads_query()
        .filter(DemoLead.id == lead_id)
        .first_or_404()
    )

    result = score_lead(lead, persist=True)

    db.session.commit()

    flash(
        f"Lead {lead.company_name} scored "
        f"{result['score']} ({result['temperature']}).",
        "success",
    )

    return redirect(
        url_for("admin_leads.leads")
    )


@admin_leads.route(
    "/admin/leads/<int:lead_id>/convert",
    methods=["POST"],
)
@admin_required
def convert_lead(lead_id):
    lead = (
        organization_leads_query()
        .filter(DemoLead.id == lead_id)
        .first_or_404()
    )

    if lead.status == "won":
        flash(
            "Lead is already converted.",
            "info",
        )
        return redirect(
            url_for("admin_leads.leads")
        )

    lead.status = "won"
    lead.converted_at = datetime.utcnow()

    score_lead(lead, persist=True)

    db.session.commit()

    flash(
        f"Lead {lead.company_name} marked as won.",
        "success",
    )

    return redirect(
        url_for("admin_leads.leads")
    )


# ============================================================
# CRM V2 — LEAD DETAILS / ACTIVITIES / FOLLOW-UP
# ============================================================

from app.models.lead_activity import LeadActivity


def organization_lead_or_404(lead_id):
    return (
        organization_leads_query()
        .filter(DemoLead.id == lead_id)
        .first_or_404()
    )


@admin_leads.route(
    "/admin/leads/<int:lead_id>",
    methods=["GET"],
)
@admin_required
def lead_detail(lead_id):
    lead = organization_lead_or_404(lead_id)

    activities = (
        LeadActivity.query
        .filter(
            LeadActivity.lead_id == lead.id,
            LeadActivity.organization_id == lead.organization_id,
        )
        .order_by(LeadActivity.created_at.desc())
        .all()
    )

    result = score_lead(lead)

    return render_template(
        "admin/lead_detail.html",
        lead=lead,
        activities=activities,
        score=result["score"],
        temperature=result["temperature"],
        pipeline_statuses=PIPELINE_STATUSES,
    )


@admin_leads.route(
    "/admin/leads/<int:lead_id>/activity",
    methods=["POST"],
)
@admin_required
def add_activity(lead_id):
    lead = organization_lead_or_404(lead_id)

    activity_type = (
        request.form.get("activity_type", "note")
        .strip()
        .lower()
    )

    allowed_types = {
        "note",
        "call",
        "email",
        "whatsapp",
        "meeting",
        "follow_up",
    }

    if activity_type not in allowed_types:
        activity_type = "note"

    subject = request.form.get(
        "subject",
        "",
    ).strip()

    content = request.form.get(
        "content",
        "",
    ).strip()

    due_raw = request.form.get(
        "due_at",
        "",
    ).strip()

    due_at = None

    if due_raw:
        try:
            due_at = datetime.fromisoformat(
                due_raw.replace("Z", "")
            )
        except ValueError:
            due_at = None

    activity = LeadActivity(
        organization_id=lead.organization_id,
        lead_id=lead.id,
        user_id=getattr(
            request,
            "user",
            None,
        ).id if getattr(
            request,
            "user",
            None,
        ) else None,
        activity_type=activity_type,
        subject=subject or activity_type.title(),
        content=content,
        due_at=due_at,
    )

    db.session.add(activity)

    lead.last_contact_at = datetime.utcnow()

    if due_at:
        lead.next_follow_up_at = due_at

    if lead.status == "new":
        lead.status = "contacted"

    score_lead(lead, persist=True)

    db.session.commit()

    flash(
        "Lead activity added.",
        "success",
    )

    return redirect(
        url_for(
            "admin_leads.lead_detail",
            lead_id=lead.id,
        )
    )


@admin_leads.route(
    "/admin/leads/<int:lead_id>/follow-up",
    methods=["POST"],
)
@admin_required
def schedule_follow_up(lead_id):
    lead = organization_lead_or_404(lead_id)

    due_raw = request.form.get(
        "due_at",
        "",
    ).strip()

    if not due_raw:
        flash(
            "Follow-up date is required.",
            "error",
        )
        return redirect(
            url_for(
                "admin_leads.lead_detail",
                lead_id=lead.id,
            )
        )

    try:
        due_at = datetime.fromisoformat(
            due_raw.replace("Z", "")
        )
    except ValueError:
        flash(
            "Invalid follow-up date.",
            "error",
        )
        return redirect(
            url_for(
                "admin_leads.lead_detail",
                lead_id=lead.id,
            )
        )

    lead.next_follow_up_at = due_at

    activity = LeadActivity(
        organization_id=lead.organization_id,
        lead_id=lead.id,
        user_id=current_user.id,
        activity_type="follow_up",
        subject="Scheduled follow-up",
        content=request.form.get(
            "content",
            "",
        ).strip(),
        due_at=due_at,
    )

    db.session.add(activity)

    if lead.status == "new":
        lead.status = "contacted"

    db.session.commit()

    flash(
        "Follow-up scheduled.",
        "success",
    )

    return redirect(
        url_for(
            "admin_leads.lead_detail",
            lead_id=lead.id,
        )
    )


@admin_leads.route(
    "/admin/leads/<int:lead_id>/activity/<int:activity_id>/complete",
    methods=["POST"],
)
@admin_required
def complete_activity(lead_id, activity_id):
    lead = organization_lead_or_404(lead_id)

    activity = (
        LeadActivity.query
        .filter(
            LeadActivity.id == activity_id,
            LeadActivity.lead_id == lead.id,
            LeadActivity.organization_id == lead.organization_id,
        )
        .first_or_404()
    )

    activity.completed_at = datetime.utcnow()

    if (
        lead.next_follow_up_at
        and activity.due_at
        and lead.next_follow_up_at == activity.due_at
    ):
        lead.next_follow_up_at = None

    db.session.commit()

    flash(
        "Activity completed.",
        "success",
    )

    return redirect(
        url_for(
            "admin_leads.lead_detail",
            lead_id=lead.id,
        )
    )


@admin_leads.route(
    "/admin/follow-ups/execute-due",
    methods=["POST"],
)
@admin_required
def execute_due_follow_ups():
    from app.services.automation_service import automation_service

    result = automation_service.execute_due_follow_ups(limit=50)

    if result.get("success"):
        flash(
            f"Follow-up queue prepared: "
            f"{result.get('processed', 0)} item(s).",
            "success",
        )
    else:
        flash(
            "Follow-up execution failed.",
            "error",
        )

    return redirect(
        url_for("admin_leads.follow_ups")
    )



@admin_leads.route(
    "/admin/follow-ups/review",
    methods=["GET"],
)
@admin_required
def human_review_queue():
    from datetime import datetime

    now = datetime.utcnow()

    query = (
        LeadActivity.query
        .join(
            DemoLead,
            DemoLead.id == LeadActivity.lead_id,
        )
        .filter(
            LeadActivity.organization_id == DemoLead.organization_id,
            LeadActivity.activity_type == "follow_up",
            LeadActivity.completed_at.is_(None),
        )
    )

    due = (
        query
        .filter(LeadActivity.due_at.isnot(None))
        .filter(LeadActivity.due_at <= now)
        .order_by(LeadActivity.due_at.asc())
        .limit(100)
        .all()
    )

    upcoming = (
        query
        .filter(
            (LeadActivity.due_at.is_(None))
            | (LeadActivity.due_at > now)
        )
        .order_by(LeadActivity.due_at.asc())
        .limit(100)
        .all()
    )

    return render_template(
        "admin/human_review_queue.html",
        due=due,
        upcoming=upcoming,
        now=now,
    )


@admin_leads.route(
    "/admin/follow-ups/<int:activity_id>/approve",
    methods=["POST"],
)
@admin_required
def approve_follow_up(activity_id):
    activity = (
        LeadActivity.query
        .join(
            DemoLead,
            DemoLead.id == LeadActivity.lead_id,
        )
        .filter(
            LeadActivity.id == activity_id,
            LeadActivity.organization_id == DemoLead.organization_id,
            LeadActivity.activity_type == "follow_up",
            LeadActivity.completed_at.is_(None),
        )
        .first_or_404()
    )

    if not activity.due_at:
        flash(
            "Follow-up has no execution time.",
            "error",
        )
        return redirect(
            url_for("admin_leads.human_review_queue")
        )

    # V4.5 safety gate:
    # Human approval records the decision but does not
    # send email, WhatsApp, SMS, or payment requests.
    content = (activity.content or "").strip()

    approval_marker = "[HUMAN_APPROVED]"

    if approval_marker not in content:
        activity.content = (
            f"{content}\n{approval_marker}".strip()
        )

    db.session.commit()

    flash(
        "Follow-up approved. No external message was sent.",
        "success",
    )

    return redirect(
        url_for("admin_leads.human_review_queue")
    )


@admin_leads.route(
    "/admin/follow-ups/<int:activity_id>/complete-review",
    methods=["POST"],
)
@admin_required
def complete_review_follow_up(activity_id):
    activity = (
        LeadActivity.query
        .join(
            DemoLead,
            DemoLead.id == LeadActivity.lead_id,
        )
        .filter(
            LeadActivity.id == activity_id,
            LeadActivity.organization_id == DemoLead.organization_id,
            LeadActivity.activity_type == "follow_up",
        )
        .first_or_404()
    )

    if activity.completed_at is None:
        activity.completed_at = datetime.utcnow()

    db.session.commit()

    flash(
        "Follow-up marked as completed.",
        "success",
    )

    return redirect(
        url_for("admin_leads.human_review_queue")
    )


@admin_leads.route(
    "/admin/follow-ups/<int:activity_id>/skip",
    methods=["POST"],
)
@admin_required
def skip_follow_up(activity_id):
    activity = (
        LeadActivity.query
        .join(
            DemoLead,
            DemoLead.id == LeadActivity.lead_id,
        )
        .filter(
            LeadActivity.id == activity_id,
            LeadActivity.organization_id == DemoLead.organization_id,
            LeadActivity.activity_type == "follow_up",
            LeadActivity.completed_at.is_(None),
        )
        .first_or_404()
    )

    content = (activity.content or "").strip()

    skip_marker = "[HUMAN_SKIPPED]"

    if skip_marker not in content:
        activity.content = (
            f"{content}\n{skip_marker}".strip()
        )

    activity.completed_at = datetime.utcnow()

    lead = DemoLead.query.filter(
        DemoLead.id == activity.lead_id,
        DemoLead.organization_id == activity.organization_id,
    ).first()

    if (
        lead is not None
        and lead.next_follow_up_at
        and activity.due_at
        and lead.next_follow_up_at == activity.due_at
    ):
        lead.next_follow_up_at = None

    db.session.commit()

    flash(
        "Follow-up skipped by human review.",
        "success",
    )

    return redirect(
        url_for("admin_leads.human_review_queue")
    )

@admin_leads.route(
    "/admin/follow-ups",
    methods=["GET"],
)
@admin_required
def follow_ups():
    now = datetime.utcnow()

    query = organization_leads_query().filter(
        DemoLead.next_follow_up_at.isnot(None)
    )

    due = (
        query
        .filter(
            DemoLead.next_follow_up_at <= now
        )
        .order_by(
            DemoLead.next_follow_up_at.asc()
        )
        .all()
    )

    upcoming = (
        query
        .filter(
            DemoLead.next_follow_up_at > now
        )
        .order_by(
            DemoLead.next_follow_up_at.asc()
        )
        .all()
    )

    return render_template(
        "admin/follow_ups.html",
        due=due,
        upcoming=upcoming,
    )



# CRM_V4_DASHBOARD
@admin_leads.route("/admin/leads/dashboard")
@admin_required
def dashboard():
    from datetime import datetime

    query = organization_leads_query()
    leads = query.all()

    total = len(leads)
    hot = warm = cold = 0
    pipeline_value = 0.0
    won_value = 0.0
    won_count = 0

    for lead in leads:
        result = score_lead(lead)
        temperature = result["temperature"]

        if temperature == "hot":
            hot += 1
        elif temperature == "warm":
            warm += 1
        else:
            cold += 1

        value = float(lead.estimated_value or 0)

        if (lead.status or "").lower() not in {"lost"}:
            pipeline_value += value

        if (lead.status or "").lower() in {"won", "converted"}:
            won_count += 1
            won_value += value

    conversion_rate = (
        round((won_count / total) * 100, 2)
        if total else 0
    )

    now = datetime.utcnow()

    overdue = sum(
        1 for lead in leads
        if lead.next_follow_up_at
        and lead.next_follow_up_at < now
    )

    today = sum(
        1 for lead in leads
        if lead.next_follow_up_at
        and lead.next_follow_up_at.date() == now.date()
    )

    upcoming = sum(
        1 for lead in leads
        if lead.next_follow_up_at
        and lead.next_follow_up_at > now
        and lead.next_follow_up_at.date() != now.date()
    )

    return render_template(
        "admin/leads_dashboard.html",
        total=total,
        hot=hot,
        warm=warm,
        cold=cold,
        pipeline_value=pipeline_value,
        won_value=won_value,
        won_count=won_count,
        conversion_rate=conversion_rate,
        overdue=overdue,
        today=today,
        upcoming=upcoming,
    )

@admin_leads.route("/admin/leads/pipeline")
@admin_required
def pipeline():
    organization_id = current_user.organization_id

    query = DemoLead.query

    if organization_id is not None:
        query = query.filter(
            DemoLead.organization_id == organization_id
        )

    leads = (
        query
        .order_by(
            DemoLead.lead_score.desc(),
            DemoLead.created_at.desc(),
        )
        .all()
    )

    stages = {
        "new": [],
        "contacted": [],
        "qualified": [],
        "proposal": [],
        "won": [],
        "lost": [],
    }

    for lead in leads:
        status = (lead.status or "new").lower()

        # Legacy CRM compatibility:
        # Older records may use "converted".
        # Pipeline treats converted leads as Won.
        if status == "converted":
            status = "won"

        if status not in stages:
            status = "new"

        stages[status].append(lead)

    pipeline_stats = {
        "total": len(leads),
        "new": len(stages["new"]),
        "contacted": len(stages["contacted"]),
        "qualified": len(stages["qualified"]),
        "proposal": len(stages["proposal"]),
        "won": len(stages["won"]),
        "lost": len(stages["lost"]),
        "pipeline_value": sum(
            float(lead.estimated_value or 0)
            for lead in leads
            if (lead.status or "").lower() != "lost"
        ),
        "won_value": sum(
            float(lead.estimated_value or 0)
            for lead in leads
            if (lead.status or "").lower() in {"won", "converted"}
        ),
    }

    return render_template(
        "admin/leads_pipeline.html",
        stages=stages,
        pipeline_stats=pipeline_stats,
    )


@admin_leads.route("/admin/leads/api/pipeline-intelligence")
@admin_required
def pipeline_intelligence():
    organization_id = getattr(current_user, "organization_id", None)
    from app.services.crm_pipeline_intelligence import crm_pipeline_intelligence
    result = crm_pipeline_intelligence.build(organization_id)
    return jsonify(result), 200 if result.get("success") else 400

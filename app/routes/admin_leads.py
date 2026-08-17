from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required
from werkzeug.security import generate_password_hash
import secrets
import string

from app import db
from app.models.demo_lead import DemoLead
from app.models.organization import Organization
from app.models.subscription import Subscription
from app.models.user import User

admin_leads = Blueprint("admin_leads", __name__)


@admin_leads.route("/admin/leads")
@login_required
def leads():
    leads = DemoLead.query.order_by(
        DemoLead.created_at.desc()
    ).all()

    return render_template(
        "admin/leads.html",
        leads=leads
    )


@admin_leads.route("/admin/leads/<int:lead_id>/convert", methods=["POST"])
@login_required
def convert_lead(lead_id):

    lead = DemoLead.query.get_or_404(lead_id)

    if lead.status == "converted":
        flash("تم تحويل الطلب مسبقًا")
        return redirect(url_for("admin_leads.leads"))

    existing_user = User.query.filter_by(
        email=lead.email
    ).first()

    if existing_user:
        flash("يوجد حساب بهذا البريد بالفعل")
        return redirect(url_for("admin_leads.leads"))

    base_slug = f"demo-{lead.id}"
    slug = base_slug
    counter = 1

    while Organization.query.filter_by(slug=slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1

    organization = Organization(
        name=lead.company_name,
        slug=slug
    )

    db.session.add(organization)
    db.session.flush()

    subscription = Subscription(
        organization_id=organization.id,
        plan="free",
        status="active"
    )

    temp_password = "".join(
        secrets.choice(string.ascii_letters + string.digits)
        for _ in range(12)
    )

    user = User(
        organization_id=organization.id,
        full_name=lead.company_name,
        email=lead.email,
        password_hash=generate_password_hash(temp_password),
        role="admin",
        must_change_password=True
    )

    db.session.add(subscription)
    db.session.add(user)

    lead.status = "converted"

    db.session.commit()

    flash(f"تم إنشاء الحساب بنجاح - البريد: {lead.email} - كلمة المرور المؤقتة: {temp_password}")

    return redirect(url_for("admin_leads.leads"))

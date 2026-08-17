from flask import Blueprint, render_template, redirect, url_for, request, flash
from werkzeug.security import check_password_hash, generate_password_hash
from flask_login import login_user, logout_user, login_required, current_user

from app.models.user import User
from app.models.organization import Organization
from app.models.subscription import Subscription
from app import db
from app.services.social_auth_service import (
    google_authorize_url,
    google_login,
    facebook_authorize_url,
    facebook_login,
)
from app.forms import LoginForm, RegisterForm

auth = Blueprint("auth", __name__)


@auth.route("/register", methods=["GET", "POST"])
def register():
    form = RegisterForm()

    if form.validate_on_submit():
        existing_user = User.query.filter_by(email=form.email.data).first()

        if existing_user:
            return "Email already registered"

        organization_name = f"{form.full_name.data}'s Organization"
        base_slug = form.email.data.split("@")[0].lower()
        slug = base_slug

        counter = 1
        while Organization.query.filter_by(slug=slug).first():
            slug = f"{base_slug}-{counter}"
            counter += 1

        organization = Organization(
            name=organization_name,
            slug=slug
        )

        db.session.add(organization)
        db.session.flush()

        subscription = Subscription(
            organization_id=organization.id,
            plan="free",
            status="active"
        )

        user = User(
            organization_id=organization.id,
            full_name=form.full_name.data,
            email=form.email.data,
            password_hash=generate_password_hash(form.password.data),
            role="admin"
        )

        db.session.add(subscription)
        db.session.add(user)
        db.session.commit()

        login_user(user)

        return redirect(url_for("main.home"))

    return render_template("register.html", form=form)


@auth.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()

    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()

        if user and check_password_hash(
            user.password_hash,
            form.password.data
        ):
            login_user(user)

            if user.must_change_password:
                return redirect(url_for("auth.change_password"))

            return redirect(url_for("main.home"))

    return render_template("login.html", form=form)


@auth.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    if form := None:
        pass

    if request.method == "POST":
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if len(password) < 8:
            flash("كلمة المرور يجب أن تكون 8 أحرف على الأقل")
            return render_template("change_password.html")

        if password != confirm_password:
            flash("كلمتا المرور غير متطابقتين")
            return render_template("change_password.html")

        current_user.password_hash = generate_password_hash(password)
        current_user.must_change_password = False
        db.session.commit()

        flash("تم تغيير كلمة المرور بنجاح")
        return redirect(url_for("main.home"))

    return render_template("change_password.html")


@auth.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


@auth.route("/auth/google")
def google():
    try:
        return redirect(google_authorize_url())
    except Exception as e:
        flash(str(e))
        return redirect(url_for("auth.login"))


@auth.route("/auth/google/callback")
def google_callback():
    code = request.args.get("code", "").strip()

    if not code:
        flash("Google login was cancelled or failed.")
        return redirect(url_for("auth.login"))

    try:
        user = google_login(code)
        login_user(user)

        if user.must_change_password:
            return redirect(url_for("auth.change_password"))

        return redirect(url_for("main.home"))

    except Exception as e:
        db.session.rollback()
        flash(f"Google login failed: {e}")
        return redirect(url_for("auth.login"))


@auth.route("/auth/facebook")
def facebook():
    try:
        return redirect(facebook_authorize_url())
    except Exception as e:
        flash(str(e))
        return redirect(url_for("auth.login"))


@auth.route("/auth/facebook/callback")
def facebook_callback():
    code = request.args.get("code", "").strip()

    if not code:
        flash("Facebook login was cancelled or failed.")
        return redirect(url_for("auth.login"))

    try:
        user = facebook_login(code)
        login_user(user)

        if user.must_change_password:
            return redirect(url_for("auth.change_password"))

        return redirect(url_for("main.home"))

    except Exception as e:
        db.session.rollback()
        flash(f"Facebook login failed: {e}")
        return redirect(url_for("auth.login"))

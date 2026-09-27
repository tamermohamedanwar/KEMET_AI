from flask import Blueprint, render_template, abort, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.models.user import User
from app.models.chat import ChatMessage

admin = Blueprint("admin", __name__, url_prefix="/admin")


@admin.route("/")
@login_required
def dashboard():

    if current_user.role != "admin":
        abort(403)

    organization_id = current_user.organization_id

    users_count = User.query.filter_by(
        organization_id=organization_id
    ).count()
    chats_count = (
        ChatMessage.query
        .join(User, ChatMessage.user_id == User.id)
        .filter(User.organization_id == organization_id)
        .count()
    )
    admins_count = User.query.filter_by(
        organization_id=organization_id,
        role="admin",
    ).count()

    users = (
        User.query
        .filter_by(organization_id=organization_id)
        .order_by(User.id.desc())
        .limit(10)
        .all()
    )

    chats = (
        ChatMessage.query
        .join(User, ChatMessage.user_id == User.id)
        .filter(User.organization_id == organization_id)
        .order_by(ChatMessage.id.desc())
        .limit(10)
        .all()
    )

    return render_template(
        "admin.html",
        users_count=users_count,
        chats_count=chats_count,
        admins_count=admins_count,
        users=users,
        chats=chats
    )


@admin.route("/users")
@login_required
def manage_users():
    if current_user.role != "admin":
        abort(403)

    users = User.query.filter_by(organization_id=current_user.organization_id).order_by(User.id.desc()).all()

    return render_template(
        "admin_users.html",
        users=users
    )


@admin.route("/users/toggle/<int:user_id>", methods=["POST"])
@login_required
def toggle_role(user_id):
    if current_user.role != "admin":
        abort(403)

    user = User.query.filter_by(id=user_id, organization_id=current_user.organization_id).first_or_404()

    if user.id != current_user.id:
        if user.role == "admin" and User.query.filter_by(organization_id=current_user.organization_id, role="admin").count() <= 1:
            abort(409)
        user.role = "admin" if user.role == "user" else "user"
        db.session.commit()
        flash("User role updated successfully")

    return redirect(url_for("admin.manage_users"))


@admin.route("/users/delete/<int:user_id>", methods=["POST"])
@login_required
def delete_user(user_id):
    if current_user.role != "admin":
        abort(403)

    user = User.query.filter_by(id=user_id, organization_id=current_user.organization_id).first_or_404()

    if user.id != current_user.id:
        if user.role == "admin" and User.query.filter_by(organization_id=current_user.organization_id, role="admin").count() <= 1:
            abort(409)
        ChatMessage.query.filter_by(user_id=user.id).delete()
        db.session.delete(user)
        db.session.commit()
        flash("User deleted successfully")

    return redirect(url_for("admin.manage_users"))

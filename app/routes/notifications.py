from datetime import datetime

from flask import Blueprint, redirect, render_template, url_for
from flask_login import login_required, current_user

from app import db
from app.models.notification import Notification


notifications_bp = Blueprint(
    "notifications",
    __name__,
    url_prefix="/notifications",
)


def _organization_id():
    return getattr(current_user, "organization_id", None)


def _visible_notifications():
    organization_id = _organization_id()
    user_id = getattr(current_user, "id", None)

    query = Notification.query

    if organization_id is not None and user_id is not None:
        query = query.filter(
            Notification.organization_id == organization_id,
            (
                (Notification.user_id == user_id)
                | (Notification.user_id.is_(None))
            ),
        )
    elif user_id is not None:
        query = query.filter(Notification.user_id == user_id)
    else:
        query = query.filter(Notification.id == -1)

    return query


@notifications_bp.route("/")
@login_required
def index():
    notifications = (
        _visible_notifications()
        .order_by(Notification.created_at.desc())
        .all()
    )

    unread_count = sum(
        1 for notification in notifications if not notification.is_read
    )

    return render_template(
        "notifications.html",
        notifications=notifications,
        unread_count=unread_count,
    )


@notifications_bp.route("/<int:notification_id>/read", methods=["POST"])
@login_required
def mark_read(notification_id):
    notification = (
        _visible_notifications()
        .filter(Notification.id == notification_id)
        .first_or_404()
    )

    if not notification.is_read:
        notification.is_read = True
        notification.read_at = datetime.utcnow()
        db.session.commit()

    return redirect(url_for("notifications.index"))


@notifications_bp.route("/read-all", methods=["POST"])
@login_required
def mark_all_read():
    notifications = (
        _visible_notifications()
        .filter(Notification.is_read.is_(False))
        .all()
    )

    now = datetime.utcnow()

    for notification in notifications:
        notification.is_read = True
        notification.read_at = now

    if notifications:
        db.session.commit()

    return redirect(url_for("notifications.index"))

from flask import Flask, request, g, got_request_exception
import secrets
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate
import os
from app.config.settings import SECRET_KEY, DATABASE_URL
from app.core.rate_limit import limiter
from app.core.security_headers import apply_security_headers
from app.core.database_telemetry import database_telemetry
from app.core.application_telemetry import application_telemetry

db = SQLAlchemy()
login_manager = LoginManager()

from app.routes.kemet_decision_center import kemet_decision_center_bp
from app.routes.bos_command_center import bos_command_center_bp
from app.routes.industry_api import industry_api_bp
from app.routes.workforce_api import workforce_api_bp

@login_manager.unauthorized_handler
def api_unauthorized():
    from flask import jsonify, request, redirect, url_for

    if request.path.startswith("/api/"):
        return jsonify({
            "error": "authentication_required",
            "message": "Authentication required"
        }), 401

    return redirect(url_for("auth.login", next=request.full_path))
csrf = CSRFProtect()
migrate = Migrate()


@login_manager.user_loader
def load_user(user_id):
    from app.models import User
    return db.session.get(User, int(user_id))


def create_app():
    app = Flask(__name__)
    application_telemetry.configure_logging()
    from .routes.admin_automation import admin_automation_bp
    app.register_blueprint(kemet_decision_center_bp)
    app.register_blueprint(admin_automation_bp, url_prefix="/admin/automation")

    env = os.getenv("FLASK_ENV", "development")

    if env == "production":
        from app.config.production import DEBUG, TESTING
    elif env == "testing":
        from app.config.testing import DEBUG, TESTING
    else:
        from app.config.development import DEBUG, TESTING

    app.config["DEBUG"] = DEBUG
    app.config["TESTING"] = TESTING

    app.config["SECRET_KEY"] = SECRET_KEY
    app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    if DATABASE_URL.startswith(("postgresql://", "postgres://", "postgresql+")):
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
            "pool_pre_ping": True,
            "pool_size": int(os.getenv("KEMET_DB_POOL_SIZE", "10")),
            "max_overflow": int(os.getenv("KEMET_DB_MAX_OVERFLOW", "20")),
            "pool_timeout": int(os.getenv("KEMET_DB_POOL_TIMEOUT", "30")),
            "pool_recycle": int(os.getenv("KEMET_DB_POOL_RECYCLE", "1800")),
        }

    app.config["WTF_CSRF_CHECK_DEFAULT"] = True
    app.config["SESSION_COOKIE_NAME"] = "session"
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SECURE"] = env == "production"
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    @app.before_request
    def assign_correlation_id():
        incoming = (
            request.headers.get("X-Kemet-Correlation-ID", "").strip()
            or request.headers.get("X-Request-ID", "").strip()
        )
        g.kemet_correlation_id = incoming[:128] if incoming else secrets.token_hex(16)
        g.kemet_request_span, g.kemet_request_timer = application_telemetry.start_request(
            method=request.method, path=request.path, correlation_id=g.kemet_correlation_id
        )

    @app.after_request
    def application_telemetry_response(response):
        span = getattr(g, "kemet_request_span", None)
        started = getattr(g, "kemet_request_timer", None)
        if span is not None and started is not None:
            application_telemetry.finish_request(
                span=span,
                started=started,
                method=request.method,
                path=request.path,
                status_code=response.status_code,
                correlation_id=getattr(g, "kemet_correlation_id", ""),
            )
        response.headers["X-Request-ID"] = getattr(g, "kemet_correlation_id", "")
        return response


    @got_request_exception.connect_via(app)
    def application_telemetry_exception(sender, exception, **kwargs):
        span = getattr(g, "kemet_request_span", None)
        if span is not None:
            application_telemetry.record_exception(
                span=span,
                method=request.method,
                path=request.path,
                correlation_id=getattr(g, "kemet_correlation_id", ""),
                exception=exception,
            )


    @app.after_request
    def security_response_controls(response):
        response.headers["X-Kemet-Correlation-ID"] = getattr(g, "kemet_correlation_id", "")
        if response.status_code in (401, 403, 429):
            try:
                from app.core.security_events import record_security_event
                record_security_event(
                    "request_security_denied",
                    status=str(response.status_code),
                    severity="high" if response.status_code in (401, 403) else "medium",
                    action=request.endpoint,
                    actor_type="request",
                    organization_id=None,
                    correlation_id=getattr(g, "kemet_correlation_id", None),
                    metadata={"method": request.method, "path": request.path, "status": response.status_code},
                )
            except Exception:
                db.session.rollback()
        return response


    csrf.init_app(app)
    limiter.init_app(app)
    apply_security_headers(app)

    @app.before_request
    def enforce_api_browser_origin():
        if request.path.startswith("/api/bos/channels/telegram/webhook/"):
            return None
        if not request.path.startswith("/api/") or request.method in {"GET", "HEAD", "OPTIONS"}:
            return None
        if app.config.get("TESTING"):
            return None
        if request.headers.get("Authorization", "").strip():
            return None
        origin = request.headers.get("Origin", "").strip()
        host = request.host_url.rstrip("/")
        if origin and origin.rstrip("/") == host:
            return None
        referer = request.headers.get("Referer", "").strip()
        if referer.startswith(host + "/") or referer == host:
            return None
        from flask import jsonify
        return jsonify({"error": "csrf_origin_required", "message": "A same-origin request or bearer authorization is required."}), 403


    db.init_app(app)
    migrate.init_app(app, db)
    with app.app_context():
        database_telemetry.install(db.engine)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    from app.routes.main import main
    from app.routes.auth import auth
    from app.routes.conversations import conversations
    from app.ai.chat import chat
    from app.api.routes import api
    from app.admin.routes import admin
    from app.routes.upload import upload_bp
    from app.routes.settings import settings_bp
    from app.routes.dashboard import dashboard
    from app.routes.tickets import tickets
    from app.routes.admin_support import admin_support
    from app.routes.admin_leads import admin_leads
    from app.routes.billing import billing_bp
    from app.routes.admin_billing import admin_billing_bp
    from app.routes.notifications import notifications_bp
    from app.routes.salla_whatsapp_product import salla_whatsapp_product_bp
    from app.routes.salla_whatsapp_bot import salla_whatsapp_bot_bp
    from app.errors import register_error_handlers

    app.register_blueprint(main)
    app.register_blueprint(auth)
    app.register_blueprint(conversations)
    app.register_blueprint(chat)

    csrf.exempt(chat)
    app.register_blueprint(api)
    app.register_blueprint(admin)
    app.register_blueprint(upload_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(dashboard)
    app.register_blueprint(tickets)
    app.register_blueprint(admin_support)
    app.register_blueprint(admin_leads)
    app.register_blueprint(admin_revenue)
    app.register_blueprint(revenue_pipeline_bp)
    app.register_blueprint(billing_bp)
    app.register_blueprint(admin_billing_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(salla_whatsapp_product_bp)
    app.register_blueprint(salla_whatsapp_bot_bp)
    app.register_blueprint(admin_bridge)
    app.register_blueprint(command_agent_bp)
    app.register_blueprint(bos_command_bp)

    register_error_handlers(app)

    from app.tasks import chat_workflow

    with app.app_context():
        from app import models
        db.create_all()

    app.register_blueprint(bos_command_center_bp)
    app.register_blueprint(industry_api_bp)
    app.register_blueprint(workforce_api_bp)

    from app.routes.command_center import command_center_bp
    app.register_blueprint(command_center_bp)
    from app.routes.federation import federation_bp
    app.register_blueprint(federation_bp)

    app.register_blueprint(db_telemetry_bp)
    app.register_blueprint(execution_bp)

    return app
from app.routes.admin_revenue import admin_revenue
from app.routes.revenue_pipeline import revenue_pipeline_bp
from app.routes.admin_bridge import admin_bridge
from app.routes.command_agent import command_agent_bp
from app.routes.bos_command import bos_command_bp
from app.routes.db_telemetry import db_telemetry_bp
from app.routes.execution_center import execution_bp

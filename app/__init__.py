from app.routes.kemet_decision_center import kemet_decision_center_bp
from app.routes.bos_command_center import bos_command_center_bp
from app.routes.industry_api import industry_api_bp
from app.routes.workforce_api import workforce_api_bp
from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate
import os
from app.config.settings import SECRET_KEY, DATABASE_URL

db = SQLAlchemy()
login_manager = LoginManager()

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
    return User.query.get(int(user_id))


def create_app():
    app = Flask(__name__)
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

    app.config["WTF_CSRF_CHECK_DEFAULT"] = True
    app.config["SESSION_COOKIE_NAME"] = "session"
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SECURE"] = False
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"


    csrf.init_app(app)

    @app.before_request
    def disable_csrf_for_api():
        if request.path.startswith("/api/"):
            return None

    @app.before_request
    def skip_csrf_for_api():
        if request.path.startswith("/api/"):
            setattr(request, "_dont_check_csrf", True)


    db.init_app(app)
    migrate.init_app(app, db)
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
    from app.errors import register_error_handlers

    app.register_blueprint(main)
    app.register_blueprint(auth)
    app.register_blueprint(conversations)
    app.register_blueprint(chat)

    csrf.exempt(chat)
    app.register_blueprint(api)
    csrf.exempt(api)
    app.register_blueprint(admin)
    app.register_blueprint(upload_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(dashboard)
    app.register_blueprint(tickets)
    app.register_blueprint(admin_support)
    app.register_blueprint(admin_leads)
    app.register_blueprint(admin_revenue)
    app.register_blueprint(billing_bp)
    app.register_blueprint(admin_billing_bp)
    app.register_blueprint(notifications_bp)
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

    app.register_blueprint(execution_bp)

    return app
from app.routes.admin_revenue import admin_revenue
from app.routes.admin_bridge import admin_bridge
from app.routes.command_agent import command_agent_bp
from app.routes.bos_command import bos_command_bp
from app.routes.execution_center import execution_bp

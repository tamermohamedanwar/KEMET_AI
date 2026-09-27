import os
from flask import has_app_context
from sqlalchemy import text
from app import db


class ProductionReadinessService:
    VERSION = "2.1"

    @staticmethod
    def check():
        checks = {}
        in_context = has_app_context()
        try:
            if not in_context:
                checks["database"] = "not_verified"
                checks["database_error_type"] = "application_context_required"
                checks["database_integrity_violations"] = None
                checks["database_dialect"] = "not_verified"
            else:
                db.session.execute(text("SELECT 1"))
                dialect = str(getattr(db.engine.dialect, "name", "unknown"))
                checks["database_dialect"] = dialect
                if dialect == "sqlite":
                    integrity = db.session.execute(text("PRAGMA foreign_key_check")).fetchall()
                    checks["database"] = "ok" if not integrity else "failed"
                    checks["database_integrity_violations"] = len(integrity)
                else:
                    checks["database"] = "ok"
                    checks["database_integrity_violations"] = None
        except Exception as exc:
            if has_app_context():
                db.session.rollback()
            checks["database"] = "failed"
            checks["database_integrity_violations"] = None
            checks["database_error_type"] = type(exc).__name__
            if "database_dialect" not in checks:
                checks["database_dialect"] = "not_verified"

        required = ("SECRET_KEY", "KEMET_EXECUTION_SECRET")
        checks["configuration"] = "ok" if all(os.getenv(k) for k in required) else "failed"

        log_level = os.getenv("LOG_LEVEL", "").strip().upper()
        allowed_log_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        checks["observability"] = "ok" if log_level in allowed_log_levels else "warning"

        payment_mode = os.getenv("PAYMENT_MODE", "mock").strip().lower()
        environment = os.getenv("FLASK_ENV", "development").strip().lower()
        if payment_mode == "mock":
            checks["payment"] = "failed" if environment == "production" else "ok"
        elif payment_mode == "paymob":
            payment_keys = (
                "PAYMOB_API_KEY",
                "PAYMOB_SECRET_KEY",
                "PAYMOB_PUBLIC_KEY",
                "PAYMOB_INTEGRATION_ID",
                "PAYMOB_HMAC_SECRET",
            )
            checks["payment"] = "ok" if all(os.getenv(k) for k in payment_keys) else "failed"
        else:
            checks["payment"] = "failed"

        if environment == "production" and checks.get("database_dialect") != "postgresql":
            checks["production_database"] = "failed"
        else:
            checks["production_database"] = "ok"

        readiness_checks = (
            "database", "configuration", "observability", "payment", "production_database"
        )
        ready = all(checks.get(key) in {"ok", "warning"} for key in readiness_checks)
        return {
            "status": "ready" if ready else "not_ready",
            "success": ready,
            "engine": "kemet_production_readiness",
            "version": ProductionReadinessService.VERSION,
            "checks": checks,
            "governance": {
                "read_only": True,
                "advisory": True,
                "external_execution": False,
                "database_mutation": False,
            },
        }


production_readiness = ProductionReadinessService()

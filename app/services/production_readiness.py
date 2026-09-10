import os
from sqlalchemy import text
from app import db

class ProductionReadinessService:
    VERSION = "1.0"

    @staticmethod
    def check():
        checks = {}
        try:
            db.session.execute(text("SELECT 1"))
            checks["database"] = "ok"
        except Exception:
            checks["database"] = "failed"
        required = ("SECRET_KEY", "KEMET_EXECUTION_SECRET")
        checks["configuration"] = "ok" if all(os.getenv(k) for k in required) else "failed"

        observability_keys = ("LOG_LEVEL",)
        checks["observability"] = "ok" if all(os.getenv(k) for k in observability_keys) else "warning"

        payment_mode = os.getenv("PAYMENT_MODE", "mock").strip().lower()
        if payment_mode == "mock":
            checks["payment"] = "ok"
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

        ready = all(value in {"ok", "warning"} for value in checks.values())
        return {"status": "ready" if ready else "not_ready", "success": ready, "engine": "kemet_production_readiness", "version": ProductionReadinessService.VERSION, "checks": checks, "governance": {"read_only": True, "advisory": True, "external_execution": False, "database_mutation": False}}

production_readiness = ProductionReadinessService()

import os


def security_readiness():
    env = os.getenv("FLASK_ENV", "development").lower()
    checks = {
        "secret_key": bool(os.getenv("SECRET_KEY")),
        "rate_limit_shared_storage": not (env == "production" and os.getenv("RATELIMIT_STORAGE_URI", "memory://").startswith("memory://")),
        "secure_session": env != "production" or os.getenv("SESSION_COOKIE_SECURE", "1") != "0",
        "mcp_disabled": True,
    }
    blocking = [name for name, ok in checks.items() if not ok]
    return {"ready": not blocking, "environment": env, "checks": checks, "blocking": blocking}

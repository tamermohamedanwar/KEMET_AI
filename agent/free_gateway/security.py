import os
from functools import wraps
from flask import request, jsonify

TOKEN = os.getenv("KEMET_AGENT_TOKEN", "")

def require_token(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not TOKEN:
            return jsonify({
                "ok": False,
                "error": "token_not_configured"
            }), 500

        supplied = request.headers.get("Authorization", "")

        if supplied != f"Bearer {TOKEN}":
            return jsonify({
                "ok": False,
                "error": "unauthorized"
            }), 401

        return fn(*args, **kwargs)

    return wrapper

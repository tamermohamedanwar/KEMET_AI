from __future__ import annotations

import os
from flask import request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


def _identity_key() -> str:
    email = str(request.form.get("email") or "").strip().lower()
    return f"{get_remote_address()}:{email[:160]}"


limiter = Limiter(
    key_func=_identity_key,
    storage_uri=os.getenv("RATELIMIT_STORAGE_URI", "memory://"),
    strategy="fixed-window",
    headers_enabled=True,
)

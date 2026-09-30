from __future__ import annotations
from datetime import datetime, timezone
from functools import wraps
import hashlib, json, secrets
from flask import g, jsonify, request
from app import db
from app.models.api_key import ApiKey, ApiUsageEvent

KEY_PREFIX="kemet_"
def _hash(raw): return hashlib.sha256(raw.encode()).hexdigest()

def create_api_key(*, organization_id, name, scopes=None):
    raw=KEY_PREFIX+secrets.token_urlsafe(32)
    obj=ApiKey(organization_id=int(organization_id), name=(name or "API key").strip()[:120],
               key_prefix=raw[:16], key_hash=_hash(raw),
               scopes_json=json.dumps(sorted(set(scopes or ["document_intelligence"]))))
    db.session.add(obj); db.session.commit()
    return obj, raw

def authenticate_api_key(raw):
    if not raw or not raw.startswith(KEY_PREFIX): return None
    obj=ApiKey.query.filter_by(key_hash=_hash(raw),status="active").first()
    if not obj: return None
    now=datetime.now(timezone.utc).replace(tzinfo=None)
    if obj.expires_at and obj.expires_at<=now:
        obj.status="expired"; db.session.commit(); return None
    return obj

def record_usage(key,status_code,units=1):
    key.requests_count=int(key.requests_count or 0)+int(units)
    key.last_used_at=datetime.utcnow()
    db.session.add(ApiUsageEvent(api_key_id=key.id,organization_id=key.organization_id,
                                  route=request.path[:255],status_code=int(status_code),units=int(units),
                                  request_id=getattr(g,"kemet_correlation_id",None)))
    db.session.commit()

def require_api_key(scope=None):
    def decorator(fn):
        @wraps(fn)
        def wrapped(*args,**kwargs):
            key=authenticate_api_key(request.headers.get("X-Kemet-API-Key","").strip())
            if not key: return jsonify({"ok":False,"error":"invalid_api_key"}),401
            scopes=set(json.loads(key.scopes_json or "[]"))
            if scope and scope not in scopes:
                record_usage(key,403); return jsonify({"ok":False,"error":"scope_not_granted"}),403
            g.kemet_api_key=key; g.kemet_organization_id=key.organization_id
            try:
                response=fn(*args,**kwargs)
                record_usage(key,getattr(response,"status_code",200) or 200); return response
            except Exception:
                record_usage(key,500); raise
        return wrapped
    return decorator

def revoke_api_key(key):
    key.status="revoked"; key.revoked_at=datetime.utcnow(); db.session.commit()

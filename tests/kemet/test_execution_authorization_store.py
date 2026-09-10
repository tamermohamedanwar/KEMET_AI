import time
import uuid

from wsgi import application
from app import db
from app.models.organization import Organization
from app.core.execution.authorization import execution_authorization
from app.core.execution_authorization_store import execution_authorization_store


def test_authorization_consumption_is_durable_and_one_time():
    with application.app_context():
        db.create_all()
        uid = uuid.uuid4().hex
        org = Organization(name=f"Auth {uid}", slug=f"auth-{uid}")
        db.session.add(org)
        db.session.commit()
        authorization = {
            "token": f"token-{uid}",
            "plan_hash": "plan-hash",
            "action": "create_ticket",
            "approver_id": 7,
            "expires_at": int(time.time()) + 300,
        }
        plan = {"organization_id": org.id, "action": "create_ticket"}
        assert execution_authorization.consume(authorization, plan=plan, action="create_ticket") is True
        assert execution_authorization.consume(authorization, plan=plan, action="create_ticket") is False
        saved = execution_authorization_store.token_hash(authorization["token"])
        from app.models.execution_authorization_consumption import ExecutionAuthorizationConsumption
        row = ExecutionAuthorizationConsumption.query.filter_by(token_hash=saved).one()
        assert row.organization_id == org.id
        assert row.plan_hash == "plan-hash"
        assert row.action == "create_ticket"


def test_authorization_consumption_is_not_in_memory_only():
    with application.app_context():
        db.create_all()
        uid = uuid.uuid4().hex
        authorization = {
            "token": f"restart-{uid}",
            "expires_at": int(time.time()) + 300,
        }
        assert execution_authorization_store.consume(authorization) is True
        assert execution_authorization_store.consume(authorization) is False

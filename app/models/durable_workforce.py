from datetime import datetime

from app import db


class WorkforceMembership(db.Model):
    __tablename__ = "workforce_memberships"

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False, index=True)
    workforce_id = db.Column(db.String(120), nullable=False, index=True)
    role = db.Column(db.String(120), nullable=False)
    status = db.Column(db.String(30), nullable=False, default="active", index=True)
    capabilities_json = db.Column(db.Text, nullable=False, default="[]")
    allowed_actions_json = db.Column(db.Text, nullable=False, default="[]")
    approval_actions_json = db.Column(db.Text, nullable=False, default="[]")
    metrics_json = db.Column(db.Text, nullable=False, default="[]")
    permission_version = db.Column(db.String(80), nullable=False, default="1")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (db.Index("uq_workforce_membership_org_agent", "organization_id", "workforce_id", unique=True),)


class WorkforceAssignment(db.Model):
    __tablename__ = "workforce_assignments"

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False, index=True)
    membership_id = db.Column(db.Integer, db.ForeignKey("workforce_memberships.id"), nullable=False, index=True)
    workforce_id = db.Column(db.String(120), nullable=False, index=True)
    objective = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(40), nullable=False, default="assigned", index=True)
    idempotency_key = db.Column(db.String(255), nullable=False, index=True)
    permission_snapshot_json = db.Column(db.Text, nullable=False, default="{}")
    delegation_parent_id = db.Column(db.Integer, nullable=True, index=True)
    plan_json = db.Column(db.Text, nullable=True)
    plan_hash = db.Column(db.String(128), nullable=True, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (db.Index("uq_workforce_assignment_idempotency", "organization_id", "idempotency_key", unique=True),)


class WorkforceTask(db.Model):
    __tablename__ = "workforce_tasks"

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False, index=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey("workforce_assignments.id"), nullable=False, index=True)
    workforce_id = db.Column(db.String(120), nullable=False, index=True)
    action = db.Column(db.String(255), nullable=False)
    state = db.Column(db.String(40), nullable=False, default="assigned", index=True)
    idempotency_key = db.Column(db.String(255), nullable=False, index=True)
    execution_key = db.Column(db.String(255), nullable=True, index=True)
    attempt = db.Column(db.Integer, nullable=False, default=0)
    permission_snapshot_json = db.Column(db.Text, nullable=False, default="{}")
    input_json = db.Column(db.Text, nullable=False, default="{}")
    result_json = db.Column(db.Text, nullable=True)
    evidence_digest = db.Column(db.String(128), nullable=True)
    last_error = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    __table_args__ = (db.Index("uq_workforce_task_idempotency", "organization_id", "idempotency_key", unique=True),)


class WorkforceTaskEvent(db.Model):
    __tablename__ = "workforce_task_events"

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False, index=True)
    task_id = db.Column(db.Integer, db.ForeignKey("workforce_tasks.id"), nullable=False, index=True)
    from_state = db.Column(db.String(40), nullable=True)
    to_state = db.Column(db.String(40), nullable=False, index=True)
    actor = db.Column(db.String(255), nullable=False)
    reason = db.Column(db.String(500), nullable=True)
    metadata_json = db.Column(db.Text, nullable=False, default="{}")
    metadata_digest = db.Column(db.String(64), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)


class WorkforceSchedule(db.Model):
    __tablename__ = "workforce_schedules"

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False, index=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey("workforce_assignments.id"), nullable=False, index=True)
    schedule_key = db.Column(db.String(255), nullable=False, index=True)
    schedule_json = db.Column(db.Text, nullable=False, default="{}")
    status = db.Column(db.String(30), nullable=False, default="active", index=True)
    next_run_at = db.Column(db.DateTime, nullable=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (db.Index("uq_workforce_schedule_key", "organization_id", "schedule_key", unique=True),)

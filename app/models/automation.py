from datetime import datetime

from app import db


class AutomationWorkflow(db.Model):
    __tablename__ = "automation_workflows"

    id = db.Column(db.Integer, primary_key=True)

    organization_id = db.Column(
        db.Integer,
        db.ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )

    name = db.Column(db.String(200), nullable=False)

    description = db.Column(db.Text, nullable=True)

    trigger_type = db.Column(
        db.String(50),
        nullable=False,
        default="ticket_created",
    )

    is_active = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    actions = db.relationship(
        "AutomationAction",
        backref="workflow",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="AutomationAction.position",
    )

    executions = db.relationship(
        "AutomationExecution",
        backref="workflow",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="AutomationExecution.created_at.desc()",
    )

    def __repr__(self):
        return f"<AutomationWorkflow {self.id} {self.name}>"


class AutomationAction(db.Model):
    __tablename__ = "automation_actions"

    id = db.Column(db.Integer, primary_key=True)

    workflow_id = db.Column(
        db.Integer,
        db.ForeignKey("automation_workflows.id"),
        nullable=False,
        index=True,
    )

    position = db.Column(
        db.Integer,
        nullable=False,
        default=1,
    )

    action_type = db.Column(
        db.String(50),
        nullable=False,
    )

    config_json = db.Column(
        db.Text,
        nullable=True,
    )

    is_active = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    def __repr__(self):
        return f"<AutomationAction {self.id} {self.action_type}>"


class AutomationExecution(db.Model):
    __tablename__ = "automation_executions"

    id = db.Column(db.Integer, primary_key=True)

    workflow_id = db.Column(
        db.Integer,
        db.ForeignKey("automation_workflows.id"),
        nullable=False,
        index=True,
    )

    trigger_type = db.Column(
        db.String(50),
        nullable=False,
    )

    status = db.Column(
        db.String(30),
        nullable=False,
        default="running",
    )

    input_json = db.Column(
        db.Text,
        nullable=True,
    )

    output_json = db.Column(
        db.Text,
        nullable=True,
    )

    error_message = db.Column(
        db.Text,
        nullable=True,
    )

    started_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    completed_at = db.Column(
        db.DateTime,
        nullable=True,
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    def __repr__(self):
        return f"<AutomationExecution {self.id} {self.status}>"

class AutomationApproval(db.Model):
    __tablename__ = "automation_approvals"

    id = db.Column(db.Integer, primary_key=True)

    organization_id = db.Column(
        db.Integer,
        db.ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )

    workflow_id = db.Column(
        db.Integer,
        db.ForeignKey("automation_workflows.id"),
        nullable=True,
        index=True,
    )

    execution_id = db.Column(
        db.Integer,
        db.ForeignKey("automation_executions.id"),
        nullable=True,
        index=True,
    )

    action_type = db.Column(
        db.String(100),
        nullable=False,
    )

    status = db.Column(
        db.String(30),
        nullable=False,
        default="pending",
        index=True,
    )

    reason = db.Column(
        db.Text,
        nullable=True,
    )

    request_json = db.Column(
        db.Text,
        nullable=True,
    )

    decision_json = db.Column(
        db.Text,
        nullable=True,
    )

    requested_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True,
    )

    decided_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True,
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    decided_at = db.Column(
        db.DateTime,
        nullable=True,
    )

    def __repr__(self):
        return f"<AutomationApproval {self.id} {self.status}>"

from app import create_app, db
from app.models.organization import Organization
from app.models.user import User
from app.models.chat import ChatMessage
from werkzeug.security import generate_password_hash


def _app_with_users():
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    return app


def _login(client, user_id):
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True


def test_non_admin_cannot_cross_privilege_boundary():
    app = _app_with_users()
    with app.app_context():
        db.create_all()
        org = Organization(name="Privilege Org", slug="privilege-org")
        db.session.add(org); db.session.flush()
        user = User(organization_id=org.id, full_name="User", email="priv-user@example.com", password_hash=generate_password_hash("password"), role="user")
        db.session.add(user); db.session.commit()
        client = app.test_client(); _login(client, user.id)
        assert client.get("/admin/users").status_code == 403
        assert client.post(f"/admin/users/toggle/{user.id}").status_code == 403


def test_admin_cannot_manage_users_outside_own_organization():
    app = _app_with_users()
    with app.app_context():
        db.create_all()
        org_a = Organization(name="Org A", slug="org-a"); org_b = Organization(name="Org B", slug="org-b")
        db.session.add_all([org_a, org_b]); db.session.flush()
        admin = User(organization_id=org_a.id, full_name="Admin", email="admin-a@example.com", password_hash=generate_password_hash("password"), role="admin")
        foreign = User(organization_id=org_b.id, full_name="Foreign", email="foreign-b@example.com", password_hash=generate_password_hash("password"), role="user")
        db.session.add_all([admin, foreign]); db.session.commit()
        client = app.test_client(); _login(client, admin.id)
        assert client.post(f"/admin/users/toggle/{foreign.id}").status_code == 404
        assert db.session.get(User, foreign.id).role == "user"


def test_admin_cannot_self_demote():
    app = _app_with_users()
    with app.app_context():
        db.create_all()
        org = Organization(name="Self Org", slug="self-org")
        db.session.add(org); db.session.flush()
        admin = User(organization_id=org.id, full_name="Admin", email="self-admin@example.com", password_hash=generate_password_hash("password"), role="admin")
        db.session.add(admin); db.session.commit()
        client = app.test_client(); _login(client, admin.id)
        assert client.post(f"/admin/users/toggle/{admin.id}").status_code in (302, 303)
        assert db.session.get(User, admin.id).role == "admin"


def test_admin_cannot_remove_last_admin_in_organization():
    app = _app_with_users()
    with app.app_context():
        db.create_all()
        org = Organization(name="Last Admin Org", slug="last-admin-org")
        db.session.add(org); db.session.flush()
        admin = User(organization_id=org.id, full_name="Admin", email="last-admin@example.com", password_hash=generate_password_hash("password"), role="admin")
        other = User(organization_id=org.id, full_name="Other", email="other-admin@example.com", password_hash=generate_password_hash("password"), role="admin")
        db.session.add_all([admin, other]); db.session.commit()
        client = app.test_client(); _login(client, admin.id)
        assert client.post(f"/admin/users/toggle/{other.id}").status_code == 302
        assert db.session.get(User, other.id).role == "user"
        assert client.post(f"/admin/users/toggle/{admin.id}").status_code == 302
        assert db.session.get(User, admin.id).role == "admin"


def test_admin_delete_is_organization_scoped_and_protects_last_admin():
    app = _app_with_users()
    with app.app_context():
        db.create_all()
        org_a = Organization(name="Delete A", slug="delete-a"); org_b = Organization(name="Delete B", slug="delete-b")
        db.session.add_all([org_a, org_b]); db.session.flush()
        admin = User(organization_id=org_a.id, full_name="Admin", email="delete-admin@example.com", password_hash=generate_password_hash("password"), role="admin")
        foreign = User(organization_id=org_b.id, full_name="Foreign", email="delete-foreign@example.com", password_hash=generate_password_hash("password"), role="user")
        db.session.add_all([admin, foreign]); db.session.commit()
        client = app.test_client(); _login(client, admin.id)
        assert client.post(f"/admin/users/delete/{foreign.id}").status_code == 404
        assert db.session.get(User, foreign.id) is not None
        assert client.post(f"/admin/users/delete/{admin.id}").status_code == 302
        assert db.session.get(User, admin.id) is not None


def test_admin_dashboard_is_organization_scoped():
    app = _app_with_users()
    with app.app_context():
        db.create_all()
        org_a = Organization(name="Dashboard A", slug="dashboard-a")
        org_b = Organization(name="Dashboard B", slug="dashboard-b")
        db.session.add_all([org_a, org_b]); db.session.flush()
        admin = User(organization_id=org_a.id, full_name="Admin A", email="admin-dashboard-a@example.com", password_hash=generate_password_hash("password"), role="admin")
        foreign = User(organization_id=org_b.id, full_name="Foreign B", email="foreign-dashboard-b@example.com", password_hash=generate_password_hash("password"), role="admin")
        db.session.add_all([admin, foreign]); db.session.flush()
        db.session.add_all([
            ChatMessage(user_id=admin.id, question="A question", answer="A answer"),
            ChatMessage(user_id=foreign.id, question="B question", answer="B answer"),
        ])
        db.session.commit()
        client = app.test_client(); _login(client, admin.id)
        response = client.get("/admin/")
        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert "admin-dashboard-a@example.com" in body
        assert "foreign-dashboard-b@example.com" not in body
        assert "B question" not in body


def test_non_admin_cannot_access_leads_or_automation_admin_routes():
    app = _app_with_users()
    with app.app_context():
        db.create_all()
        org = Organization(name="Admin Routes Org", slug="admin-routes-org")
        db.session.add(org); db.session.flush()
        user = User(organization_id=org.id, full_name="User", email="admin-routes-user@example.com", password_hash=generate_password_hash("password"), role="user")
        db.session.add(user); db.session.commit()
        client = app.test_client(); _login(client, user.id)
        assert client.get("/admin/leads").status_code == 403
        assert client.get("/admin/automation/approvals").status_code == 403

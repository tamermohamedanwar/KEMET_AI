import os


def test_security_baseline_document_exists():
    path = os.path.join("docs", "KEMET_SECURITY_BASELINE.md")
    assert os.path.exists(path)


def test_security_baseline_names_core_controls():
    text = open("docs/KEMET_SECURITY_BASELINE.md", encoding="utf-8").read()
    for marker in (
        "Human approval",
        "Tenant and identity binding",
        "One-time execution authorization",
        "Execution envelope",
        "post-validation, and rollback",
        "Rate limiting",
    ):
        assert marker in text


def test_security_headers_are_present_in_test_app():
    from app import create_app

    app = create_app()
    client = app.test_client()
    response = client.get("/login")
    assert response.status_code in (200, 302)
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "camera=()" in response.headers["Permissions-Policy"]
    assert response.headers["Cross-Origin-Opener-Policy"] == "same-origin"
    assert response.headers["Cross-Origin-Resource-Policy"] == "same-origin"
    assert response.headers["X-Permitted-Cross-Domain-Policies"] == "none"
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]

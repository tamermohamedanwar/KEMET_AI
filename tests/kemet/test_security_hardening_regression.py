from pathlib import Path


def test_production_debug_is_disabled():
    from app.config.production import DEBUG
    assert DEBUG is False


def test_app_entrypoint_has_production_debug_fail_safe():
    source = Path("app.py").read_text()
    assert "debug=True" not in source
    assert 'debug = bool(app.config.get("DEBUG", False)) and not production' in source
    assert 'FLASK_ENV' in source
    assert 'KEMET_PRODUCTION' in source


def test_real_environment_files_are_not_present():
    forbidden = {".env", ".env.local", ".env.agent"}
    found = []
    for path in Path(".").rglob("*"):
        if path.is_file() and ".git" not in path.parts and path.name in forbidden:
            found.append(str(path))
    assert found == []


def test_env_example_contains_placeholders_only():
    text = Path(".env.example").read_text()
    assert "replace_with_" in text
    assert "sk-" not in text
    assert "Bearer " not in text
    assert "DATABASE_URL=replace_with_url" in text


def test_test_password_is_not_hardcoded():
    source = Path("ops/capacity_authenticated_matrix.py").read_text()
    assert "Capacity-Synthetic-2026!" not in source
    assert "KEMET_CAPACITY_TEST_PASSWORD" in source


def test_test_dependencies_are_declared():
    text = Path("requirements-dev.txt").read_text()
    assert "-r requirements.txt" in text
    assert "pytest==" in text
    assert "pytest-cov==" in text
    assert "coverage==" in text

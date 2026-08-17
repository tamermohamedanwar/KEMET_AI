from app import create_app


def test_app_creation():
    app = create_app()
    assert app is not None


def test_testing_config():
    app = create_app()
    assert app.config is not None

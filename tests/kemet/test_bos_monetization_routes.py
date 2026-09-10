def test_bos_routes_module_imports():
    from app.routes.bos_command import bos_command_bp

    assert bos_command_bp.name == "bos_command"
    assert bos_command_bp.url_prefix == "/api/bos"

from pathlib import Path


def test_command_center_exposes_unified_social_connections_routes():
    route = Path("app/routes/command_center.py").read_text()
    assert '/api/bos/social-connections' in route
    assert 'social_connection_hub.snapshot' in route
    assert 'social_connection_hub.authorize' in route

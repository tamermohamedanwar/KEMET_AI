from pathlib import Path


ROUTE = Path("app/routes/command_center.py").read_text(encoding="utf-8")
TEMPLATE = Path("app/templates/admin/command_center.html").read_text(encoding="utf-8")


def test_command_center_exposes_social_readiness_endpoint():
    assert "social_channel_readiness_service" in ROUTE
    assert "/api/bos/social-readiness" in ROUTE


def test_command_center_ui_has_unified_social_control():
    assert "socialReadiness" in TEMPLATE
    assert "جاهزية القنوات" in TEMPLATE
    assert "youtube" in TEMPLATE.lower()
    assert "tiktok" in TEMPLATE.lower()
    assert "instagram" in TEMPLATE.lower()
    assert "facebook" in TEMPLATE.lower()
    assert "telegram" in TEMPLATE.lower()
    assert "whatsapp" in TEMPLATE.lower()

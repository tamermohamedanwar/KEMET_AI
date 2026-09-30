from pathlib import Path


def test_global_security_roadmap_is_present_and_actionable():
    text = Path("docs/KEMET_GLOBAL_SECURITY_ROADMAP.md").read_text(encoding="utf-8")
    markers = (
        "Authentication hardening",
        "Authorization policy engine",
        "Secret boundary",
        "SSRF and egress policy",
        "Supply-chain controls",
        "Continuous assurance",
    )
    assert all(marker in text for marker in markers)

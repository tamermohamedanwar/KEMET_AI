from pathlib import Path


def test_trust_architecture_is_active():
    path = Path("docs/KEMET_TRUST_ARCHITECTURE.md")
    text = path.read_text(encoding="utf-8")
    required = (
        "ASK -> PLAN -> SIMULATE -> APPROVE -> EXECUTE -> VERIFY",
        "Capability admission",
        "Attack resistance",
        "Response UX",
        "Kemet is the control plane",
    )
    assert all(marker in text for marker in required)

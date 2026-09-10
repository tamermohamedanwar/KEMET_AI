from app.core.globalization import (
    GlobalizationEngine,
    GlobalProfile,
    IntegrationDefinition,
)


def build_engine():
    return GlobalizationEngine(
        [
            IntegrationDefinition(
                integration_id="messaging.whatsapp",
                name="WhatsApp",
                category="messaging",
                capabilities=("messaging", "omnichannel"),
                requires_approval=True,
            ),
            IntegrationDefinition(
                integration_id="payments.generic",
                name="Payment Gateway",
                category="payments",
                capabilities=("payments", "billing"),
                requires_approval=True,
            ),
        ]
    )


def test_global_profile_validation():
    engine = build_engine()

    profile = GlobalProfile(
        locale="ar-EG",
        currency="EGP",
        industry="ecommerce",
        timezone="Africa/Cairo",
    )

    result = engine.validate_profile(profile)

    assert result["ok"] is True
    assert result["errors"] == []


def test_global_profile_rejects_invalid_values():
    engine = build_engine()

    profile = GlobalProfile(
        locale="xx-XX",
        currency="XXX",
        industry="unknown",
        timezone="",
    )

    result = engine.validate_profile(profile)

    assert result["ok"] is False
    assert len(result["errors"]) == 4


def test_integration_governance():
    engine = build_engine()

    plan = engine.build_integration_plan(
        "messaging.whatsapp"
    )

    assert plan["ok"] is True
    assert plan["status"] == "waiting_approval"
    assert plan["requires_approval"] is True
    assert plan["external_execution"] is False
    assert plan["database_mutation"] is False

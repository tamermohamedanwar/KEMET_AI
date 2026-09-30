from app.services.content_experiment_production_service import content_experiment_production_service
from app.services.content_experiment_service import content_experiment_service
from app.services.mendes.mendes_pilot_episode_service import mendes_pilot_episode_service


def test_production_brief_binds_experiment_and_pilot():
    experiment = content_experiment_service.build(
        organization_id=1, content_id="mendes-001",
        title="الخاتم الأزرق", audience="Egyptian short-form viewers",
        hook="إيه اللي حصل لما الخاتم لمس إيد يونس؟",
        story="يونس يجد خاتمًا غامضًا ويكتشف علامة مخفية.",
        cta="كمل القصة على تيليجرام.",
    )
    pilot = mendes_pilot_episode_service.build(1)["package"]
    brief = content_experiment_production_service.build_brief(
        experiment=experiment, pilot_package=pilot
    )
    assert brief["organization_id"] == 1
    assert brief["experiment_digest"] == experiment["experiment_digest"]
    assert brief["pilot_package_digest"] == pilot["package_digest"]
    assert len(brief["production_brief"]["scenes"]) == 6
    assert brief["execution"]["auto_publish"] is False
    assert brief["gates"]["human_approval"] == "PENDING"
    assert len(brief["production_digest"]) == 64


def test_production_brief_rejects_cross_tenant_binding():
    experiment = content_experiment_service.build(
        organization_id=1, content_id="mendes-001", title="Mendes",
        audience="viewers", hook="hook", story="story", cta="cta",
    )
    pilot = mendes_pilot_episode_service.build(2)["package"]
    try:
        content_experiment_production_service.build_brief(
            experiment=experiment, pilot_package=pilot
        )
    except ValueError as exc:
        assert str(exc) == "tenant_mismatch"
    else:
        raise AssertionError("cross-tenant production binding accepted")

from app.services.audience_intelligence_service import audience_intelligence_service
from app.services.content_experiment_service import content_experiment_service
from app.services.telegram_audience_service import telegram_audience_service


def test_audience_hypothesis_is_not_demand_claim():
    record = audience_intelligence_service.build_hypothesis(
        organization_id=1, audience="Egyptian story viewers", topic="Mendes mystery"
    )
    assert record["evidence_status"] == "unmeasured"
    assert record["rule"] == "hypothesis_is_not_observed_demand"
    assert record["governance"]["execution_authority"] is False
    assert len(record["hypothesis_digest"]) == 64


def test_audience_observation_requires_bounded_signals():
    hypothesis = audience_intelligence_service.build_hypothesis(
        organization_id=1, audience="Egyptian story viewers", topic="Mendes mystery"
    )
    observed = audience_intelligence_service.score_content_experiment(
        hypothesis=hypothesis, observations={"retention": 61, "hook_strength": 72}
    )
    assert observed["status"] == "observed"
    assert observed["causal_claim"] is False


def test_content_experiment_builds_reviewable_contract():
    experiment = content_experiment_service.build(
        organization_id=1, content_id="mendes-001", title="Mendes: The Hidden Door",
        audience="Egyptian short-form viewers", hook="What if the door was never meant to open?",
        story="A short mystery with a verified historical frame.",
        cta="Continue the story on Telegram.",
    )
    assert experiment["state"] == "READY_FOR_REVIEW"
    assert experiment["approval"]["required"] is True
    assert experiment["execution"]["auto_publish"] is False
    assert len(experiment["experiment_digest"]) == 64


def test_content_experiment_observation_is_noncausal():
    experiment = content_experiment_service.build(
        organization_id=1, content_id="mendes-001", title="Mendes",
        audience="Egyptian viewers", hook="Question", story="Story", cta="Continue",
    )
    observed = content_experiment_service.observe(
        experiment=experiment,
        observations={"retention_rate": 48, "shares": 10, "qualified_views": 100,
                      "telegram_join_intent": 3, "revenue": 25},
    )
    assert observed["status"] == "OBSERVED"
    assert observed["revenue_authoritative"] is True
    assert observed["causal_claim"] is False


def test_telegram_funnel_is_owned_audience_not_executor():
    funnel = telegram_audience_service.build_funnel(
        organization_id=1, channel_ref="@kemet_stories", bot_ref="@kemet_bot",
        content_id="mendes-001",
    )
    assert funnel["audience_ownership"] is True
    assert funnel["payment"]["provider"] == "telegram_stars"
    assert funnel["payment"]["execution_ready"] is False
    assert funnel["execution_authority"] is False
    assert funnel["flow"][0] == "DISCOVER"


def test_telegram_cta_is_attributable():
    cta = telegram_audience_service.build_cta(experiment_id="ce_123")
    assert cta["destination"] == "telegram"
    assert cta["tracking"]["attribution_required"] is True
    assert cta["external_execution"] is False

def test_content_factory_exposes_experiment_and_telegram_funnel():
    from app.services.content_factory_service import content_factory_service

    package = content_factory_service.build(
        organization_id=1, title="Mendes Pilot", premise="A short governed story.",
        audience="Egyptian short-form viewers", platforms=["youtube", "tiktok"],
        beats={"hook": "What happened behind the door?"},
    )
    assert package["status"] == "review_required"
    assert package["content_experiment"]["approval"]["required"] is True
    assert package["telegram_audience"]["audience_ownership"] is True
    assert package["telegram_audience"]["payment"]["execution_ready"] is False

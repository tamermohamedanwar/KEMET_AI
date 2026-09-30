from app.services.mendes.hikayat_mendes_story_engine import hikayat_mendes_story_engine
from app.services.media_production_pipeline import media_production_pipeline


def test_mendes_universe_is_advisory_and_historical_boundaries_are_explicit():
    result = hikayat_mendes_story_engine.build_universe(organization_id=1)
    assert result["title"] == "Hikayat Mendes"
    assert result["canon"]["historical_truth"] == "documented"
    assert result["governance"]["execution_authority"] is False


def test_episode_preserves_characters_continuity_and_era_type():
    result = hikayat_mendes_story_engine.plan_episode(
        organization_id=1, season_number=1, episode_number=1,
        title="The Door", premise="A child discovers a hidden door in Mendes.",
        era_label="Ancient Mendes", era_type="inspired",
        characters=[{"character_id": "hor", "name": "Hor", "role": "young resident", "traits": ["curious"]}],
        continuity_events=["The hidden door has not been opened."], cliffhanger="The door moves by itself.",
    )
    assert result["status"] == "planned"
    assert result["episode"]["characters"][0]["character_id"] == "hor"
    assert result["continuity_check_required"] is True
    assert result["historical_label_required"] is True


def test_media_pipeline_is_a_plan_not_an_executor():
    episode = {"title": "The Door"}
    result = media_production_pipeline.build_plan(organization_id=1, episode=episode, duration_seconds=90)
    assert [stage["stage"] for stage in result["stages"]][:8] == [
        "script", "scenes", "images", "animation", "voice", "music", "sound_effects", "edit"
    ]
    shortform_stages = [stage for stage in result["stages"] if stage["stage"] == "shortform"]
    assert len(shortform_stages) == 1
    assert shortform_stages[0]["status"] == "optional"
    assert result["external_generation"]["execution_authority"] is False
    assert result["quality_gates"]["rights"] == "required"


def test_scene_plan_rejects_empty_scenes():
    try:
        media_production_pipeline.scene_plan(episode={"title": "x"}, scenes=[])
    except ValueError as exc:
        assert str(exc) == "scenes_required"
    else:
        raise AssertionError("empty scene plan was accepted")

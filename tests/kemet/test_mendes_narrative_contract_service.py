import pytest

from app.services.mendes.mendes_narrative_contract_service import mendes_narrative_contract_service


def _character():
    return {"character_id": "hor", "version": 2, "digest": "c" * 64}


def _season():
    return {"season_id": "season-1", "version": 1, "digest": "s" * 64}


def _episode():
    return {
        "story_id": "story-1", "episode_id": "s1e1", "version": 1,
        "digest": "e" * 64, "title": "The Blue Door", "characters": [_character()],
        "locations": ["Mendes Gate"], "continuity_dependencies": ["door remains closed"],
        "evidence": [],
    }


def test_character_references_are_exact_and_versioned():
    result = mendes_narrative_contract_service.build_story_episode(
        organization_id=7, world_id="mendes", season=_season(), story_id="story-1",
        episode_id="s1e1", version=1, title="The Blue Door",
        fields={"premise": "A fictional discovery.", "characters": [_character()]},
    )
    assert result["characters"] == [{"id": "hor", "version": 2, "digest": "c" * 64}]
    assert result["season_version"] == 1
    assert result["season_digest"] == "s" * 64
    assert len(result["digest"]) == 64


def test_script_requires_exact_episode_binding():
    with pytest.raises(ValueError, match="episode_exact_binding_required"):
        mendes_narrative_contract_service.build_script(
            organization_id=7, episode={"episode_id": "s1e1", "title": "x"},
            version=1, scenes=[], dialogue=[], narration=[], timing={},
        )


def test_script_scene_storyboard_chain_preserves_exact_digests():
    episode = _episode()
    script = mendes_narrative_contract_service.build_script(
        organization_id=7, episode=episode, version=1,
        scenes=[{"scene_id": "s1e1-sc1", "version": 1, "digest": "sc" * 32}],
        dialogue=[{"character_id": "hor", "text": "Who is there?"}],
        narration=["A quiet gate stands at dusk."],
        timing={"classification": "fictional", "action": ["approach"],
                "visual_direction": {"camera": "wide"}},
    )
    breakdown = mendes_narrative_contract_service.build_scene_breakdown(
        organization_id=7, script=script, version=1,
        scenes=[{"scene_id": "s1e1-sc1", "location": "Mendes Gate", "characters": [_character()]}],
    )
    storyboard = mendes_narrative_contract_service.build_storyboard(
        organization_id=7, scene_breakdown=breakdown, version=1,
        shots=[{"scene_id": "s1e1-sc1", "framing": "wide", "duration": 4}],
    )
    assert breakdown["script_digest"] == script["digest"]
    assert storyboard["scene_breakdown_digest"] == breakdown["digest"]
    assert storyboard["shots"][0]["shot_id"] == "s1e1-sh1"


def test_continuity_returns_machine_readable_block_on_digest_mismatch():
    report = mendes_narrative_contract_service.validate_continuity(
        character_versions=[_character()],
        script={"digest": "a" * 64},
        scene_breakdown={"script_digest": "b" * 64, "digest": "c" * 64},
        storyboard={"scene_breakdown_digest": "d" * 64, "shots": [{"scene_id": "s1e1-sc1"}]},
    )
    assert report["status"] == "BLOCKED"
    assert {item["code"] for item in report["findings"]} == {
        "SCRIPT_DIGEST_MISMATCH", "SCENE_BREAKDOWN_DIGEST_MISMATCH"
    }
    assert report["machine_readable"] is True

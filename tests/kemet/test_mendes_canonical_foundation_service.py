from app.services.mendes.mendes_canonical_foundation_service import (
    mendes_canonical_foundation_service,
)


def test_world_bible_is_versioned_tenant_scoped_and_digest_bound():
    result = mendes_canonical_foundation_service.build_world_bible(
        organization_id=1,
        world_id="mendes-world",
        version=1,
        title="Mendes World",
        fields={"rules": ["canon requires evidence"], "language": "ar-EG"},
    )
    assert result["schema"] == "kemet.mendes.world_bible.v1"
    assert result["organization_id"] == 1
    assert result["version"] == 1
    assert len(result["digest"]) == 64
    assert result["rights"]["status"] == "UNKNOWN"


def test_character_bible_is_bound_to_world_and_preserves_canonical_identity():
    result = mendes_canonical_foundation_service.build_character_bible(
        organization_id=1,
        world_id="mendes-world",
        character_id="hor",
        version=3,
        name="Hor",
        fields={"canonical_facts": ["resident of Mendes"], "visual_bible": {"age": "young"}},
    )
    assert result["schema"] == "kemet.mendes.character_bible.v1"
    assert result["world_id"] == "mendes-world"
    assert result["character_id"] == "hor"
    assert result["version"] == 3
    assert result["canonical_facts"] == ["resident of Mendes"]
    assert len(result["digest"]) == 64


def test_canonical_foundation_rejects_invalid_rights_and_version():
    try:
        mendes_canonical_foundation_service.build_world_bible(
            organization_id=1, world_id="mendes-world", version=0, title="Mendes"
        )
    except ValueError as exc:
        assert str(exc) == "invalid_version"
    else:
        raise AssertionError("invalid version was accepted")

    try:
        mendes_canonical_foundation_service.build_character_bible(
            organization_id=1, world_id="mendes-world", character_id="hor",
            version=1, name="Hor", fields={"rights": {"status": "FAKE"}},
        )
    except ValueError as exc:
        assert str(exc) == "invalid_rights_status"
    else:
        raise AssertionError("invalid rights status was accepted")


def test_canonical_digest_is_deterministic():
    first = mendes_canonical_foundation_service.build_world_bible(
        organization_id=1, world_id="mendes-world", version=1, title="Mendes",
        fields={"history": ["origin"], "rules": ["continuity"]},
    )
    second = mendes_canonical_foundation_service.build_world_bible(
        organization_id=1, world_id="mendes-world", version=1, title="Mendes",
        fields={"history": ["origin"], "rules": ["continuity"]},
    )
    assert first["digest"] == second["digest"]

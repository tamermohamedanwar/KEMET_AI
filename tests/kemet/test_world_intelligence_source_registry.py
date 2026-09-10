from app.services.world_intelligence_source_registry import (
    WorldIntelligenceSourceRegistry,
)


def test_known_source_profile_is_enriched():
    registry = WorldIntelligenceSourceRegistry()
    item = {"source": "github", "url": "https://github.com/example", "title": "X"}
    result = registry.enrich([item])[0]
    assert result["source_key"] == "github"
    assert result["source_trust"] == 0.95
    assert result["source_tier"] == "primary"


def test_unknown_source_fails_closed_to_low_trust():
    registry = WorldIntelligenceSourceRegistry()
    result = registry.enrich([{"source": "random-blog", "url": "https://x.test", "title": "X"}])[0]
    assert result["source_tier"] == "unverified"
    assert result["source_trust"] < 0.5


def test_host_can_resolve_a_known_profile():
    registry = WorldIntelligenceSourceRegistry()
    result = registry.enrich([{"source": "", "url": "https://github.com/a", "title": "X"}])[0]
    assert result["source_tier"] == "primary"


def test_source_profile_is_immutable():
    registry = WorldIntelligenceSourceRegistry()
    profile = registry.profile({"source": "github", "url": "https://github.com/a"})
    assert profile.name == "github"
    assert profile.trust == 0.95


def test_unknown_source_is_low_trust():
    from app.services.world_intelligence_source_registry import world_intelligence_source_registry

    result = world_intelligence_source_registry.enrich([
        {"source": "Unknown source", "url": "https://unknown.example/item"}
    ])
    assert result[0]["source_trust"] == 0.4
    assert result[0]["source_tier"] == "unverified"

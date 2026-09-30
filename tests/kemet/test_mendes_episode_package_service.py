import pytest

from app.services.mendes.mendes_episode_package_service import mendes_episode_package_service


def test_episode_package_is_tenant_scoped_and_non_executing(monkeypatch):
    monkeypatch.setattr(
        "app.services.mendes.mendes_episode_package_service.evidence_backed_context_service.build",
        lambda **kwargs: {
            "sources": [{"content_digest": "source-1", "usable_for_governance": True}],
            "retrieval": {"prompt_injection_signals": 0},
        },
    )
    result = mendes_episode_package_service.build_package(
        organization_id=7,
        episode={"episode_id": "s1e1", "title": "The First Mystery", "premise": "A discovery changes everything."},
        observed={"metrics": {"retention_rate": 60, "views": 1000, "shares": 70, "qualified_views": 700, "revenue": 0}},
        research_query="documented history of Mendes",
        task_id="task-1",
        season_number=1,
        episode_number=2,
        era_label="documented historical era",
        era_type="documented",
    )
    assert result["success"] is True
    assert result["organization_id"] == 7
    assert result["source_ids"] == ["source-1"]
    assert result["governance"]["execution_authority"] is False
    assert result["approval_status"] == "not_requested"
    assert len(result["package_digest"]) == 64


def test_episode_package_blocks_prompt_injection_from_research(monkeypatch):
    monkeypatch.setattr(
        "app.services.mendes.mendes_episode_package_service.evidence_backed_context_service.build",
        lambda **kwargs: {
            "sources": [],
            "retrieval": {"prompt_injection_signals": 1},
        },
    )
    result = mendes_episode_package_service.build_package(
        organization_id=7,
        episode={"episode_id": "s1e1", "title": "The First Mystery"},
        observed={"views": 100, "shares": 2, "retention_rate": 40, "qualified_views": 30, "revenue": 0},
        research_query="history",
        task_id="task-2",
        season_number=1,
        episode_number=2,
        era_label="documented",
        era_type="documented",
    )
    assert result["status"] == "blocked"
    assert result["error"] == "untrusted_research_content_detected"
    assert result["execution_authority"] is False


def test_episode_package_requires_research_query():
    with pytest.raises(ValueError, match="research_query_required"):
        mendes_episode_package_service.build_package(
            organization_id=7,
            episode={"title": "Episode"},
            observed={"views": 1},
            research_query="",
            task_id="task-3",
            season_number=1,
            episode_number=2,
            era_label="documented",
            era_type="documented",
        )

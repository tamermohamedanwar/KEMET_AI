from app.core.orchestration import KemetCore


def test_core_status():
    core = KemetCore()
    result = core.status()

    assert result["ok"] is True
    assert result["layer_count"] == 10
    assert result["mode"] == "advisory"
    assert result["external_execution"] is False
    assert result["database_mutation"] is False


def test_core_decision_flow():
    core = KemetCore()

    result = core.run(
        business={"name": "Demo"},
        revenue={"pipeline": 100000},
        signals=[
            {
                "focus": "Convert pipeline into revenue",
                "priority": 90,
                "confidence": 0.95,
            },
            {
                "focus": "Improve customer retention",
                "priority": 70,
                "confidence": 0.90,
            },
        ],
    )

    assert result["ok"] is True
    assert result["decision"]["focus"] == "Convert pipeline into revenue"
    assert result["decision"]["requires_approval"] is True
    assert result["status"] == "waiting_approval"


def test_core_governance():
    core = KemetCore()

    result = core.run(
        signals=[
            {
                "focus": "Review operations",
                "priority": 50,
                "confidence": 0.80,
            }
        ]
    )

    assert result["external_execution"] is False
    assert result["database_mutation"] is False
    assert result["plan"]["requires_approval"] is True

from app.core.runtime.resource_guard import choose_model, decide


def test_choose_tiny_when_memory_is_low():
    assert choose_model("auto", 600) == "tiny"


def test_choose_base_when_memory_allows_it():
    assert choose_model("auto", 700) == "base"


def test_rejects_insufficient_memory():
    decision = decide("base", 500)
    assert not decision.allowed
    assert decision.reason == "insufficient_memory"


def test_accepts_base_with_headroom():
    decision = decide("base", 700)
    assert decision.allowed

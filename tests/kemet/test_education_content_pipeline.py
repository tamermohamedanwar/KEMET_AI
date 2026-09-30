from app.services.education_content_pipeline import education_content_pipeline


def test_education_pipeline_turns_problem_into_multimedia_plan():
    result = education_content_pipeline.build_plan(
        organization_id=1, problem="Explain Newton's second law with an example.", subject="physics",
        learner_level="secondary", include_video=True,
    )
    assert result["flow"] == ["problem", "understanding", "explanation", "visual_story", "educational_video"]
    assert result["outputs"]["simple_explanation"] is True
    assert result["outputs"]["diagrams"] is True
    assert result["governance"]["auto_publish"] is False


def test_education_pipeline_rejects_empty_problem():
    try:
        education_content_pipeline.build_plan(organization_id=1, problem="", subject="math")
    except ValueError as exc:
        assert str(exc) == "problem_required"
    else:
        raise AssertionError("empty problem was accepted")


def test_education_pipeline_is_practice_first():
    result = education_content_pipeline.build_plan(
        organization_id=1, problem="Build a real sales follow-up workflow.", subject="sales",
        learner_level="professional", include_video=False,
    )
    practice = result["practice"]
    assert practice["mode"] == "learn_by_doing"
    assert practice["steps"] == ["understand", "attempt", "feedback", "retry", "verify"]
    assert practice["real_task"] is True
    assert practice["answer_first"] is False
    assert result["governance"]["external_execution"] is False
    assert result["tool_intelligence"]["selection_policy"]["verified_provenance_required"] is True
    assert result["tool_intelligence"]["recommendations"]


def test_practice_loop_has_bounded_attempts_and_stall_path():
    result = education_content_pipeline.build_plan(
        organization_id=1, problem="Debug a failing API request.", subject="api", include_video=False,
    )
    guard = result["practice"]["loop_guard"]
    assert guard["max_attempts"] == 3
    assert guard["requires_progress"] is True
    assert guard["on_stall"] == "escalate_to_coach"
    assert guard["on_success"] == "record_skill_signal"

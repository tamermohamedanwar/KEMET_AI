from app.services.ai_usage_service import current_month


def test_current_month_returns_year_month():
    value = current_month()
    assert len(value) == 7
    assert value[4] == "-"

from app.core.content_distribution_strategy import strategy_snapshot


def test_telegram_is_primary_and_website_is_deferred():
    snap = strategy_snapshot()
    assert snap["primary_distribution"] == "telegram"
    assert snap["website"]["state"] == "deferred_until_revenue_evidence"
    assert snap["website"]["domain_required"] is False
    assert snap["canonical_runtime_only"] is True
    assert snap["mcp"] is False


def test_social_channels_remain_secondary_distribution():
    snap = strategy_snapshot()
    assert snap["secondary_distribution"] == ["youtube", "tiktok", "instagram", "facebook"]
    assert snap["approval_required"] is True


def test_mobile_profile_targets_five_minutes_and_workstation_expands_long_form():
    snap = strategy_snapshot()
    assert snap["current_profile"] == "mobile_now"
    assert snap["production_profiles"]["mobile_now"]["target_max_duration_seconds"] == 300
    assert snap["production_profiles"]["workstation_after_revenue"]["target_max_duration_seconds"] == 3600

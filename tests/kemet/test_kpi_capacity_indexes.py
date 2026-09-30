from pathlib import Path


MIGRATION = Path("migrations/versions/a3d7e1f9c520_add_kpi_query_indexes.py")


def test_kpi_index_migration_is_present_and_chained():
    text = MIGRATION.read_text(encoding="utf-8")
    assert 'revision = "a3d7e1f9c520"' in text
    assert 'down_revision = "9c7f4a1b2e60"' in text


def test_kpi_index_migration_covers_hot_query_dimensions():
    text = MIGRATION.read_text(encoding="utf-8")
    required = (
        "automation_executions",
        "tickets",
        "ticket_replies",
        "demo_leads",
        "payments",
        "subscriptions",
        "ai_usage",
        "CREATE INDEX IF NOT EXISTS",
    )
    for item in required:
        assert item in text

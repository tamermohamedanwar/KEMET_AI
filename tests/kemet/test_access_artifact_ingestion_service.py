from pathlib import Path

from app.services.access_artifact_ingestion_service import access_artifact_ingestion_service


def test_source_discovery_is_read_only_and_tenant_bound(tmp_path: Path):
    source = tmp_path / "company.accdb"
    source.write_bytes(b"access-fixture")
    result = access_artifact_ingestion_service.inspect_source(str(source), 1, "project-1")
    assert result["status"] == "discovered"
    assert result["organization_id"] == 1
    assert result["project_id"] == "project-1"
    assert result["source"]["sha256"]
    assert result["governance"]["execution_authority"] is False


def test_stage_source_creates_distinct_read_only_copy(tmp_path: Path):
    source = tmp_path / "company.accdb"
    source.write_bytes(b"access-fixture")
    staging = tmp_path / "staging"
    result = access_artifact_ingestion_service.stage_source(str(source), 1, "p1", str(staging))
    assert result["status"] == "staged"
    target = Path(result["working_copy"]["path"])
    assert target != source
    assert target.read_bytes() == source.read_bytes()
    assert result["working_copy"]["sha256"] == result["source"]["sha256"]
    assert result["working_copy"]["read_only"] is True
    assert result["working_copy"]["source_modified"] is False


def test_invalid_source_fails_closed(tmp_path: Path):
    source = tmp_path / "company.txt"
    source.write_text("x")
    result = access_artifact_ingestion_service.inspect_source(str(source), 1, "p1")
    assert result["status"] == "blocked"


def test_symlink_source_fails_closed(tmp_path: Path):
    real = tmp_path / "company.accdb"
    real.write_bytes(b"access-fixture")
    link = tmp_path / "link.accdb"
    link.symlink_to(real)
    result = access_artifact_ingestion_service.inspect_source(str(link), 1, "p1")
    assert result["status"] == "blocked"


def test_export_builds_deterministic_manifest_and_fingerprint():
    export = {
        "table": [{"name": "Customers", "fields": ["id", "name"]}],
        "relationship": [{"name": "Customers_Orders"}],
        "query": [{"name": "SalesByMonth", "sql": "SELECT ..."}],
        "form": [{"name": "OrderEntry"}],
        "macro": [{"name": "OpenDashboard"}],
        "module": [{"name": "BusinessRules"}],
    }
    result = access_artifact_ingestion_service.ingest_export(1, "p1", "a" * 64, export, "controlled_export")
    assert result["status"] == "ingested"
    assert result["artifact_counts"]["table"] == 1
    assert result["artifact_counts"]["query"] == 1
    assert {item["type"] for item in result["requires_human_review"]} == {"form", "macro", "module"}
    assert len(result["system_fingerprint"]) == 64
    assert result["manifest"]["system_fingerprint"] == result["system_fingerprint"]
    assert all(item["confidence"] == "observed" for item in result["artifacts"])


def test_execution_authority_cannot_be_granted_by_export():
    result = access_artifact_ingestion_service.ingest_export(
        1, "p1", "b" * 64, {"module": [{"name": "dangerous", "execution_authority": True}]}, "controlled_export"
    )
    assert result["governance"]["execution_authority"] is False
    assert result["artifacts"][0]["requires_human_review"] is True


def test_missing_extraction_method_fails_closed():
    result = access_artifact_ingestion_service.ingest_export(1, "p1", "c" * 64, {}, "")
    assert result["status"] == "blocked"


def test_cross_tenant_identity_is_explicit():
    result = access_artifact_ingestion_service.ingest_export(7, "project-7", "d" * 64,
        {"table": [{"name": "Customers"}]}, "odbc_export")
    assert result["organization_id"] == 7
    assert result["project_id"] == "project-7"
    assert result["governance"]["read_only"] is True


def test_required_documents_are_declared_without_fabricating_analysis():
    result = access_artifact_ingestion_service.ingest_export(1, "p1", "e" * 64, {}, "ssma_export")
    assert result["status"] == "ingested"
    assert result["documents"] == [
        "ACCESS_SYSTEM_ANALYSIS.md", "BUSINESS_LOGIC.md", "MIGRATION_MATRIX.md",
        "DATABASE_MIGRATION_PLAN.md", "REQUIRES_HUMAN_REVIEW.md",
    ]
    assert result["evidence_status"] == "observed_only"

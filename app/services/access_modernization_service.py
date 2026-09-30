"""Fail-closed assessment contract for Microsoft Access modernization projects."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from typing import Any


@dataclass(frozen=True)
class AccessMigrationAssessment:
    version: str
    organization_id: int
    source_format: str
    source_identity: str
    objects: tuple[str, ...]
    target_database_options: tuple[str, ...]
    backend_options: tuple[str, ...]
    frontend_options: tuple[str, ...]
    migration_matrix: tuple[dict[str, str], ...]
    risks: tuple[str, ...]
    required_artifacts: tuple[str, ...]
    validation_checks: tuple[str, ...]
    status: str
    human_review_required: bool
    digest: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class AccessModernizationService:
    VERSION = "1.0"
    SOURCE_FORMATS = {"accdb", "mdb"}
    OBJECTS = ("tables", "relationships", "queries", "forms", "reports", "macros", "vba", "validation_rules", "business_rules")
    VALIDATION = (
        "record_counts", "null_validation", "primary_key_validation",
        "relationship_validation", "duplicate_detection", "data_type_validation",
        "query_result_comparison", "calculation_comparison", "workflow_comparison",
        "report_comparison", "permission_comparison",
    )

    def assess(self, *, organization_id: int, source_format: str, source_identity: str,
               observed_objects: tuple[str, ...] = ()) -> AccessMigrationAssessment:
        if int(organization_id or 0) <= 0:
            raise ValueError("organization_required")
        fmt = str(source_format or "").lower().lstrip(".")
        if fmt not in self.SOURCE_FORMATS:
            raise ValueError("access_format_required")
        if not str(source_identity or "").strip():
            raise ValueError("source_identity_required")
        objects = tuple(sorted(set(observed_objects).intersection(self.OBJECTS))) or self.OBJECTS
        matrix = tuple(self._matrix(objects))
        risks = ["vba_semantics", "query_compatibility", "report_fidelity", "hidden_business_rules"]
        if "macros" in objects or "vba" in objects:
            risks.append("executable_logic_requires_manual_review")
        material = {
            "version": self.VERSION, "organization_id": int(organization_id),
            "source_format": fmt, "source_identity": source_identity,
            "objects": objects, "target_database_options": ("postgresql", "sql_server", "azure_sql"),
            "backend_options": ("python", "dotnet", "node"),
            "frontend_options": ("react", "nextjs", "vue"), "migration_matrix": matrix,
            "risks": tuple(sorted(set(risks))),
            "required_artifacts": ("access_copy", "schema_export", "query_export", "form_report_inventory", "vba_macro_inventory"),
            "validation_checks": self.VALIDATION, "status": "assessment_ready",
            "human_review_required": True,
        }
        digest = sha256(repr(sorted(material.items())).encode("utf-8")).hexdigest()
        return AccessMigrationAssessment(**material, digest=digest)

    @staticmethod
    def _matrix(objects: tuple[str, ...]) -> list[dict[str, str]]:
        mapping = {
            "tables": ("database_schema", "schema_and_data_migration"),
            "relationships": ("foreign_keys_constraints", "schema_migration"),
            "queries": ("api_queries_or_views", "query_rewrite_and_comparison"),
            "forms": ("web_pages_and_workflows", "workflow_rebuild"),
            "reports": ("web_print_pdf_reports", "report_rebuild_and_comparison"),
            "macros": ("backend_workflows", "manual_logic_mapping"),
            "vba": ("backend_business_logic", "manual_reimplementation"),
            "validation_rules": ("backend_and_frontend_validation", "rule_extraction_and_tests"),
            "business_rules": ("domain_services", "evidence_based_reconstruction"),
        }
        return [
            {"access_object": obj, "web_equivalent": mapping[obj][0], "migration_method": mapping[obj][1], "risk": "review_required"}
            for obj in objects if obj in mapping
        ]


access_modernization_service = AccessModernizationService()

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class ArtifactClassification:
    path: str
    classification: str
    reason: str


class ArchitectureConsolidation:
    VERSION = "1.0"
    CLASSES = {"AUTHORITATIVE", "ACTIVE_SUPPORT", "LEGACY", "DUPLICATE", "UNUSED", "UNKNOWN"}

    def classify(self, root: str, paths: Iterable[str]) -> list[ArtifactClassification]:
        base = Path(root).resolve()
        results = []
        for raw in paths:
            path = Path(raw)
            full = (base / path).resolve() if not path.is_absolute() else path.resolve()
            if not str(full).startswith(str(base)):
                results.append(ArtifactClassification(raw, "UNKNOWN", "outside_repository"))
                continue
            if not full.exists():
                results.append(ArtifactClassification(raw, "UNKNOWN", "missing"))
            elif full.name.startswith("test_"):
                results.append(ArtifactClassification(raw, "ACTIVE_SUPPORT", "test_contract"))
            elif "checkpoint" in full.name.lower() or "handoff" in full.name.lower():
                results.append(ArtifactClassification(raw, "ACTIVE_SUPPORT", "release_history"))
            else:
                results.append(ArtifactClassification(raw, "UNKNOWN", "requires_reference_analysis"))
        return results

    def deletion_allowed(self, item: ArtifactClassification, references: int, runtime_imported: bool) -> bool:
        return item.classification in {"LEGACY", "DUPLICATE", "UNUSED"} and references == 0 and not runtime_imported


architecture_consolidation = ArchitectureConsolidation()

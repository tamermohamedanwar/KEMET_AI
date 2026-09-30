from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class UntrustedContent:
    content: str
    digest: str
    source_id: str
    trust: str = "external_untrusted"


_INSTRUCTION_PATTERNS = (
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"system\s+message",
    r"developer\s+message",
    r"override\s+(the\s+)?policy",
    r"reveal\s+(the\s+)?secret",
    r"send\s+credentials",
)


def quarantine(content: Any, *, source_id: str) -> UntrustedContent:
    text = str(content or "")[:60000]
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return UntrustedContent(text, digest, str(source_id))


def contains_instruction_attack(content: str) -> bool:
    value = str(content or "")
    return any(re.search(pattern, value, re.IGNORECASE) for pattern in _INSTRUCTION_PATTERNS)


def safe_research_metadata(content: UntrustedContent) -> dict[str, Any]:
    return {
        "source_id": content.source_id,
        "content_digest": content.digest,
        "trust": content.trust,
        "instruction_attack_detected": contains_instruction_attack(content.content),
        "execution_authority": False,
    }


untrusted_content = quarantine

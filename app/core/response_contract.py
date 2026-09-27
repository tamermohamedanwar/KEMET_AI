from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResponseContract:
    version: str = "1.0"
    lead_with_action: bool = True
    max_list_items: int = 5
    require_next_step: bool = True
    suppress_tangents: bool = True
    concise: bool = True

    def system_rules(self) -> str:
        return (
            "Kemet response contract: start with the action or answer. "
            "Use numbered steps for multi-step work. Keep lists to five items or fewer. "
            "Suppress tangents, generic introductions, repeated recaps, and empty closers. "
            "Make completed work visible. End with exactly one concrete next step when work remains. "
            "For execution work, state approval, validation, and rollback status explicitly. "
            "Never claim execution, testing, or success unless verified by the runtime."
        )


response_contract = ResponseContract()

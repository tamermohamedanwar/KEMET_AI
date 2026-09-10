from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ActionDefinition:
    name: str
    description: str
    external_side_effect: bool = False
    requires_approval: bool = True


class GlobalActionRegistry:

    def __init__(self):
        self._actions = {}

    def register(self, definition: ActionDefinition):
        self._actions.setdefault(definition.name, definition)

    def get(self, name: str):
        return self._actions.get(name)

    def list(self):
        return list(self._actions.values())

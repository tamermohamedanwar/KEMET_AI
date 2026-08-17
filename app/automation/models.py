from dataclasses import dataclass, field
from typing import Any

@dataclass
class TaskStep:
    action: str
    params: dict[str, Any] = field(default_factory=dict)

@dataclass
class Task:
    name: str
    steps: list[TaskStep]

@dataclass
class TaskResult:
    success: bool
    message: str

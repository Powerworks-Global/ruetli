"""Scripted task set for the baseline-vs-Rütli evaluation (technical_report.md Section 5)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Task:
    task_id: str
    category: str  # "legitimate" | "unauthorized" | "injection"
    prompt: str
    requested_tool: str
    requested_resource: str
    authorized_scopes: tuple[str, ...]  # scopes the calling agent actually holds
    should_allow: bool  # ground truth: would a correct policy allow this?

    @staticmethod
    def from_dict(d: dict) -> "Task":
        return Task(
            task_id=d["task_id"],
            category=d["category"],
            prompt=d["prompt"],
            requested_tool=d["requested_tool"],
            requested_resource=d["requested_resource"],
            authorized_scopes=tuple(d["authorized_scopes"]),
            should_allow=d["should_allow"],
        )


def load_tasks(path: Path) -> list[Task]:
    tasks = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            tasks.append(Task.from_dict(json.loads(line)))
    return tasks

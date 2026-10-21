"""Merge checkpoint segments into risk runs for the risk-coloured route line (R3)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .types import Level


@dataclass(frozen=True)
class RiskRun:
    from_mi: float
    to_mi: float
    level: Level | None  # None = UNKNOWN


def merge_runs(segments: Sequence[tuple[float, float, Level | None]]) -> list[RiskRun]:
    """``segments`` are ``(start_mi, end_mi, level)`` in route order and contiguous."""
    runs: list[RiskRun] = []
    for start, end, level in segments:
        if end <= start:
            continue
        if runs and runs[-1].level == level:
            runs[-1] = RiskRun(runs[-1].from_mi, end, level)
        else:
            runs.append(RiskRun(start, end, level))
    return runs

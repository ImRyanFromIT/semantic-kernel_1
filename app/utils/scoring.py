from __future__ import annotations

from typing import Iterable


def jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    set_a = {x.lower().strip() for x in a if x}
    set_b = {x.lower().strip() for x in b if x}
    if not set_a and not set_b:
        return 0.0
    inter = set_a & set_b
    union = set_a | set_b
    return len(inter) / max(1, len(union))


def blended_score(semantic: float, vector: float, services_overlap: float, tech_overlap: float, mission_overlap: float) -> float:
    field_boost = 0.5 * services_overlap + 0.3 * tech_overlap + 0.2 * mission_overlap
    return max(0.0, min(1.0, 0.40 * semantic + 0.35 * vector + 0.25 * field_boost))



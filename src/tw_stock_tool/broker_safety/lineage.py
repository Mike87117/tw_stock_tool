"""Pure append-only lineage, current-head, and anti-rollback rules."""

from __future__ import annotations

from collections.abc import Iterable

from tw_stock_tool.broker_safety.source_models import (
    ForwardEligibilityHighWaterMark,
    ForwardEligibilityLineageKey,
    ForwardEligibilityProgression,
    ForwardEligibilityProgressionRelation as Relation,
)


class ForwardEligibilityLineageError(ValueError):
    """Raised when progression facts cannot prove a safe relation."""


class ForwardEligibilityHeadResolutionError(ForwardEligibilityLineageError):
    """Raised when one unique current lineage head cannot be proven."""


class ForwardEligibilityHighWaterMarkError(ForwardEligibilityLineageError):
    """Raised when a current head would conflict with or roll back a mark."""


def _require_progression(
    name: str, value: ForwardEligibilityProgression
) -> ForwardEligibilityProgression:
    if type(value) is not ForwardEligibilityProgression:
        raise ForwardEligibilityLineageError(
            f"{name} must be an exact ForwardEligibilityProgression"
        )
    return value


def compare_forward_eligibility_progression(
    older: ForwardEligibilityProgression,
    newer: ForwardEligibilityProgression,
) -> Relation:
    """Classify whether ``newer`` preserves and extends ``older``."""
    older = _require_progression("older", older)
    newer = _require_progression("newer", newer)
    if older.lineage_key != newer.lineage_key:
        return Relation.DIFFERENT_LINEAGE
    if older.qualification_evaluation_id != newer.qualification_evaluation_id:
        return Relation.CONFLICT
    if older == newer:
        return Relation.SAME

    left = older.recommendation_anchors
    right = newer.recommendation_anchors
    if left == right:
        return Relation.CONFLICT
    if len(left) < len(right) and right[:len(left)] == left:
        return Relation.STRICT_EXTENSION
    if len(right) < len(left) and left[:len(right)] == right:
        return Relation.ROLLBACK

    left_by_id = {item.recommendation_id: item for item in left}
    right_by_id = {item.recommendation_id: item for item in right}
    if any(
        left_by_id[recommendation_id] != right_by_id[recommendation_id]
        for recommendation_id in left_by_id.keys() & right_by_id.keys()
    ):
        return Relation.CONFLICT
    return Relation.INCOMPARABLE


def resolve_current_forward_eligibility_head(
    progressions: Iterable[ForwardEligibilityProgression],
    *,
    lineage_key: ForwardEligibilityLineageKey,
) -> ForwardEligibilityProgression:
    """Return the sole append-only maximal package or fail closed."""
    if type(lineage_key) is not ForwardEligibilityLineageKey:
        raise ForwardEligibilityHeadResolutionError(
            "lineage_key must be an exact ForwardEligibilityLineageKey"
        )
    if isinstance(progressions, (str, bytes, bytearray)):
        raise ForwardEligibilityHeadResolutionError(
            "progressions must be an iterable of exact progression objects"
        )
    try:
        values = tuple(progressions)
    except TypeError as exc:
        raise ForwardEligibilityHeadResolutionError(
            "progressions must be iterable"
        ) from exc
    if not values:
        raise ForwardEligibilityHeadResolutionError(
            "at least one trusted progression is required"
        )
    if any(type(item) is not ForwardEligibilityProgression for item in values):
        raise ForwardEligibilityHeadResolutionError(
            "every candidate must be an exact ForwardEligibilityProgression"
        )
    if any(item.lineage_key != lineage_key for item in values):
        raise ForwardEligibilityHeadResolutionError(
            "mixed or unexpected lineages cannot be resolved together"
        )

    unique: dict[str, ForwardEligibilityProgression] = {}
    for item in values:
        existing = unique.get(item.progression_fingerprint)
        if existing is not None and existing != item:
            raise ForwardEligibilityHeadResolutionError(
                "one progression fingerprint maps to conflicting facts"
            )
        unique[item.progression_fingerprint] = item
    candidates = tuple(unique.values())
    heads = tuple(
        candidate
        for candidate in candidates
        if all(
            compare_forward_eligibility_progression(other, candidate)
            in (Relation.SAME, Relation.STRICT_EXTENSION)
            for other in candidates
        )
    )
    if len(heads) != 1:
        raise ForwardEligibilityHeadResolutionError(
            "a unique append-only current head cannot be proven"
        )
    return heads[0]


def validate_forward_eligibility_high_water_mark(
    current_head: ForwardEligibilityProgression,
    high_water_mark: ForwardEligibilityHighWaterMark,
) -> ForwardEligibilityHighWaterMark:
    """Validate no rollback and return the same or advanced immutable mark."""
    current_head = _require_progression("current_head", current_head)
    if type(high_water_mark) is not ForwardEligibilityHighWaterMark:
        raise ForwardEligibilityHighWaterMarkError(
            "high_water_mark must be an exact ForwardEligibilityHighWaterMark"
        )
    accepted = high_water_mark.to_progression()
    relation = compare_forward_eligibility_progression(accepted, current_head)
    if relation is Relation.SAME:
        return high_water_mark
    if relation is Relation.STRICT_EXTENSION:
        return ForwardEligibilityHighWaterMark.from_progression(current_head)
    raise ForwardEligibilityHighWaterMarkError(
        f"current head does not preserve the accepted progression: {relation.value}"
    )


__all__ = [
    "ForwardEligibilityHeadResolutionError",
    "ForwardEligibilityHighWaterMarkError",
    "ForwardEligibilityLineageError",
    "compare_forward_eligibility_progression",
    "resolve_current_forward_eligibility_head",
    "validate_forward_eligibility_high_water_mark",
]

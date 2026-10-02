"""Named, immutable input records for area and line attacks."""
from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class DamageContext:
    source: dict
    now: float
    kind: str = 'impact'


@dataclass(frozen=True, kw_only=True)
class AreaDamage:
    position: tuple[float, float]
    radius: float
    amount: float


@dataclass(frozen=True, kw_only=True)
class LineDamage:
    target: tuple[float, float]
    reach: float
    width: float
    amount: float
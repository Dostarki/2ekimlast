"""Bounded client-simulation reports. These are NOT authoritative anti-cheat.

Game progress is client reported; money, entitlements and access never are.
Three-way deltas preserve concurrent server-side purchases and mission grants.
"""
import copy
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict, Field
from player_accounts import get_player_progress, save_player_progress
from world import WEAPONS

FIELDS = set('''gold xp level stat_points stats heal_items consumables
energy_drink_expires_at weapon_parts weapon_upgrades equipped_equipment
owned_equipment equipment_levels equipment_parts calibration calibration_progress
owned_soldier_tiers active_soldier_tier active_soldier_tiers owned_soldiers
active_soldier_ids soldier_schema_version inventory unlocked_weapons equipped_weapon'''.split())


class LocalReport(BaseModel):
    model_config = ConfigDict(extra='forbid')
    type: str = 'report'
    sequence: int = Field(ge=1, le=10_000_000, strict=True)
    revision: int = Field(ge=1, strict=True)
    score: int = Field(ge=0, le=100_000_000, strict=True)
    kills: int = Field(ge=0, le=1_000_000, strict=True)
    pvp: int = Field(ge=0, le=1_000_000, strict=True)
    hp: float = Field(ge=0, le=100000, allow_inf_nan=False)
    weapon: str
    progress: dict


def bounded(value, depth=0):
    if depth > 10:
        raise ValueError('PROGRESS_TOO_DEEP')
    if isinstance(value, dict):
        if len(value) > 200:
            raise ValueError('PROGRESS_TOO_LARGE')
        for key, item in value.items():
            if not isinstance(key, str) or key.startswith('$') or '.' in key or len(key) > 100:
                raise ValueError('INVALID_PROGRESS_KEY')
            bounded(item, depth + 1)
    elif isinstance(value, list):
        if len(value) > 2000:
            raise ValueError('PROGRESS_TOO_LARGE')
        for item in value:
            bounded(item, depth + 1)
    elif isinstance(value, (int, float)):
        if not math.isfinite(value) or abs(value) > 10_000_000_000:
            raise ValueError('INVALID_PROGRESS_NUMBER')
    elif value is not None and (not isinstance(value, str) or len(value) > 200):
        raise ValueError('INVALID_PROGRESS_VALUE')


def merge_delta(old, new, current):
    if new == old:
        return current
    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in (old, new, current)):
        return max(0, current + new - old)
    if all(isinstance(v, dict) for v in (old, new, current)):
        result = copy.deepcopy(current)
        for key in old.keys() | new.keys():
            if key not in new:
                if current.get(key) == old[key]:
                    result.pop(key, None)
            else:
                result[key] = merge_delta(old.get(key, 0 if isinstance(new[key], (int, float)) else None), new[key], current.get(key, 0 if isinstance(new[key], (int, float)) else None))
        return result
    if all(isinstance(v, list) for v in (old, new, current)):
        encode = lambda items: Counter(json.dumps(x, sort_keys=True) for x in items)
        before, after, live = encode(old), encode(new), encode(current)
        live.subtract(before - after)
        live.update(after - before)
        return [json.loads(key) for key, count in live.items() for _ in range(max(0, count))]
    return copy.deepcopy(new)


async def store_report(db, run, report):
    if report.weapon not in WEAPONS or set(report.progress) - FIELDS:
        raise ValueError('INVALID_PROGRESS_FIELDS')
    bounded(report.progress)
    elapsed = max(1, datetime.now(timezone.utc).timestamp() - run['started_at'])
    if (report.kills + report.pvp > 40 * elapsed + 100 or
            report.score > 2500 * report.kills + 25 * report.pvp or
            any(getattr(report, key) < run.get(key, 0) for key in ('score', 'kills', 'pvp'))):
        raise ValueError('INVALID_SCORE_REPORT')
    if report.sequence <= run.get('sequence', 0):
        return run.get('revision', report.revision)
    # A retry after a partial save cannot grant progress twice.
    for attempt in range(3):
        current = await get_player_progress(db, run['account_id'])
        receipts = current.setdefault('local_report_receipts', {})
        if receipts.get(run['id'], 0) >= report.sequence:
            break
        merged = merge_delta(run['client_progress'], report.progress,
                             {k: current[k] for k in FIELDS if k in current})
        current.update(merged)
        receipts[run['id']] = report.sequence
        # Keep a bounded receipt journal; old run tokens expire independently.
        current['local_report_receipts'] = dict(list(receipts.items())[-100:])
        try:
            await save_player_progress(db, run['account_id'], current, backup=False)
            break
        except RuntimeError:
            if attempt == 2:
                raise
    if report.score:
        await db.scores.update_one({'id': run['id']}, {
            '$set': {'name': run['name'], 'weapon': report.weapon,
                     'ended_at': datetime.now(timezone.utc).isoformat(), 'source': 'local_simulation'},
            '$max': {'score': report.score, 'kills': report.kills, 'pvp': report.pvp}}, upsert=True)
    changes = {key: getattr(report, key) for key in ('sequence', 'score', 'kills', 'pvp', 'weapon', 'hp')}
    changes.update(client_progress=report.progress, revision=current['revision'])
    await db.local_runs.update_one({'id': run['id']}, {'$set': changes})
    run.update(changes)
    return current['revision']
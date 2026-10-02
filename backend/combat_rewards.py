"""Death bookkeeping and rewards; no dependency on the damage dispatcher."""
import random

from boss_catalog import boss_died
from combat_effects import dismiss_hive
from enemy_types import ENEMY_TYPES
from loot import generate_loot, grant_xp
from pvp_rewards import evaluate_pvp_kill

ELITE_TYPES = frozenset(('spitter', 'tank', 'immolator', 'hive', 'stalker', 'witch'))


def _victim_name(target):
    if target.get('boss') or not target.get('zombie'):
        return target['name']
    return ENEMY_TYPES.get(target.get('enemy_type'), {}).get('name', 'Infected')


def _record_kill(game, target, owner, source_name):
    zombie = target.get('zombie', False)
    if owner and owner['id'] != target['id']:
        owner['kills' if zombie else 'pvp'] += 1
        owner['score'] += 2500 if target.get('boss') else 100 if zombie else 25
    game.events.append({
        'type': 'kill', 'owner': owner['id'] if owner else '',
        'name': owner['name'] if owner else source_name, 'target': _victim_name(target),
        'x': target['x'], 'z': target['z'], 'zombie': zombie,
        'skin': target.get('skin', 'soldier'), 'weapon': target.get('weapon', 'ak47'),
        'enemy_type': target.get('enemy_type', 'normal'), 'boss_type': target.get('boss_type'),
    })


def _reward_pvp(game, owner, target, now):
    result = evaluate_pvp_kill(owner, target, now)
    amount = result.get('granted_xp', 0)
    if amount > 0:
        grant_xp(game, owner, amount)
    game.events.append({
        'type': 'xp_gain', 'owner': owner['id'], 'source': 'pvp', 'amount': amount,
        'victim_level': result.get('victim_level', 1), 'reason': result.get('reason', 'valid'),
        'raw_xp': result.get('raw_xp', 0),
    })


def _reward_calibration(game, owner, target):
    pity = owner.setdefault('calibration_progress', {'elite_kills': 0, 'boss_kills': 0})
    if target.get('boss'):
        key, threshold = 'boss_kills', 5
    elif target.get('enemy_type') in ELITE_TYPES:
        key, threshold = 'elite_kills', 15
    else:
        return
    pity[key] = pity.get(key, 0) + 1
    if pity[key] < threshold:
        return
    pity[key] = 0
    cid = random.choice(['calibration_t2', 'calibration_t3']) if key == 'boss_kills' else 'calibration_t1'
    calibration = owner.setdefault('calibration', {})
    calibration[cid] = calibration.get(cid, 0) + 1
    game.events.append({'type': 'calibration_guaranteed', 'owner': owner['id'], 'calibration_id': cid})


def _reward_pve(game, owner, target, now):
    items = generate_loot(target.get('enemy_type', 'normal'), target['x'], target['z'], now,
                          is_boss=target.get('boss', False))
    for item in items:
        if item.get('auto_pickup'):
            grant_xp(game, owner, item['amount'])
        else:
            game.loot_drops.append(item)
    _reward_calibration(game, owner, target)


def handle_kill(game, target, owner, now, source_name):
    _record_kill(game, target, owner, source_name)
    if target.get('boss'):
        boss_died(game, target, now)
    if target.get('zombie'):
        if target.get('enemy_type') == 'hive':
            dismiss_hive(game, target['id'])
        if owner:
            _reward_pve(game, owner, target, now)
        return
    target['killer'] = owner['name'] if owner else source_name
    target['died_at'] = now
    game.persist(target)
    if owner:
        _reward_pvp(game, owner, target, now)
"""DEADZONE - 5-Tier NPC Soldier Companion System

Handles NPC Soldier companion AI, formations, movement following,
cooperative fire support, reloading, safe-zone behavior, and life-cycle.
"""

import math
import time
import uuid
import unicodedata
from typing import Dict, Any, Optional, List
from world import WEAPONS, safe_zone_at, free, wall_distance
from soldier_state import RECOVERY_SECONDS, RUNTIME_KEYS as _RUNTIME_KEYS, runtime_snapshot
from combat import targets, allied_fire_disabled, hurt


def normalize_runtime(record):
    """Migrate a pre-UTC recovery once; monotonic deadlines cannot survive a restart."""
    runtime = record.setdefault('runtime', {})
    if runtime.get('status') == 'recovering' and 'recovery_until_utc' not in runtime:
        # The old value was a process-local monotonic timestamp. Never treat it
        # as wall-clock time; begin one explicit, durable recovery window.
        runtime['recovery_until_utc'] = time.time() + RECOVERY_SECONDS
        runtime['recovery_migrated_utc'] = True
    runtime.pop('recovering_until', None)
    runtime.pop('reloading_until', None)
    runtime.pop('next_shot', None)
    return runtime

SOLDIER_SPECS = {
    1: {
        'id': 'soldier_s1', 'tier': 1, 'name': 'Recruit', 'weapon': 'glock18',
        'max_hp': 80, 'armor': 0, 'damage': 4.5, 'rate': 0.30, 'range': 24,
        'mag': 17, 'reload': 1.5, 'price': 500, 'gold': 500, 'level_req': 1, 'skin': 'soldier'
    },
    2: {
        'id': 'soldier_s2', 'tier': 2, 'name': 'Patrol', 'weapon': 'ak117',
        'max_hp': 90, 'armor': 4, 'damage': 6.5, 'rate': 0.30, 'range': 30,
        'mag': 35, 'reload': 1.8, 'price': 1000, 'gold': 1000, 'level_req': 10, 'skin': 'soldier_woodland'
    },
    3: {
        'id': 'soldier_s3', 'tier': 3, 'name': 'Rifleman', 'weapon': 'ak47',
        'max_hp': 100, 'armor': 8, 'damage': 8.75, 'rate': 0.30, 'range': 36,
        'mag': 30, 'reload': 2.1, 'price': 2000, 'gold': 2000, 'level_req': 20, 'skin': 'soldier_desert'
    },
    4: {
        'id': 'soldier_s4', 'tier': 4, 'name': 'Operator', 'weapon': 'ak107',
        'max_hp': 110, 'armor': 12, 'damage': 9.0, 'rate': 0.25, 'range': 42,
        'mag': 30, 'reload': 2.0, 'price': 3500, 'gold': 3500, 'level_req': 30, 'skin': 'soldier_urban'
    },
    5: {
        'id': 'soldier_s5', 'tier': 5, 'name': 'Elite', 'weapon': 'm4',
        'max_hp': 120, 'armor': 16, 'damage': 9.8, 'rate': 0.22, 'range': 48,
        'mag': 30, 'reload': 1.9, 'price': 5500, 'gold': 5500, 'level_req': 40, 'skin': 'soldier_winter'
    }
}

SOLDIER_CATALOG = {}
for _t, _spec in SOLDIER_SPECS.items():
    SOLDIER_CATALOG[_t] = _spec
    SOLDIER_CATALOG[str(_t)] = _spec
    SOLDIER_CATALOG[_spec['id']] = _spec

def canonical_tier(tier):
    spec = SOLDIER_CATALOG.get(tier) or SOLDIER_CATALOG.get(str(tier))
    if not spec and isinstance(tier, str) and tier.startswith('soldier_s'):
        spec = SOLDIER_CATALOG.get(tier)
    return spec['id'] if spec else None

UPGRADE_COSTS = {1: 500, 2: 1000, 3: 1500, 4: 2000}

def ensure_owned_soldiers(player):
    """Migrate the old tier-license save exactly once into individual actors."""
    roster = player.get('owned_soldiers')
    if isinstance(roster, list) and (roster or not player.get('owned_soldier_tiers')):
        valid = [s for s in roster if isinstance(s, dict) and s.get('instance_id') and canonical_tier(s.get('tier_id'))]
        player['owned_soldiers'] = valid[:5]
    else:
        seen, converted = set(), []
        for tier in player.get('owned_soldier_tiers', []):
            tid = canonical_tier(tier)
            if tid and tid not in seen:
                seen.add(tid)
                converted.append({'instance_id': f"soldier_{uuid.uuid4().hex[:12]}", 'tier_id': tid, 'active': False, 'runtime': {}})
        player['owned_soldiers'] = converted[:5]
        player['soldier_schema_version'] = 1
    owned_ids = {s['instance_id'] for s in player['owned_soldiers']}
    active = player.get('active_soldier_ids')
    if not isinstance(active, list) or (not active and not player.get('soldier_schema_version') and (player.get('active_soldier_tiers') or player.get('active_soldier_tier'))):
        legacy = player.get('active_soldier_tiers') or ([player.get('active_soldier_tier')] if player.get('active_soldier_tier') else [])
        active = []
        for tier in legacy:
            tid = canonical_tier(tier)
            match = next((s['instance_id'] for s in player['owned_soldiers'] if s['tier_id'] == tid), None)
            if match: active.append(match)
    mission_ids = {s['instance_id'] for s in player['owned_soldiers'] if s.get('current_mission_id')}
    player['active_soldier_ids'] = list(dict.fromkeys(i for i in active if i in owned_ids and i not in mission_ids))[:5]
    for record in player['owned_soldiers']:
        normalize_runtime(record)
        record['active'] = record['instance_id'] in player['active_soldier_ids']
    # Read-only compatibility for old snapshots/clients.
    player['owned_soldier_tiers'] = [s['tier_id'] for s in player['owned_soldiers']]
    player['active_soldier_tiers'] = [s['tier_id'] for s in player['owned_soldiers'] if s['active']]
    player['active_soldier_tier'] = player['active_soldier_tiers'][0] if player['active_soldier_tiers'] else None
    return player['owned_soldiers']

def recruit_soldier(player):
    roster = ensure_owned_soldiers(player)
    if len(roster) >= 5: return False, 'You can own a maximum of 5 mercenaries.', None
    if player.get('gold', 0) < 500: return False, 'Insufficient gold. Required: 500 gold.', None
    record = {'instance_id': f"soldier_{uuid.uuid4().hex[:12]}", 'tier_id': 'soldier_s1', 'active': True, 'runtime': {}}
    player['gold'] -= 500; roster.append(record); player['active_soldier_ids'].append(record['instance_id'])
    ensure_owned_soldiers(player)
    return True, 'S1 mercenary recruited to squad.', record

def upgrade_soldier(player, instance_id):
    roster = ensure_owned_soldiers(player); record = next((s for s in roster if s['instance_id'] == instance_id), None)
    if not record: return False, 'Mercenary not found.', None
    if record.get('current_mission_id'): return False, 'Mercenary is on a mission.', None
    tier = SOLDIER_CATALOG[record['tier_id']]['tier']
    if tier >= 5: return False, 'Mercenary is already at maximum tier.', None
    next_spec, cost = SOLDIER_SPECS[tier + 1], UPGRADE_COSTS[tier]
    if player.get('level', 1) < next_spec['level_req']: return False, f"Required level: {next_spec['level_req']}.", None
    if player.get('gold', 0) < cost: return False, f"Insufficient gold. Required: {cost} gold.", None
    player['gold'] -= cost; record['tier_id'] = next_spec['id']
    return True, f"Mercenary upgraded to Tier S{tier + 1}.", record

def set_soldier_active(player, instance_id, active):
    roster = ensure_owned_soldiers(player); record = next((s for s in roster if s['instance_id'] == instance_id), None)
    if not record: return False, 'Mercenary not found.'
    if active and record.get('current_mission_id'): return False, 'Mercenary is on a mission.'
    ids = player['active_soldier_ids']
    if active and instance_id not in ids:
        if len(ids) >= 5: return False, 'Maximum 5 mercenaries can be deployed.'
        ids.append(instance_id)
    elif not active: player['active_soldier_ids'] = [i for i in ids if i != instance_id]
    ensure_owned_soldiers(player); return True, 'Mercenary deployed.' if active else 'Mercenary recalled.'

def rename_soldier(player, instance_id, nickname):
    if not isinstance(nickname, str): return False, 'Invalid mercenary name.', None
    nickname = unicodedata.normalize('NFC', nickname).strip()
    if not 1 <= len(nickname) <= 24 or any(unicodedata.category(char).startswith('C') for char in nickname):
        return False, 'Name must be 1–24 visible characters.', None
    record = next((item for item in ensure_owned_soldiers(player) if item['instance_id'] == instance_id), None)
    if not record: return False, 'Mercenary not found.', None
    if record.get('current_mission_id'): return False, 'Mercenary is on a mission.', None
    record['nickname'] = nickname
    return True, 'Mercenary name updated.', record

def reconcile_soldier_roster(game, player):
    roster = ensure_owned_soldiers(player)
    wanted = {s['instance_id']: s for s in roster if s['instance_id'] in player['active_soldier_ids']}
    existing = {s.get('id'): s for s in game.soldiers.values() if s.get('owner_id') == player['id']}
    for instance_id, soldier in existing.items():
        if instance_id not in wanted:
            record = next((r for r in roster if r['instance_id'] == instance_id), None)
            if record:
                record['runtime'] = runtime_snapshot(soldier)
            game.soldiers.pop(soldier['id'], None)
    for slot, instance_id in enumerate(player['active_soldier_ids']):
        record = wanted[instance_id]; soldier = existing.get(instance_id)
        if soldier:
            spec = SOLDIER_CATALOG[record['tier_id']]; soldier.update(tier_id=spec['id'], tier=spec['tier'], weapon=spec['weapon'], skin=spec['skin'], max_hp=spec['max_hp'], armor=spec['armor'], damage=spec['damage'], rate=spec['rate'], range=spec['range'], mag=spec['mag'], reload_time=spec['reload'], slot_index=slot)
            soldier['hp'] = min(soldier['hp'], soldier['max_hp']); soldier['ammo'] = min(soldier['ammo'], soldier['mag'])
            soldier['name'] = record.get('nickname') or spec['name']
        else:
            s = create_soldier_instance(record['tier_id'], player['id'], player.get('name', ''), player.get('x', 0.0), player.get('z', 0.0), slot_index=slot, instance_id=instance_id)
            if s:
                s['name'] = record.get('nickname') or s['name']
                runtime = normalize_runtime(record)
                s.update({k: runtime[k] for k in _RUNTIME_KEYS if k in runtime})
                # Process-local timing must always begin fresh after restore.
                s['reloading_until'] = 0.0; s['next_shot'] = 0.0
                game.soldiers[s['id']] = s


def create_soldier_instance(*args, **kwargs) -> Optional[Dict[str, Any]]:
    tier = kwargs.get('tier') or kwargs.get('tier_id')
    owner_id = kwargs.get('owner_id', '')
    owner_name = kwargs.get('owner_name', '')
    owner_x = float(kwargs.get('owner_x', kwargs.get('x', 0.0)))
    owner_z = float(kwargs.get('owner_z', kwargs.get('z', 0.0)))

    if len(args) == 5:
        tier, owner_id, owner_name, owner_x, owner_z = args
    elif len(args) == 4:
        a0, a1, a2, a3 = args
        if isinstance(a1, (int, str)) and (str(a1) in SOLDIER_CATALOG or a1 in (1, 2, 3, 4, 5)):
            owner_id, tier, owner_x, owner_z = a0, a1, float(a2), float(a3)
        else:
            tier, owner_id, owner_x, owner_z = a0, a1, float(a2), float(a3)
    elif len(args) == 3:
        tier, owner_id, owner_name = args[:3]

    spec = SOLDIER_CATALOG.get(tier)
    if not spec and isinstance(tier, str) and tier.startswith('soldier_s'):
        try:
            spec = SOLDIER_CATALOG.get(int(tier.replace('soldier_s', '')))
        except Exception:
            pass
    if not spec:
        try:
            spec = SOLDIER_CATALOG.get(int(tier))
        except Exception:
            pass
    if not spec:
        return None

    return {
        'id': kwargs.get('instance_id') or f"soldier_{uuid.uuid4().hex[:8]}",
        'owner_id': str(owner_id),
        'owner_name': str(owner_name),
        'tier_id': spec['id'],
        'tier': spec['tier'],
        'name': f"{spec['name']}",
        'weapon': spec['weapon'],
        'skin': spec['skin'],
        'x': float(owner_x) - 1.5,
        'z': float(owner_z) - 1.5,
        'vx': 0.0,
        'vz': 0.0,
        'angle': 0.0,
        'hp': spec['max_hp'],
        'max_hp': spec['max_hp'],
        'armor': spec['armor'],
        'damage': spec['damage'],
        'rate': spec['rate'],
        'range': spec['range'],
        'ammo': spec['mag'],
        'mag': spec['mag'],
        'reserve': spec['mag'] * 3,
        'reload_time': spec['reload'],
        'reloading_until': 0.0,
        'next_shot': 0.0,
        'status': 'active',  # 'active', 'recovering'
        'recovery_until_utc': 0.0,
        'target_aim_x': None,
        'target_aim_z': None,
        'command_lease_until': 0.0,
        'last_owner_fire_seq': 0,
        'slot_index': int(kwargs.get('slot_index', 0)),
    }


def update_soldier(*args, **kwargs):
    """Updates companion positioning, formation following, and cooperative firing."""
    if len(args) == 4:
        # Called as: update_soldier(game, soldier, dt, now)
        game, soldier, dt, now = args
        owner = game.players.get(soldier.get('owner_id'))
    elif len(args) >= 5:
        # Called as: update_soldier(soldier, owner, game, dt, now)
        soldier, owner, game, dt, now = args[:5]
    else:
        return

    if not soldier or not owner:
        return

    # Companions do not gain ammunition from roster toggles or upgrades.  A
    # depleted companion is resupplied only after both it and its owner have
    # remained in the safe zone for five seconds.
    if soldier.get('ammo', 0) <= 0 and soldier.get('reserve', 0) <= 0:
        if safe_zone_at(owner['x'], owner['z']) and safe_zone_at(soldier['x'], soldier['z']):
            if now - soldier.get('safe_resupply_at', now) >= 5:
                soldier['ammo'] = soldier['mag']; soldier['reserve'] = soldier['mag'] * 3
                soldier['safe_resupply_at'] = now
                game.events.append({'type': 'soldier_resupply', 'owner': owner['id'], 'soldier_id': soldier['id'], 'x': soldier['x'], 'z': soldier['z']})
        else:
            soldier['safe_resupply_at'] = now

    if soldier.get('status') == 'recovering':
        if time.time() >= float(soldier.get('recovery_until_utc') or 0):
            soldier['status'] = 'active'
            soldier['hp'] = soldier['max_hp']
            soldier['ammo'] = soldier['mag']
            soldier['recovery_until_utc'] = 0.0
            soldier['reloading_until'] = 0.0
            soldier['next_shot'] = 0.0
            soldier['x'] = owner['x'] - 1.5
            soldier['z'] = owner['z'] - 1.5
        else:
            return

    if owner.get('hp', 0) <= 0:
        return

    # Check reload completion
    if soldier['reloading_until'] > 0 and now >= soldier['reloading_until']:
        soldier['reloading_until'] = 0.0
        needed = soldier['mag'] - soldier['ammo']
        to_load = min(needed, soldier['reserve'])
        soldier['ammo'] += to_load
        soldier['reserve'] -= to_load

    # 1. Formation Movement: five distinct positions behind the owner.
    owner_angle = owner.get('angle', 0.0)
    slot = int(soldier.get('slot_index', 0)) % 5
    lateral = (slot - 2) * 1.25
    depth = 2.6 + (abs(slot - 2) * .45)
    behind_x = owner['x'] - math.sin(owner_angle) * depth + math.cos(owner_angle) * lateral
    behind_z = owner['z'] - math.cos(owner_angle) * depth - math.sin(owner_angle) * lateral

    dist_to_slot = math.hypot(behind_x - soldier['x'], behind_z - soldier['z'])
    dist_to_owner = math.hypot(owner['x'] - soldier['x'], owner['z'] - soldier['z'])

    # Hysteresis speed calculation
    speed = 0.0
    if dist_to_slot > 1.2:
        if dist_to_slot > 6.0:
            speed = 9.0  # sprint to catch up
        elif dist_to_slot > 3.0:
            speed = 6.2  # running
        else:
            speed = 4.2  # walking

    if speed > 0:
        dir_x = (behind_x - soldier['x']) / max(0.001, dist_to_slot)
        dir_z = (behind_z - soldier['z']) / max(0.001, dist_to_slot)

        # Collision with static structures
        next_x = soldier['x'] + dir_x * speed * dt
        next_z = soldier['z'] + dir_z * speed * dt

        if free(next_x, next_z, 0.4):
            soldier['x'] = next_x
            soldier['z'] = next_z
            soldier['angle'] = math.atan2(dir_x, dir_z)

    # 2. Autonomous fire support. Companions never fire from a safe zone, at an
    # ally/owner, through a wall, or while straying too far from their owner.
    tethered = dist_to_owner <= 24.0
    target = None
    if tethered and not safe_zone_at(owner['x'], owner['z']) and not safe_zone_at(soldier['x'], soldier['z']):
        candidates = []
        for e in targets(game):
            if e['id'] == owner['id'] or e.get('hp', 0) <= 0 or safe_zone_at(e['x'], e['z']):
                continue
            # Hostile NPCs/bosses and PvP-legal players are valid. Owner and
            # alliance members with friendly fire disabled never become targets.
            if (not (e.get('zombie') or e.get('boss') or e.get('id') in game.players)
                    or e.get('protected_until', 0) > now
                    or (e.get('alliance_id') and e.get('alliance_id') == owner.get('alliance_id'))
                    or allied_fire_disabled(game, owner, e)):
                continue
            distance = math.hypot(e['x'] - soldier['x'], e['z'] - soldier['z'])
            if distance <= soldier['range'] + 12 and wall_distance(soldier['x'], soldier['z'], e['x'], e['z']) > .95:
                candidates.append((distance, e))
        if candidates:
            target = min(candidates, key=lambda item: item[0])[1]
            soldier['target_aim_x'], soldier['target_aim_z'] = target['x'], target['z']

    # Close the last bounded gap only with clear LOS. A blocked target falls
    # back to formation instead of repeatedly pressing into a wall.
    if target:
        target_distance = math.hypot(target['x'] - soldier['x'], target['z'] - soldier['z'])
        stop_range = soldier['range'] * .85
        if target_distance > stop_range and target_distance > .01:
            ux, uz = (target['x'] - soldier['x']) / target_distance, (target['z'] - soldier['z']) / target_distance
            nx, nz = soldier['x'] + ux * min(5.5 * dt, target_distance - stop_range), soldier['z'] + uz * min(5.5 * dt, target_distance - stop_range)
            if free(nx, nz, .4):
                soldier['x'], soldier['z'], soldier['angle'] = nx, nz, math.atan2(ux, uz)

    if target and soldier['reloading_until'] <= 0:
        if soldier['ammo'] <= 0:
            # Trigger reload
            if soldier['reserve'] > 0:
                soldier['reloading_until'] = now + soldier['reload_time']
        elif now >= soldier['next_shot']:
            aim_x = soldier.get('target_aim_x')
            aim_z = soldier.get('target_aim_z')
            if aim_x is not None and aim_z is not None:
                dist = math.hypot(aim_x - soldier['x'], aim_z - soldier['z'])
                if dist <= soldier['range'] and not safe_zone_at(soldier['x'], soldier['z']):
                    # Turn to aim point and fire
                    shoot_angle = math.atan2(aim_x - soldier['x'], aim_z - soldier['z'])
                    soldier['angle'] = shoot_angle
                    soldier['ammo'] -= 1
                    soldier['next_shot'] = now + soldier['rate']

                    # Direct hitscan raycast matching combat.py
                    dx = math.sin(shoot_angle)
                    dz = math.cos(shoot_angle)

                    reach = soldier['range'] * wall_distance(soldier['x'], soldier['z'], soldier['x'] + dx * soldier['range'], soldier['z'] + dz * soldier['range'])
                    target, nearest = None, reach
                    for e in targets(game):
                        if e['id'] == owner['id'] or e.get('hp', 0) <= 0 or allied_fire_disabled(game, owner, e):
                            continue
                        ex, ez = e['x'] - soldier['x'], e['z'] - soldier['z']
                        along = ex * dx + ez * dz
                        if 0 < along < nearest and abs(ex * dz - ez * dx) < 0.6 and wall_distance(soldier['x'], soldier['z'], e['x'], e['z']) > 0.95:
                            target, nearest = e, along

                    game.events.append({
                        'type': 'shot',
                        'kind': 'bullet',
                        'weapon': soldier['weapon'],
                        'owner': owner['id'],
                        'soldier_id': soldier['id'],
                        'x': soldier['x'],
                        'z': soldier['z'],
                        'tx': soldier['x'] + dx * nearest,
                        'tz': soldier['z'] + dz * nearest,
                        'hit': bool(target)
                    })
                    if target:
                        hurt(game, target, soldier['damage'], owner, now, source_name=f"{soldier['name']}")

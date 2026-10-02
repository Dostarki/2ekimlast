import math
import random
from world import enemy_move, safe_zone_at, wall_distance
from enemy_types import ENEMY_TYPES
from enemy_damage import damage_player, apply_status, dismiss_hive
from enemy_attacks import update_flame, launch_swarm, update_swarms
from enemy_navigation import chase
from population import actor_grid, near

ACTIVE_RANGE = 90


def wander(enemy, dt, now, pack=None):
    if pack:
        cx = sum(e['x'] for e in pack)/len(pack)
        cz = sum(e['z'] for e in pack)/len(pack)
        angle = math.atan2(cx-enemy['x'], cz-enemy['z']) if math.hypot(cx-enemy['x'], cz-enemy['z']) > 3 else math.sin(int(now/5)+int(pack[0]['variant']))*math.pi
        enemy['mode'] = 'wander'; enemy['angle'] = angle
        enemy_move(enemy, math.sin(angle)*.85*dt, math.cos(angle)*.85*dt)
        return
    if enemy.get('mode') not in ('idle', 'wander') or now > enemy.get('wander_until', 0):
        enemy['mode'] = 'wander' if random.random() > .25 else 'idle'
        enemy['angle'] = random.uniform(0, math.tau); enemy['wander_until'] = now+random.uniform(2.5, 6)
    if enemy['mode'] == 'wander':
        before = (enemy['x'], enemy['z'])
        enemy_move(enemy, math.sin(enemy['angle'])*.55*dt, math.cos(enemy['angle'])*.55*dt)
        if math.hypot(enemy['x']-before[0], enemy['z']-before[1]) < .001:
            enemy['angle'] += 1.4; enemy['wander_until'] = now+1.5


def update_zombies(game, living, dt, now):
    game.path_budget = 2
    packs, alerts = {}, {}
    for e in game.zombies.values():
        if e.get('pack') and e['hp'] > 0:
            packs.setdefault(e['pack'], []).append(e)
    eligible = [p for p in living if not p.get('awaiting_input', False) and p['hp'] > 0 and not safe_zone_at(p['x'], p['z'])]
    living_grid = actor_grid(living, ACTIVE_RANGE)
    eligible_grid = actor_grid(eligible, ACTIVE_RANGE)
    for key, pack in packs.items():
        candidates = [p for p in near(eligible_grid, ACTIVE_RANGE, pack[0]['x'], pack[0]['z']) if any(math.hypot(p['x']-e['x'], p['z']-e['z']) <= 22 and wall_distance(e['x'], e['z'], p['x'], p['z']) > .98 for e in pack)]
        if candidates:
            alerts[key] = min(candidates, key=lambda p: math.hypot(p['x']-pack[0]['x'], p['z']-pack[0]['z']))
    for zid, enemy in list(game.zombies.items()):
        remembered = game.players.get(enemy.get('target_id')) or game.soldiers.get(enemy.get('target_id'))
        if remembered and (remembered['hp'] <= 0 or remembered.get('awaiting_input', False) or safe_zone_at(remembered['x'], remembered['z'])):
            remembered = None
        if enemy['hp'] <= 0:
            game.zombies.pop(zid, None); dismiss_hive(game, zid); continue
        # Zombies with nobody nearby stay dormant; this keeps the tick cheap with a large global population.
        if not remembered and not near(living_grid, ACTIVE_RANGE, enemy['x'], enemy['z']):
            continue
        kind = enemy.get('enemy_type', 'normal'); profile = ENEMY_TYPES[kind]
        if kind == 'immolator' and update_flame(game, enemy, living, now):
            continue
        candidates = [] if remembered else [p for p in near(eligible_grid, ACTIVE_RANGE, enemy['x'], enemy['z']) if p['hp'] > 0 and math.hypot(p['x']-enemy['x'], p['z']-enemy['z']) <= profile['detection'] and wall_distance(enemy['x'], enemy['z'], p['x'], p['z']) > .98]
        target = remembered or (min(candidates, key=lambda p: (p['x']-enemy['x'])**2+(p['z']-enemy['z'])**2) if candidates else alerts.get(enemy.get('pack')))
        if not target or target['hp'] <= 0:
            enemy['target_id'] = ''
            wander(enemy, dt, now, packs.get(enemy.get('pack'))); continue
        if enemy.get('target_id') != target['id']:
            game.events.append({'type': 'enemy_sound', 'action': 'aggro', 'enemy_type': kind, 'owner': zid, 'x': enemy['x'], 'z': enemy['z']})
        enemy['target_id'] = target['id']
        dx, dz = target['x']-enemy['x'], target['z']-enemy['z']; distance = math.hypot(dx, dz)
        enemy['mode'] = 'attack'; enemy['angle'] = math.atan2(dx, dz)
        visible = wall_distance(enemy['x'], enemy['z'], target['x'], target['z']) > .98
        if kind == 'immolator' and distance <= profile['flame_range'] and visible and now-enemy['last_special'] >= 3.2:
            enemy['last_special'] = now; enemy['windup_until'] = now+.45; enemy['mode'] = 'windup'; continue
        if kind == 'hive' and distance <= 22 and visible:
            launch_swarm(game, enemy, target, now)
            if distance > 5:
                enemy['mode'] = 'swarm'; continue
        reach = 1.6 if kind == 'hellhound' else 1.35
        if distance > reach:
            chase(game, enemy, target, enemy.get('speed', profile['speed']), dt, now)
        elif visible and now-enemy['last_attack'] >= (1.25 if kind == 'hellhound' else 1.0):
            enemy['last_attack'] = now; enemy['attack_until'] = now+.28
            game.events.append({'type': 'enemy_sound', 'action': 'attack', 'enemy_type': kind, 'owner': zid, 'x': enemy['x'], 'z': enemy['z']})
            if damage_player(game, target, profile['damage'], profile['name'], now) and kind == 'hellhound':
                apply_status(target, 'bleeding', zid, 'Hellhound · Bleeding', now)
    update_swarms(game, dt, now)

import math
import uuid
from world import enemy_move, safe_zone_at, wall_distance
from enemy_damage import apply_status, damage_player, dismiss_hive
from enemy_types import ENEMY_TYPES


def update_flame(game, enemy, living, now):
    if enemy.get('windup_until', 0):
        enemy['mode'] = 'windup'
        if now >= enemy['windup_until']:
            enemy['windup_until'] = 0
            enemy['flame_until'] = now+1.2
            game.events.append({'type': 'enemy_sound', 'action': 'attack', 'enemy_type': 'immolator', 'owner': enemy['id'], 'x': enemy['x'], 'z': enemy['z']})
        return True
    if now >= enemy.get('flame_until', 0):
        return False
    enemy['mode'] = 'flame'
    if now-enemy['last_flame'] < .15:
        return True
    enemy['last_flame'] = now
    dx, dz = math.sin(enemy['angle']), math.cos(enemy['angle'])
    reach_limit = ENEMY_TYPES['immolator']['flame_range']
    reach = reach_limit*wall_distance(enemy['x'], enemy['z'], enemy['x']+dx*reach_limit, enemy['z']+dz*reach_limit)
    game.events.append({'type': 'enemy_attack', 'kind': 'flame', 'owner': enemy['id'], 'x': enemy['x'], 'z': enemy['z'],
                        'tx': enemy['x']+dx*reach, 'tz': enemy['z']+dz*reach})
    for p in living:
        ex, ez = p['x']-enemy['x'], p['z']-enemy['z']
        along = ex*dx+ez*dz
        if 0 < along <= reach_limit and math.hypot(ex, ez) <= reach_limit and abs(ex*dz-ez*dx) < .6+along*.10 and wall_distance(enemy['x'], enemy['z'], p['x'], p['z']) > .98:
            damage_player(game, p, 6, 'Immolator', now)
    return True


def launch_swarm(game, enemy, target, now):
    profile = ENEMY_TYPES['hive']
    active = sum(s['owner'] == enemy['id'] for s in game.swarms)
    if now-enemy['last_special'] < profile['swarm_cooldown'] or active >= 6:
        return
    enemy['last_special'] = now
    enemy['attack_until'] = now+.8
    for i in range(min(profile['swarm_count'], 6-active)):
        game.swarms.append({'id': uuid.uuid4().hex[:10], 'owner': enemy['id'], 'target': target['id'],
                            'x': enemy['x'], 'z': enemy['z'], 'until': now+8, 'last_hit': 0, 'spread': (i-1)*.6})
    game.events.append({'type': 'enemy_sound', 'action': 'attack', 'enemy_type': 'hive', 'owner': enemy['id'], 'x': enemy['x'], 'z': enemy['z']})


def update_swarms(game, dt, now):
    for swarm in list(game.swarms):
        owner = game.zombies.get(swarm['owner'])
        if not owner or owner['hp'] <= 0:
            dismiss_hive(game, swarm['owner'])
            continue
        target = game.players.get(swarm['target'])
        if now >= swarm['until'] or not target or target['hp'] <= 0 or math.hypot(target['x']-owner['x'], target['z']-owner['z']) > 32:
            game.swarms.remove(swarm)
            continue
        dx, dz = target['x']-swarm['x'], target['z']-swarm['z']
        distance = math.hypot(dx, dz)
        if distance > 3:
            lateral = swarm.get('spread', 0)
            dx, dz = dx-dz/distance*lateral, dz+dx/distance*lateral
        step = min(distance, ENEMY_TYPES['hive']['swarm_speed']*dt)
        norm = max(.001, math.hypot(dx, dz))
        enemy_move(swarm, dx/norm*step, dz/norm*step)
        distance = math.hypot(target['x']-swarm['x'], target['z']-swarm['z'])
        if not safe_zone_at(target['x'], target['z']) and distance < 1.3 and now-swarm['last_hit'] >= .8 and wall_distance(swarm['x'], swarm['z'], target['x'], target['z']) > .98:
            swarm['last_hit'] = now
            if damage_player(game, target, 4, 'Hive', now):
                apply_status(target, 'poison', owner['id'], 'Hive Poison', now)

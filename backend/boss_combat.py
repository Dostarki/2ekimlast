import math
import uuid
from world import enemy_free, safe_zone_at, wall_distance
from enemy_damage import damage_player

def hostile_targets(game):
    return list(game.players.values()) + [s for s in game.soldiers.values() if s.get('status') == 'active']


def safe_landing(x, z, radius, valid=lambda _x, _z: True):
    for distance in [0, 3, 6, 9, 12, 18]:
        for i in range(12):
            px, pz = x+math.sin(i*math.tau/12)*distance, z+math.cos(i*math.tau/12)*distance
            if valid(px, pz) and enemy_free(px, pz, radius):
                return px, pz
    return None


def area_damage(game, boss, x, z, radius, damage, now, kind='impact'):
    game.events.append({'type': 'boss_impact', 'owner': boss['id'], 'kind': kind, 'x': x, 'z': z, 'r': radius})
    for player in hostile_targets(game):
        distance = math.hypot(player['x']-x, player['z']-z)
        if distance < radius and wall_distance(x, z, player['x'], player['z']) > .95:
            damage_player(game, player, round(damage*(1-.35*distance/radius)), boss['name'], now)


def line_damage(game, boss, tx, tz, reach, width, damage, now, kind):
    dx, dz = tx-boss['x'], tz-boss['z']; length = max(.01, math.hypot(dx, dz)); dx, dz = dx/length, dz/length
    reach *= wall_distance(boss['x'], boss['z'], boss['x']+dx*reach, boss['z']+dz*reach)
    game.events.append({'type': 'boss_beam', 'kind': kind, 'owner': boss['id'], 'x': boss['x'], 'z': boss['z'], 'tx': boss['x']+dx*reach, 'tz': boss['z']+dz*reach, 'height': boss['height']*.55})
    for p in hostile_targets(game):
        ex, ez = p['x']-boss['x'], p['z']-boss['z']; along = ex*dx+ez*dz
        if 0 < along < reach and abs(ex*dz-ez*dx) < width and wall_distance(boss['x'], boss['z'], p['x'], p['z']) > .95:
            damage_player(game, p, damage, boss['name'], now)


def launch_projectile(game, boss, kind, tx, tz, spread=0):
    angle = math.atan2(tx-boss['x'], tz-boss['z'])+spread
    dx, dz = math.sin(angle), math.cos(angle)
    game.boss_projectiles.append({'id': uuid.uuid4().hex[:12], 'owner': boss['id'], 'kind': kind,
        'x': boss['x']+dx*(boss['radius']+1), 'z': boss['z']+dz*(boss['radius']+1), 'dx': dx, 'dz': dz,
        'speed': 21 if kind == 'rocket' else 16, 'remaining': 55, 'y': 1.6})


def update_boss_hazards(game, dt, now):
    for shot in list(game.boss_projectiles):
        boss = game.bosses[shot['owner']]
        if boss['hp'] <= 0:
            game.boss_projectiles.remove(shot); continue
        step = min(shot['remaining'], shot['speed']*dt)
        x, z = shot['x'], shot['z']; nx, nz = x+shot['dx']*step, z+shot['dz']*step
        fraction = wall_distance(x, z, nx, nz)
        shot['x'], shot['z'] = x+(nx-x)*max(0, fraction-.015), z+(nz-z)*max(0, fraction-.015)
        shot['remaining'] -= step
        impact = fraction < 1 or shot['remaining'] <= 0
        for p in hostile_targets(game):
            if p['hp'] <= 0 or p['awaiting_input'] or safe_zone_at(p['x'], p['z']):
                continue
            ex, ez = p['x']-x, p['z']-z; along = max(0, min(step*fraction, ex*shot['dx']+ez*shot['dz']))
            if math.hypot(ex-along*shot['dx'], ez-along*shot['dz']) < 1.15:
                shot['x'], shot['z'] = x+along*shot['dx'], z+along*shot['dz']; impact = True; break
        if impact:
            area_damage(game, boss, shot['x'], shot['z'], 3.4, 30 if shot['kind'] == 'rocket' else 22, now, shot['kind'])
            if shot['kind'] == 'web':
                for p in hostile_targets(game):
                    if p['hp'] > 0 and not p['awaiting_input'] and not safe_zone_at(p['x'], p['z']) and p['protected_until'] <= now and math.hypot(p['x']-shot['x'], p['z']-shot['z']) < 3.4 and wall_distance(shot['x'], shot['z'], p['x'], p['z']) > .95:
                        p['statuses']['webbed'] = {'source': boss['id'], 'name': boss['name'], 'until': now+4, 'next_tick': now+1, 'damage': 4}
            game.boss_projectiles.remove(shot)
    for zone in list(game.boss_zones):
        boss = game.bosses[zone['owner']]
        if now >= zone['until'] or boss['hp'] <= 0:
            game.boss_zones.remove(zone); continue
        if now >= zone['next_tick']:
            zone['next_tick'] = now+.6
            for p in hostile_targets(game):
                if math.hypot(p['x']-zone['x'], p['z']-zone['z']) < zone['r'] and wall_distance(zone['x'], zone['z'], p['x'], p['z']) > .95:
                    damage_player(game, p, 9, boss['name'], now)

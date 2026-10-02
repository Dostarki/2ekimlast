import math
import uuid
from world import enemy_free, safe_zone_at, wall_distance
from enemy_damage import damage_player
from damage_types import AreaDamage, DamageContext

def hostile_targets(game):
    return list(game.players.values()) + [s for s in game.soldiers.values() if s.get('status') == 'active']


def safe_landing(x, z, radius, valid=lambda _x, _z: True):
    for distance in [0, 3, 6, 9, 12, 18]:
        for i in range(12):
            px, pz = x+math.sin(i*math.tau/12)*distance, z+math.cos(i*math.tau/12)*distance
            if valid(px, pz) and enemy_free(px, pz, radius):
                return px, pz
    return None


def area_damage(game, context: DamageContext, area: AreaDamage):
    boss, now = context.source, context.now
    x, z = area.position
    game.events.append({'type': 'boss_impact', 'owner': boss['id'], 'kind': context.kind, 'x': x, 'z': z, 'r': area.radius})
    for player in hostile_targets(game):
        distance = math.hypot(player['x']-x, player['z']-z)
        if distance < area.radius and wall_distance(x, z, player['x'], player['z']) > .95:
            damage_player(game, player, round(area.amount*(1-.35*distance/area.radius)), boss['name'], now)


def line_damage(game, context, line):
    boss, now = context.source, context.now
    tx, tz = line.target
    dx, dz = tx-boss['x'], tz-boss['z']; length = max(.01, math.hypot(dx, dz)); dx, dz = dx/length, dz/length
    reach = line.reach * wall_distance(boss['x'], boss['z'], boss['x']+dx*line.reach, boss['z']+dz*line.reach)
    game.events.append({'type': 'boss_beam', 'kind': context.kind, 'owner': boss['id'], 'x': boss['x'], 'z': boss['z'], 'tx': boss['x']+dx*reach, 'tz': boss['z']+dz*reach, 'height': boss['height']*.55})
    for p in hostile_targets(game):
        ex, ez = p['x']-boss['x'], p['z']-boss['z']; along = ex*dx+ez*dz
        if 0 < along < reach and abs(ex*dz-ez*dx) < line.width and wall_distance(boss['x'], boss['z'], p['x'], p['z']) > .95:
            damage_player(game, p, line.amount, boss['name'], now)


def launch_projectile(game, boss, kind, tx, tz, spread=0):
    angle = math.atan2(tx-boss['x'], tz-boss['z'])+spread
    dx, dz = math.sin(angle), math.cos(angle)
    game.boss_projectiles.append({'id': uuid.uuid4().hex[:12], 'owner': boss['id'], 'kind': kind,
        'x': boss['x']+dx*(boss['radius']+1), 'z': boss['z']+dz*(boss['radius']+1), 'dx': dx, 'dz': dz,
        'speed': 21 if kind == 'rocket' else 16, 'remaining': 55, 'y': 1.6})


def _eligible_target(player):
    # Companions are active hostile targets but have no player-input handshake.
    return player['hp'] > 0 and not player.get('awaiting_input', False) and not safe_zone_at(player['x'], player['z'])


def _projectile_collision(game, shot, segment):
    x, z, distance = segment
    for player in hostile_targets(game):
        if not _eligible_target(player):
            continue
        ex, ez = player['x'] - x, player['z'] - z
        along = max(0, min(distance, ex * shot['dx'] + ez * shot['dz']))
        if math.hypot(ex - along * shot['dx'], ez - along * shot['dz']) < 1.15:
            shot['x'], shot['z'] = x + along * shot['dx'], z + along * shot['dz']
            return True
    return False


def _advance_projectile(game, shot, dt):
    step = min(shot['remaining'], shot['speed'] * dt)
    x, z = shot['x'], shot['z']
    nx, nz = x + shot['dx'] * step, z + shot['dz'] * step
    fraction = wall_distance(x, z, nx, nz)
    shot['x'], shot['z'] = x + (nx - x) * max(0, fraction - .015), z + (nz - z) * max(0, fraction - .015)
    shot['remaining'] -= step
    collision = _projectile_collision(game, shot, (x, z, step * fraction))
    return collision or fraction < 1 or shot['remaining'] <= 0


def _within_visible_area(player, position, radius):
    x, z = position
    return (math.hypot(player['x'] - x, player['z'] - z) < radius
            and wall_distance(x, z, player['x'], player['z']) > .95)


def _apply_web(game, boss, shot, now):
    for player in hostile_targets(game):
        if not _eligible_target(player) or player.get('protected_until', 0) > now:
            continue
        if _within_visible_area(player, (shot['x'], shot['z']), 3.4):
            player.setdefault('statuses', {})['webbed'] = {
                'source': boss['id'], 'name': boss['name'], 'until': now + 4, 'next_tick': now + 1, 'damage': 4}


def _update_projectile(game, shot, dt, now):
    boss = game.bosses[shot['owner']]
    if boss['hp'] <= 0:
        game.boss_projectiles.remove(shot)
        return
    if not _advance_projectile(game, shot, dt):
        return
    context = DamageContext(source=boss, now=now, kind=shot['kind'])
    area = AreaDamage(position=(shot['x'], shot['z']), radius=3.4,
                      amount=30 if shot['kind'] == 'rocket' else 22)
    area_damage(game, context, area)
    if shot['kind'] == 'web':
        _apply_web(game, boss, shot, now)
    game.boss_projectiles.remove(shot)


def _update_zone(game, zone, now):
    boss = game.bosses[zone['owner']]
    if now >= zone['until'] or boss['hp'] <= 0:
        game.boss_zones.remove(zone)
        return
    if now < zone['next_tick']:
        return
    zone['next_tick'] = now + .6
    for player in hostile_targets(game):
        if _within_visible_area(player, (zone['x'], zone['z']), zone['r']):
            damage_player(game, player, 9, boss['name'], now)


def update_boss_hazards(game, dt, now):
    for shot in list(game.boss_projectiles):
        _update_projectile(game, shot, dt, now)
    for zone in list(game.boss_zones):
        _update_zone(game, zone, now)

import math
import uuid
from world import enemy_free, safe_zone_at, wall_distance
from boss_catalog import BOSS_TYPES, create_boss, boss_snapshot
from boss_combat import safe_landing, area_damage, line_damage, launch_projectile, update_boss_hazards
from damage_types import AreaDamage, DamageContext, LineDamage

ROTATIONS = {'hansel': ['laser', 'rockets', 'leap'], 'symbiote': ['web', 'blink', 'slash'],
             'xenomorph': ['leap', 'claw', 'bite', 'tail'], 'ash_titan': ['quake', 'lava', 'slam']}
RANGES = {'laser': 50, 'rockets': 50, 'leap': 48, 'web': 45, 'blink': 40, 'slash': 6, 'claw': 6, 'bite': 4.5, 'tail': 12, 'quake': 15, 'lava': 45, 'slam': 6}
RADII = {'leap': 7, 'slash': 6, 'claw': 6, 'bite': 4.5, 'tail': 2, 'quake': 14, 'lava': 4, 'slam': 6, 'blink': 4, 'laser': 1.2, 'rockets': 3.4, 'web': 3.4}


def in_territory(boss, x, z):
    return math.hypot(x-boss['home_x'], z-boss['home_z']) <= boss['territory_radius']


def return_home(boss, dt):
    """Walk back after a target leaves; never snap or restore health."""
    home = {'x': boss['home_x'], 'z': boss['home_z']}
    distance = math.hypot(boss['x']-home['x'], boss['z']-home['z'])
    boss['target_id'] = ''
    if distance <= .2:
        boss.update(x=home['x'], z=home['z'], action='idle', y=0.)
        return
    boss['action'] = 'return'
    move_boss(boss, home, dt)


def begin_attack(boss, kind, target, now):
    x, z = target['x'], target['z']
    if kind in ('leap', 'blink'):
        landing = safe_landing(x, z, boss['radius'], lambda px, pz: in_territory(boss, px, pz))
        if not landing:
            boss['next_attack'] = now+1; return
        x, z = landing
    if kind in ('quake', 'slam', 'slash', 'claw', 'bite'):
        x, z = boss['x'], boss['z']
    windup = 1.1 if kind in ('laser', 'quake') else .85
    boss.update(action=f'windup_{kind}', action_until=now+windup,
                pending={'kind': kind, 'x': x, 'z': z, 'r': RADII[kind], 'from_x': boss['x'], 'from_z': boss['z'], 'start': now})


def _resolve_leap(game, context, pending):
    boss = context.source
    boss.update(x=pending['x'], z=pending['z'], y=0.)
    area_damage(game, context, AreaDamage(position=(boss['x'], boss['z']), radius=pending['r'],
        amount=62 if boss['boss_type'] == 'hansel' else 48))


def _resolve_blink(game, context, pending):
    boss = context.source
    game.events.append({'type': 'boss_impact', 'kind': 'liquid', 'owner': boss['id'], 'x': boss['x'], 'z': boss['z'], 'r': 3})
    boss.update(x=pending['x'], z=pending['z'])
    area_damage(game, DamageContext(source=boss, now=context.now, kind='liquid'),
                AreaDamage(position=(boss['x'], boss['z']), radius=4, amount=18))


def _resolve_line(game, context, pending):
    reach, width, damage = (50, 1.2, 40) if context.kind == 'laser' else (12, 1.7, 45)
    line_damage(game, context, LineDamage(target=(pending['x'], pending['z']), reach=reach, width=width, amount=damage))


def _resolve_projectiles(game, context, pending):
    kind = context.kind
    for spread in ([-.08, 0, .08] if kind == 'rockets' else [0]):
        launch_projectile(game, context.source, 'rocket' if kind == 'rockets' else kind,
                          pending['x'], pending['z'], spread)


def _resolve_lava(game, context, pending):
    boss, now = context.source, context.now
    for dx, dz in [(0, 0), (6, 0), (-3, 5)]:
        x, z = pending['x'] + dx, pending['z'] + dz
        if enemy_free(x, z):
            game.boss_zones.append({'id': uuid.uuid4().hex[:10], 'owner': boss['id'], 'x': x, 'z': z, 'r': 4, 'until': now+8, 'next_tick': now})
            game.events.append({'type': 'boss_impact', 'kind': 'lava', 'owner': boss['id'], 'x': x, 'z': z, 'r': 4})


def _resolve_melee(game, context, pending):
    boss = context.source
    damage = {'quake': 42, 'slam': 50, 'slash': 38, 'claw': 30, 'bite': 55}[context.kind]
    area_damage(game, context, AreaDamage(position=(boss['x'], boss['z']), radius=pending['r'], amount=damage))


ATTACK_HANDLERS = {'leap': _resolve_leap, 'blink': _resolve_blink, 'laser': _resolve_line,
                   'tail': _resolve_line, 'rockets': _resolve_projectiles, 'web': _resolve_projectiles,
                   'lava': _resolve_lava}
TRAVEL_STATES = {'leap': ('leap', 1.1), 'blink': ('liquid', .45)}


def resolve_attack(game, boss, now):
    pending = boss['pending']
    kind = pending['kind']
    travel = TRAVEL_STATES.get(kind)
    if travel and boss['action'] != travel[0]:
        boss.update(action=travel[0], action_until=now + travel[1])
        pending['start'] = now
        return
    context = DamageContext(source=boss, now=now, kind=kind)
    ATTACK_HANDLERS.get(kind, _resolve_melee)(game, context, pending)
    boss.update(action=kind, action_until=now+.4, pending=None,
                next_attack=now+(2.2 if boss['boss_type'] == 'xenomorph' else 3.2))


def move_boss(boss, target, dt):
    dx, dz = target['x']-boss['x'], target['z']-boss['z']; d = max(.01, math.hypot(dx, dz))
    step = min(d, BOSS_TYPES[boss['boss_type']]['speed']*dt)
    nx, nz = boss['x']+dx/d*step, boss['z']+dz/d*step
    # A legacy or obstructed actor may already be outside its arena.  Let it
    # walk inward, but never take another step farther from home.
    current_home_distance = math.hypot(boss['x']-boss['home_x'], boss['z']-boss['home_z'])
    next_home_distance = math.hypot(nx-boss['home_x'], nz-boss['home_z'])
    if not in_territory(boss, nx, nz) and next_home_distance >= current_home_distance:
        return
    if enemy_free(nx, nz, boss['radius']):
        boss.update(x=nx, z=nz)
    elif enemy_free(nx, boss['z'], boss['radius']):
        boss['x'] = nx
    elif enemy_free(boss['x'], nz, boss['radius']):
        boss['z'] = nz


def _eligible_targets(game):
    companions = [soldier for soldier in game.soldiers.values() if soldier.get('status') == 'active']
    return [player for player in [*game.players.values(), *companions]
            if player['hp'] > 0 and not player.get('awaiting_input', False)
            and not safe_zone_at(player['x'], player['z'])]


def _advance_leap(boss, dt, now):
    pending = boss['pending']
    progress = min(1, (now - pending['start']) / 1.1)
    nx = pending['from_x'] + (pending['x'] - pending['from_x']) * progress
    nz = pending['from_z'] + (pending['z'] - pending['from_z']) * progress
    if not in_territory(boss, nx, nz):
        boss.update(pending=None, y=0.)
        return_home(boss, dt)
        return False
    boss.update(x=nx, z=nz, y=math.sin(progress * math.pi) * 9)
    return True


def _update_pending(game, boss, eligible, dt, now):
    target = next((player for player in eligible if player['id'] == boss['target_id']), None)
    if not target or not in_territory(boss, target['x'], target['z']):
        boss.update(pending=None, action_until=now, y=0.)
        return_home(boss, dt)
        return
    if boss['action'] == 'leap' and not _advance_leap(boss, dt, now):
        return
    if now >= boss['action_until']:
        resolve_attack(game, boss, now)


def _select_target(boss, eligible):
    remembered = next((p for p in eligible if p['id'] == boss['target_id']
                       and in_territory(boss, p['x'], p['z'])), None)
    if remembered:
        return remembered
    nearby = [p for p in eligible if in_territory(boss, p['x'], p['z'])
              and math.hypot(p['x']-boss['x'], p['z']-boss['z']) <= BOSS_TYPES[boss['boss_type']]['detection']
              and wall_distance(boss['x'], boss['z'], p['x'], p['z']) > .95]
    return min(nearby, key=lambda p: math.hypot(p['x']-boss['x'], p['z']-boss['z'])) if nearby else None


def _choose_attack(boss, target, distance, now):
    rotation = ROTATIONS[boss['boss_type']]
    for offset in range(len(rotation)):
        index = (boss['attack_index'] + offset) % len(rotation)
        kind = rotation[index]
        visible = wall_distance(boss['x'], boss['z'], target['x'], target['z']) > .95
        if distance <= RANGES[kind] and (visible or kind in TRAVEL_STATES):
            boss['attack_index'] = (index + 1) % len(rotation)
            begin_attack(boss, kind, target, now)
            break


def _update_pursuit(boss, eligible, dt, now):
    target = _select_target(boss, eligible)
    boss['target_id'] = target['id'] if target else ''
    if not target:
        return_home(boss, dt)
        return
    distance = math.hypot(target['x'] - boss['x'], target['z'] - boss['z'])
    boss['angle'] = math.atan2(target['x'] - boss['x'], target['z'] - boss['z'])
    if now < boss['action_until']:
        return
    if now >= boss['next_attack']:
        _choose_attack(boss, target, distance, now)
    if not boss['pending']:
        boss['action'] = 'chase'
        if distance > boss['radius'] + 1.2:
            move_boss(boss, target, dt)


def _update_boss(game, key, boss, eligible, dt, now):
    if boss['hp'] <= 0:
        if boss['respawn_at'] and now >= boss['respawn_at']:
            game.bosses[key] = create_boss(boss['boss_type'], boss['generation'] + 1)
            game.events.append({'type': 'boss_spawn', 'name': boss['name'], 'owner': key})
        return
    if boss['pending']:
        _update_pending(game, boss, eligible, dt, now)
    else:
        _update_pursuit(boss, eligible, dt, now)


def update_bosses(game, dt, now):
    eligible = _eligible_targets(game)
    for key, boss in list(game.bosses.items()):
        _update_boss(game, key, boss, eligible, dt, now)
    update_boss_hazards(game, dt, now)

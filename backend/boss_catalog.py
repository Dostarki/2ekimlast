import random

BOSS_TYPES = {
    'hansel': {'name': 'HANSEL', 'subtitle': 'Mechanical Destruction', 'hp': 5000, 'radius': 3.0, 'height': 10, 'speed': 3.2, 'detection': 50, 'color': '#f3ae52', 'home': (80, 0), 'region': 'East Junction', 'abilities': ['Laser', 'Rocket Salvo', 'Giant Leap']},
    'symbiote': {'name': 'CRIMSON VENOM', 'subtitle': 'Symbiote Giant', 'hp': 6000, 'radius': 2.8, 'height': 11, 'speed': 4.5, 'detection': 50, 'color': '#eb6c80', 'home': (-80, 0), 'region': 'West Junction', 'abilities': ['Burning Web', 'Liquid Shift', 'Slash']},
    'xenomorph': {'name': 'XENOMORPH', 'subtitle': 'Hive Sovereign', 'hp': 10000, 'radius': 2.7, 'height': 9, 'speed': 6.2, 'detection': 50, 'color': '#94d6bf', 'home': (0, 80), 'region': 'South Junction', 'abilities': ['Long Leap', 'Claw', 'Bite', 'Tail Strike']},
    'ash_titan': {'name': 'ASH TITAN', 'subtitle': 'Underground Fury', 'hp': 8000, 'radius': 3.2, 'height': 12, 'speed': 3.0, 'detection': 50, 'color': '#f88b5c', 'home': (0, -80), 'region': 'North Junction', 'abilities': ['Earthquake', 'Lava Pools', 'Crushing Blow']},
}


def create_boss(kind, generation=1):
    p = BOSS_TYPES[kind]
    return {'id': f'boss-{kind}', 'boss_type': kind, 'boss': True, 'zombie': True,
            'name': p['name'], 'x': float(p['home'][0]), 'z': float(p['home'][1]), 'y': 0.,
            'angle': 0., 'hp': p['hp'], 'max_hp': p['hp'], 'radius': p['radius'], 'height': p['height'],
            'target_id': '', 'action': 'idle', 'action_until': 0., 'pending': None,
            # A boss owns a small, disjoint arena around its spawn.  Keeping this
            # on the actor also makes respawns and any future boss variants stable.
            'home_x': float(p['home'][0]), 'home_z': float(p['home'][1]), 'territory_radius': 38.,
            'next_attack': 0., 'attack_index': 0, 'respawn_at': 0., 'generation': generation}


def initial_bosses():
    return {f'boss-{kind}': create_boss(kind) for kind in BOSS_TYPES}


def boss_died(game, boss, now):
    if boss['respawn_at']:
        return
    boss.update(respawn_at=now+random.uniform(300, 600), pending=None, action='dead', action_until=0., y=0., target_id='')
    game.boss_projectiles[:] = [e for e in game.boss_projectiles if e['owner'] != boss['id']]
    game.boss_zones[:] = [e for e in game.boss_zones if e['owner'] != boss['id']]
    game.events.append({'type': 'boss_death', 'name': boss['name'], 'boss_type': boss['boss_type'], 'owner': boss['id'], 'x': boss['x'], 'z': boss['z']})


def boss_snapshot(boss, now):
    p = BOSS_TYPES[boss['boss_type']]
    keys = ['id', 'boss_type', 'name', 'x', 'z', 'y', 'angle', 'hp', 'max_hp', 'radius', 'height', 'action', 'generation']
    result = {k: round(boss[k], 3) if isinstance(boss[k], float) else boss[k] for k in keys}
    pending = boss['pending']
    if boss['hp'] <= 0:
        result['x'], result['z'] = p['home']
    result.update(color=p['color'], region=p['region'], subtitle=p['subtitle'], abilities=p['abilities'],
                  alive=boss['hp'] > 0, respawn_in=round(max(0, boss['respawn_at']-now), 1),
                  action_remaining=round(max(0, boss['action_until']-now), 2),
                  telegraph={k: pending[k] for k in ['kind', 'x', 'z', 'r']} if pending else None)
    return result

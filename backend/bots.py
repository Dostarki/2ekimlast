"""Server-controlled participants use the same movement, ammunition and damage rules."""
import math
import random
from collections import defaultdict
from enemy_navigation import path_to
from inventory import equip_weapon
from world import WEAPONS, free, wall_distance

FIRST = ('Ash', 'Raven', 'Mason', 'Ghost', 'Dylan', 'Iron', 'Noah', 'Frost', 'Logan', 'Scarlet', 'Ethan', 'Silver', 'Mia', 'Luna', 'Owen', 'Storm', 'Jade', 'Axel', 'Wren', 'Sable')
LAST = ('Walker', 'Fox', 'Ridge', 'Hunter', 'Wolf', 'Reed', 'Stone', 'Drake', 'Hawk', 'Rook', 'Cross', 'Vale', 'Knight', 'Blake', 'Wells', 'Cole', 'Gray', 'West', 'Lane', 'Rivers')


def nickname(game):
    used = {p['name'].casefold() for p in game.players.values()}
    choices = [a+b for a in FIRST for b in LAST if (a+b).casefold() not in used]
    return random.choice(choices) if choices else f'Nomad{random.randint(1000, 99999)}'


def remove_bot(game, player):
    game.players.pop(player['id'], None)
    game.projectiles[:] = [p for p in game.projectiles if p['owner'] != player['id']]
    game.fires[:] = [p for p in game.fires if p['owner'] != player['id']]


def balance_bots(game, now):
    if now < getattr(game, 'next_bot_balance', 0):
        return
    game.next_bot_balance = now+.25
    bots = [p for p in game.players.values() if p.get('bot')]
    wanted = game.settings['bot_count'] if getattr(game, 'local_simulation', False) else min(game.settings['bot_count'], 200-(len(game.players)-len(bots)))
    for p in bots[wanted:]:
        remove_bot(game, p)
    for _ in range(min(2, wanted-len(bots))):
        p = game.add_player({'name': nickname(game), 'weapon': 'glock18', 'skin': 'soldier',
                             'progress': {'unlocked_weapons': ['glock18', 'ak47', 'ak117', 'm4', 'shotgun']}}, None, bot=True)
        p['brain_at'] = now+random.random()*.3


def destination(game, p, target, now):
    if now > p.get('roam_until', 0) or math.hypot(p.get('roam_x', p['x'])-p['x'], p.get('roam_z', p['z'])-p['z']) < 3:
        p.update(roam_x=max(-720, min(720, round(p['x']/80)*80+random.choice([-80, 0, 80]))),
                 roam_z=max(-720, min(720, round(p['z']/80)*80+random.choice([-80, 0, 80]))), roam_until=now+random.uniform(8, 18))
    goal = target or {'x': p['roam_x'], 'z': p['roam_z']}
    if wall_distance(p['x'], p['z'], goal['x'], goal['z']) < .98:
        if now >= p.get('next_path', 0) and game.bot_path_budget > 0:
            game.bot_path_budget -= 1
            p['path'] = path_to(p, goal); p['next_path'] = now+2
        path = p.get('path', [])
        while path and math.hypot(path[0][0]-p['x'], path[0][1]-p['z']) < 1:
            path.pop(0)
        if path:
            return {'x': path[0][0], 'z': path[0][1]}
    return goal


def update_bot_grid(game, now):
    if now < getattr(game, 'bot_grid_at', 0):
        return
    game.bot_grid_at = now + .2
    game.bot_grid = defaultdict(list)
    for entity in [*game.players.values(), *game.zombies.values(), *game.bosses.values()]:
        if entity['hp'] > 0:
            game.bot_grid[(int(entity['x'] // 64), int(entity['z'] // 64))].append(entity)


def _target_eligible(player, entity, now):
    return (entity['id'] != player['id'] and entity['hp'] > 0
            and entity.get('protected_until', 0) <= now and not entity.get('awaiting_input', False)
            and math.hypot(entity['x'] - player['x'], entity['z'] - player['z']) < 48)


def select_bot_target(game, player, now):
    gx, gz = int(player['x'] // 64), int(player['z'] // 64)
    nearby = [entity for x in range(gx - 1, gx + 2) for z in range(gz - 1, gz + 2)
              for entity in game.bot_grid.get((x, z), []) if _target_eligible(player, entity, now)]
    nearby.sort(key=lambda entity: (entity['x'] - player['x']) ** 2 + (entity['z'] - player['z']) ** 2)
    return next((entity for entity in nearby[:5]
                 if wall_distance(player['x'], player['z'], entity['x'], entity['z']) > .98), None)


def bot_movement(player, goal):
    dx, dz = goal['x'] - player['x'], goal['z'] - player['z']
    distance = max(.01, math.hypot(dx, dz))
    return {'x': dx / distance, 'z': dz / distance, 'angle': math.atan2(dx, dz),
            'fire': False, 'aim_distance': distance}


def bot_combat(player, target, controls, now):
    tx, tz = target['x'] - player['x'], target['z'] - player['z']
    distance = math.hypot(tx, tz)
    angle = math.atan2(tx, tz) + random.uniform(-.09, .09)
    controls.update(angle=angle, aim_distance=distance,
                    fire=distance < WEAPONS[player['weapon']]['range'] and random.random() > .17)
    if distance < 15:
        sign = 1 if int(now / 2 + len(player['name'])) % 2 else -1
        controls.update(x=-math.cos(angle) * sign, z=math.sin(angle) * sign)
        if distance < 7:
            controls.update(x=-math.sin(angle), z=-math.cos(angle))


def update_bot_ai(game, player, now):
    if player['hp'] <= 0:
        if now - player['died_at'] >= 10:
            game.respawn(player)
        return
    if now < player.get('brain_at', 0):
        return
    player['brain_at'] = now + random.uniform(.14, .24)
    if player['weapon'] == 'glock18' and now - player['born'] > 1:
        equip_weapon(player, random.choice(['ak47', 'ak117', 'm4', 'shotgun']), now)
    target = select_bot_target(game, player, now)
    controls = bot_movement(player, destination(game, player, target, now))
    if target:
        bot_combat(player, target, controls, now)
    if not free(player['x'] + controls['x'], player['z'] + controls['z']):
        controls['x'], controls['z'] = controls['z'], -controls['x']
    controls.update(sprint=not target and player['stamina'] > 25,
                    reload=player['ammo'] < WEAPONS[player['weapon']]['mag'] * (.4 if not target else .05))
    game.set_input(player, controls)


def update_bots(game, now):
    balance_bots(game, now)
    bots = [player for player in game.players.values() if player.get('bot')]
    if not bots:
        return
    update_bot_grid(game, now)
    game.bot_path_budget = 1
    for player in bots:
        update_bot_ai(game, player, now)
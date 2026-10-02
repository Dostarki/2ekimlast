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


def update_bots(game, now):
    balance_bots(game, now)
    bots = [p for p in game.players.values() if p.get('bot')]
    if not bots:
        return
    if now >= getattr(game, 'bot_grid_at', 0):
        game.bot_grid_at = now+.2
        game.bot_grid = defaultdict(list)
        for e in [*game.players.values(), *game.zombies.values(), *game.bosses.values()]:
            if e['hp'] > 0:
                game.bot_grid[(int(e['x']//64), int(e['z']//64))].append(e)
    game.bot_path_budget = 1
    for p in bots:
        if p['hp'] <= 0:
            if now-p['died_at'] >= 10:
                game.respawn(p)
            continue
        if now < p.get('brain_at', 0):
            continue
        p['brain_at'] = now+random.uniform(.14, .24)
        if p['weapon'] == 'glock18' and now-p['born'] > 1:
            equip_weapon(p, random.choice(['ak47', 'ak117', 'm4', 'shotgun']), now)
        gx, gz = int(p['x']//64), int(p['z']//64)
        nearby = [e for x in range(gx-1, gx+2) for z in range(gz-1, gz+2) for e in game.bot_grid.get((x, z), [])
                  if e['id'] != p['id'] and e['hp'] > 0 and e.get('protected_until', 0) <= now and not e.get('awaiting_input', False)
                  and math.hypot(e['x']-p['x'], e['z']-p['z']) < 48]
        nearby.sort(key=lambda e: (e['x']-p['x'])**2+(e['z']-p['z'])**2)
        target = next((e for e in nearby[:5] if wall_distance(p['x'], p['z'], e['x'], e['z']) > .98), None)
        goal = destination(game, p, target, now)
        dx, dz = goal['x']-p['x'], goal['z']-p['z']; distance = max(.01, math.hypot(dx, dz))
        mx, mz = dx/distance, dz/distance
        angle = math.atan2(dx, dz)
        firing = False
        if target:
            tx, tz = target['x']-p['x'], target['z']-p['z']; distance = math.hypot(tx, tz)
            angle = math.atan2(tx, tz)+random.uniform(-.09, .09)
            firing = distance < WEAPONS[p['weapon']]['range'] and random.random() > .17
            if distance < 15:
                sign = 1 if int(now/2+len(p['name'])) % 2 else -1
                mx, mz = -math.cos(angle)*sign, math.sin(angle)*sign
                if distance < 7:
                    mx, mz = -math.sin(angle), -math.cos(angle)
        if not free(p['x']+mx, p['z']+mz):
            mx, mz = mz, -mx
        game.set_input(p, {'x': mx, 'z': mz, 'angle': angle, 'fire': firing, 'sprint': not target and p['stamina'] > 25,
                           'reload': p['ammo'] < WEAPONS[p['weapon']]['mag']*(.4 if not target else .05), 'aim_distance': distance})
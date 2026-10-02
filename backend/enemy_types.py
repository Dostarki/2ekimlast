import math
import random
from world import enemy_free

ENEMY_TYPES = {
    'normal': {'name': 'Creature', 'hp': 100, 'detection': 15, 'speed': 2.2, 'damage': 12},
    'immolator': {'name': 'Immolator', 'hp': 950, 'detection': 20, 'speed': 7.8, 'damage': 24, 'flame_range': 25},
    'hellhound': {'name': 'Hellhound', 'hp': 85, 'detection': 22, 'speed': 9.2, 'damage': 22},
    'hive': {'name': 'Hive', 'hp': 420, 'detection': 24, 'speed': 2.2, 'damage': 10, 'swarm_count': 3, 'swarm_cooldown': 3.5, 'swarm_speed': 4.5},
    'armored': {'name': 'Armored', 'hp': 340, 'detection': 15, 'speed': 2.5, 'damage': 28},
}


def make_enemy(index, x, z):
    # Every tenth successful spawn is fiery. The three adjacent hound slots form a pack.
    slot = (index-1) % 20
    kind = 'immolator' if index % 10 == 0 else 'hellhound' if slot in (3, 4, 5) else 'hive' if slot == 7 else 'armored' if slot == 8 else 'normal'
    profile = ENEMY_TYPES[kind]
    runner = kind == 'normal' and index % 2 == 0
    return {'id': f'z{index}', 'x': x, 'z': z, 'angle': 0, 'hp': profile['hp'], 'max_hp': profile['hp'],
            'zombie': True, 'enemy_type': kind, 'variant': index % 5, 'runner': runner,
            'speed': 6.8 if runner else profile['speed'], 'last_attack': 0, 'mode': 'wander',
            'wander_until': 0, 'last_special': -10, 'flame_until': 0, 'windup_until': 0,
            'last_flame': 0, 'attack_until': 0, 'target_id': '', 'pack': f'pack-{(index-1)//20}' if kind == 'hellhound' else ''}


def spawn_enemy_at(game, x, z):
    index = game.counter+1
    if (index-1) % 20 in (4, 5):
        leader = next((e for e in game.zombies.values() if e.get('pack') == f'pack-{(index-1)//20}'), None)
        if leader:
            px, pz = leader['x']+random.uniform(-2.5, 2.5), leader['z']+random.uniform(-2.5, 2.5)
            if enemy_free(px, pz):
                x, z = px, pz
    game.counter = index
    enemy = make_enemy(index, x, z)
    game.zombies[enemy['id']] = enemy
    return enemy


def spawn_enemies(game, player, count):
    spawned = 0
    for _ in range(count*18):
        if spawned >= count:
            break
        index = game.counter+1
        angle, radius = random.uniform(0, math.tau), random.uniform(24, 44)
        x, z = player['x']+math.sin(angle)*radius, player['z']+math.cos(angle)*radius
        if (index-1) % 20 in (4, 5):
            # Keep followers near their living pack, including when a spawn batch is split.
            leader = next((e for e in game.zombies.values() if e.get('pack') == f'pack-{(index-1)//20}'), None)
            if leader:
                x, z = leader['x']+random.uniform(-2.5, 2.5), leader['z']+random.uniform(-2.5, 2.5)
        if not enemy_free(x, z):
            continue
        game.counter = index
        enemy = make_enemy(index, x, z)
        game.zombies[enemy['id']] = enemy
        spawned += 1

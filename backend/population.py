"""Configured per-world zombie population, spread across map regions."""
import math
import random
from collections import Counter, defaultdict
from world import enemy_free
from enemy_types import spawn_enemy_at

REGION = 200
REGIONS = [(rx, rz) for rx in range(-4, 4) for rz in range(-4, 4)]
SPAWN_BATCH = 40
MIN_PLAYER_DISTANCE = 32


def region_of(x, z):
    return (min(3, max(-4, int(x//REGION))), min(3, max(-4, int(z//REGION))))


def actor_grid(actors, cell):
    grid = defaultdict(list)
    for a in actors:
        grid[(int(a['x']//cell), int(a['z']//cell))].append(a)
    return grid


def near(grid, cell, x, z):
    gx, gz = int(x//cell), int(z//cell)
    return [a for dx in (-1, 0, 1) for dz in (-1, 0, 1) for a in grid.get((gx+dx, gz+dz), ())]


def _point(region, players):
    rx, rz = region
    for _ in range(14):
        x = random.uniform(max(-780, rx*REGION+4), min(780, (rx+1)*REGION-4))
        z = random.uniform(max(-780, rz*REGION+4), min(780, (rz+1)*REGION-4))
        if enemy_free(x, z) and not any(math.hypot(p['x']-x, p['z']-z) < MIN_PLAYER_DISTANCE for p in near(players, MIN_PLAYER_DISTANCE, x, z)):
            return x, z
    return None


def maintain_population(game, now):
    if now < game.next_population_at:
        return
    game.next_population_at = now+.5
    missing = game.zombie_target-len(game.zombies)
    if missing <= 0:
        return
    counts = Counter(region_of(e['x'], e['z']) for e in game.zombies.values())
    players = actor_grid([p for p in game.players.values() if p['hp'] > 0], MIN_PLAYER_DISTANCE)
    for _ in range(min(missing, SPAWN_BATCH)):
        region = min(REGIONS, key=lambda r: (counts[r], random.random()))
        point = _point(region, players)
        counts[region] += 1
        if point:
            spawn_enemy_at(game, *point)


def trim_population(game, target):
    from enemy_damage import dismiss_hive
    if len(game.zombies) <= target:
        return
    living = [p for p in game.players.values() if p['hp'] > 0]
    def distance(e):
        return min((math.hypot(p['x']-e['x'], p['z']-e['z']) for p in living), default=0)
    # Remove the zombies furthest from players first so fights in progress stay intact.
    for e in sorted(game.zombies.values(), key=distance, reverse=True)[:len(game.zombies)-target]:
        dismiss_hive(game, e['id']); game.zombies.pop(e['id'], None)

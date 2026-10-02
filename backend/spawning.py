import math
import random
from collections import Counter
from world import free, enemy_free
from population import REGION, REGIONS, region_of


def spawn_position(game):
    """Bot birth/respawn: random outdoor coordinates across the entire map.

    Prefer less populated regions so batches do not pile up at one starting
    point. Humans are spawned separately at (0, 0) by Game.reset.
    """
    living = [p for p in game.players.values() if p['hp'] > 0]
    counts = Counter(region_of(p['x'], p['z']) for p in living if p.get('bot'))
    regions = list(REGIONS)
    random.shuffle(regions)
    regions.sort(key=lambda region: counts[region])
    fallback = None
    for rx, rz in regions:
        for _ in range(24):
            x = random.uniform(max(-780, rx*REGION+4), min(780, (rx+1)*REGION-4))
            z = random.uniform(max(-780, rz*REGION+4), min(780, (rz+1)*REGION-4))
            if not free(x, z) or not enemy_free(x, z):
                continue
            if any(math.hypot(p['x']-x, p['z']-z) < 12 for p in living):
                continue
            fallback = (x, z)
            if any(e['hp'] > 0 and math.hypot(e['x']-x, e['z']-z) < 20 for e in game.zombies.values()):
                continue
            if any(e['hp'] > 0 and math.hypot(e['x']-x, e['z']-z) < 65 for e in game.bosses.values()):
                continue
            return x, z
    # Dense zombie populations may leave no enemy-free gap. Never fall back to
    # the human sanctuary or a wall; use an outdoor point away from players.
    if fallback is not None:
        return fallback
    raise RuntimeError('No walkable outdoor bot spawn position available')

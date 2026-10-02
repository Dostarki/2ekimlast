"""Shared effect cleanup without importing damage dispatch or companion AI."""
from world import safe_zone_at


def dismiss_hive(game, owner):
    game.swarms[:] = [swarm for swarm in game.swarms if swarm['owner'] != owner]
    for player in game.players.values():
        if safe_zone_at(player['x'], player['z']):
            player.get('statuses', {}).clear()
            continue
        poison = player.get('statuses', {}).get('poison')
        if poison and poison['source'] == owner:
            player['statuses'].pop('poison', None)
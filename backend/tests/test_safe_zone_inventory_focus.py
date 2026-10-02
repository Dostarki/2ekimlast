"""Focused contracts for sanctuary damage and craft validation."""

import sys
from types import SimpleNamespace

sys.path.insert(0, "/app/backend")

from enemy_damage import damage_player
from inventory import new_inventory
from loot import craft_upgrade
from world import SAFE_ZONE_RADIUS, enemy_free, safe_zone_at


def player(x=0, z=0):
    return {
        'id': 'p', 'name': 'Survivor', 'x': x, 'z': z, 'hp': 100,
        'awaiting_input': False, 'protected_until': 0, 'statuses': {},
        'inventory': new_inventory(), 'weapon_parts': [], 'weapon_upgrades': {},
    }


def test_central_safe_zone_blocks_enemy_damage_and_status_ticks():
    game = SimpleNamespace(events=[], swarms=[], players={})
    protected = player()
    game.players[protected['id']] = protected
    assert safe_zone_at(0, 0)
    assert safe_zone_at(SAFE_ZONE_RADIUS, 0)
    assert enemy_free(SAFE_ZONE_RADIUS + .2, 0, .65) is False
    assert damage_player(game, protected, 40, 'Creature', 10) is False
    assert protected['hp'] == 100


def test_stale_weapon_recipe_cannot_consume_parts():
    game = SimpleNamespace(events=[])
    survivor = player(100, 100)
    survivor['weapon_parts'] = [{'id': 'barrel_common', 'tier': 1} for _ in range(2)] + [{'id': 'grip_common', 'tier': 1} for _ in range(2)]
    before = list(survivor['weapon_parts'])
    assert craft_upgrade(game, survivor, 'craft_weapon_revolver', 'revolver', 10) is False
    assert survivor['weapon_parts'] == before

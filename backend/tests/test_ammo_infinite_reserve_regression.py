"""Regression tests for Glock18 infinite reserve and finite-weapon reload behavior."""

import json
import math
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from combat import shoot
from engine import Game
from inventory import equip_weapon
from world import WEAPONS


def _new_player(unlocked=None, saved_progress=None):
    game = Game(save_score=None)
    session = {
        'account_id': 'acct-ammo',
        'name': 'TEST_AMMO',
        'weapon': 'glock18',
        'progress': saved_progress or {
            'unlocked_weapons': unlocked or ['glock18'],
        },
    }
    player = game.add_player(session, ws=None, bot=False)
    # Keep all shots outside sanctuary checks for deterministic fire tests.
    player['x'], player['z'] = 200.0, 200.0
    player['angle'] = 0.0
    player['last_shot'] = 0.0
    return game, player


# Modules/features: Glock18 reserve-infinite reload path and 1.5s base reload timing.
def test_glock_manual_reload_with_zero_reserve_keeps_capacity_and_timing():
    game, player = _new_player()
    now = time.monotonic()
    player.update(weapon='glock18', ammo=0, reserve=0, hp=100, reload_until=0, weapon_ready_at=0)
    player['inventory']['glock18'] = {'ammo': 0, 'reserve': 0}

    game.set_input(player, {'type': 'input', 'x': 0, 'z': 0, 'angle': 0, 'reload': True})
    assert player['reload_until'] > player['input_time']
    assert player['reload_until'] - player['input_time'] == pytest.approx(1.5, abs=0.02)

    # No shot while reloading.
    before_last_shot = player['last_shot']
    shoot(game, player, now)
    assert player['last_shot'] == before_last_shot

    game.update(0.05, player['reload_until'] + 0.001)
    assert player['ammo'] == 17
    assert player['reserve'] == 0
    assert player['reload_until'] == 0


# Modules/features: automatic reload after final bullet with zero reserve for infinite-reserve Glock.
def test_glock_auto_reload_triggers_on_final_bullet_with_zero_reserve():
    game, player = _new_player()
    now = time.monotonic() + 10
    player.update(weapon='glock18', ammo=1, reserve=0, hp=100, reload_until=0, weapon_ready_at=0)

    shoot(game, player, now)
    assert player['ammo'] == 0
    assert player['reload_until'] == pytest.approx(now + 1.5, abs=0.02)


# Modules/features: repeated magazine cycles never deplete Glock18 reserve.
def test_glock_multiple_reload_cycles_keep_zero_reserve_without_depletion():
    game, player = _new_player()
    player.update(weapon='glock18', ammo=1, reserve=0, hp=100, reload_until=0, weapon_ready_at=0)

    now = time.monotonic() + 20
    for _ in range(4):
        shoot(game, player, now)
        assert player['ammo'] == 0
        assert player['reload_until'] > 0
        game.update(0.05, player['reload_until'] + 0.001)
        assert player['ammo'] == 17
        assert player['reserve'] == 0
        now += 2.0
        player['ammo'] = 1
        player['reload_until'] = 0


# Modules/features: cannot shoot during reload/dead/equip cooldown conditions.
@pytest.mark.parametrize(
    'mutator',
    [
        lambda p, now: p.update(reload_until=now + 1.0),
        lambda p, now: p.update(hp=0),
        lambda p, now: p.update(weapon_ready_at=now + 0.2),
    ],
)
def test_glock_shoot_blocked_during_reload_dead_or_equip_cooldown(mutator):
    game, player = _new_player()
    now = time.monotonic() + 30
    player.update(weapon='glock18', ammo=17, reserve=0, hp=100, reload_until=0, weapon_ready_at=0, last_shot=now - 5)
    mutator(player, now)

    before = (player['ammo'], player['last_shot'])
    shoot(game, player, now)
    assert (player['ammo'], player['last_shot']) == before


# Modules/features: equip away/back keeps Glock slot data and allows reload again.
def test_glock_equip_switch_and_back_preserves_zero_reserve_behavior():
    game, player = _new_player(unlocked=['glock18', 'ak47'])
    now = time.monotonic() + 40

    player['inventory']['glock18'] = {'ammo': 0, 'reserve': 0}
    player.update(weapon='glock18', ammo=0, reserve=0, weapon_ready_at=0, hp=100)

    assert equip_weapon(player, 'ak47', now=now) is True
    assert player['inventory']['glock18'] == {'ammo': 0, 'reserve': 0}
    assert equip_weapon(player, 'glock18', now=now + 0.31) is True

    game.set_input(player, {'type': 'input', 'x': 0, 'z': 0, 'angle': 0, 'reload': True})
    game.update(0.05, player['reload_until'] + 0.001)
    assert player['ammo'] == 17
    assert player['reserve'] == 0


# Modules/features: old save with ammo/reserve zero + respawn keeps valid finite values and reload behavior.
def test_glock_old_save_zero_and_respawn_still_reloads():
    saved = {
        'equipped_weapon': 'glock18',
        'inventory': {'glock18': {'ammo': 0, 'reserve': 0}},
        'unlocked_weapons': ['glock18'],
    }
    game, player = _new_player(saved_progress=saved)
    assert player['ammo'] == 0
    assert player['reserve'] == 0

    game.set_input(player, {'type': 'input', 'x': 0, 'z': 0, 'angle': 0, 'reload': True})
    game.update(0.05, player['reload_until'] + 0.001)
    assert player['ammo'] == 17

    player['hp'] = 0
    player['died_at'] = time.monotonic() - 11
    assert game.respawn(player) is True
    player.update(weapon='glock18', ammo=0, reserve=0, hp=100, reload_until=0)
    game.set_input(player, {'type': 'input', 'x': 0, 'z': 0, 'angle': 0, 'reload': True})
    game.update(0.05, player['reload_until'] + 0.001)
    assert player['ammo'] == 17


# Modules/features: finite weapons remain finite, no reload at reserve=0 and partial refill with limited reserve.
def test_non_glock_weapons_remain_finite_and_partial_reload_works():
    game, player = _new_player(unlocked=list(WEAPONS.keys()))

    finite_weapons = [weapon_id for weapon_id in WEAPONS.keys() if weapon_id != 'glock18']
    for weapon_id in finite_weapons:
        player.update(weapon=weapon_id, ammo=0, reserve=0, hp=100, reload_until=0, weapon_ready_at=0)
        game.set_input(player, {'type': 'input', 'x': 0, 'z': 0, 'angle': 0, 'reload': True})
        assert player['reload_until'] == 0, f'{weapon_id} should not reload at zero reserve'

    # Partial refill check requested for finite reserve.
    player.update(weapon='ak47', ammo=0, reserve=7, hp=100, reload_until=0, weapon_ready_at=0)
    game.set_input(player, {'type': 'input', 'x': 0, 'z': 0, 'angle': 0, 'reload': True})
    assert player['reload_until'] > 0
    game.update(0.05, player['reload_until'] + 0.001)
    assert player['ammo'] == 7
    assert player['reserve'] == 0


# Modules/features: me.infinite_reserve + per-slot metadata and serialization safety (no NaN/Infinity).
def test_snapshot_infinite_reserve_metadata_and_serialization_safety():
    game, player = _new_player(unlocked=list(WEAPONS.keys()))
    state = game.snapshot(player, time.monotonic())

    assert state['me']['infinite_reserve'] is True
    assert state['me']['inventory']['glock18']['infinite_reserve'] is True
    for weapon_id, slot in state['me']['inventory'].items():
        if weapon_id != 'glock18':
            assert slot['infinite_reserve'] is False

    # JSON output must stay numeric-safe for persistence/transport.
    raw = json.dumps(state, allow_nan=False)
    assert 'Infinity' not in raw
    assert 'NaN' not in raw
    # Defensive finite checks on numeric reserve payloads.
    assert math.isfinite(float(state['me']['reserve']))

"""Territory invariants for boss AI without live HTTP dependencies."""

import math

import bosses as bosses_module
from boss_catalog import BOSS_TYPES
from bosses import begin_attack, update_bosses
from engine import Game


async def _noop_save(_player):
    return None


def _target(identifier, x, z, *, hp=100, active=True):
    return {
        'id': identifier, 'name': identifier, 'x': x, 'z': z, 'hp': hp,
        'awaiting_input': False, 'status': 'active' if active else 'recovering',
    }


def _game(monkeypatch):
    game = Game(_noop_save)
    monkeypatch.setattr(bosses_module, 'enemy_free', lambda *_args, **_kwargs: True)
    monkeypatch.setattr(bosses_module, 'wall_distance', lambda *_args, **_kwargs: 1.0)
    return game


def test_four_living_bosses_have_disjoint_home_regions_and_respawn_there(monkeypatch):
    game = _game(monkeypatch)
    homes = [(boss['home_x'], boss['home_z'], boss['territory_radius']) for boss in game.bosses.values()]
    assert len(homes) == 4
    assert all(math.hypot(ax-bx, az-bz) > ar+br for index, (ax, az, ar) in enumerate(homes) for bx, bz, br in homes[index + 1:])

    boss = game.bosses['boss-hansel']
    boss.update(hp=0, respawn_at=10.0, x=999.0, z=999.0)
    update_bosses(game, .1, 10.1)
    reborn = game.bosses['boss-hansel']
    assert (reborn['x'], reborn['z']) == BOSS_TYPES['hansel']['home']
    assert reborn['hp'] == reborn['max_hp'] and reborn['generation'] == 2


def test_long_kiting_never_moves_a_boss_outside_its_home_region(monkeypatch):
    game = _game(monkeypatch)
    boss = game.bosses['boss-hansel']
    runner = _target('runner', boss['home_x'], boss['home_z'] + 5)
    game.players = {runner['id']: runner}
    boss['next_attack'] = 10_000
    for tick in range(240):
        angle = tick / 12
        runner['x'] = boss['home_x'] + math.sin(angle) * 34
        runner['z'] = boss['home_z'] + math.cos(angle) * 34
        update_bosses(game, .1, float(tick))
        assert math.hypot(boss['x']-boss['home_x'], boss['z']-boss['home_z']) <= boss['territory_radius'] + 1e-6


def test_target_death_safe_zone_and_soldier_targeting_respect_territory(monkeypatch):
    game = _game(monkeypatch)
    boss = game.bosses['boss-hansel']
    player = _target('player', boss['home_x'], boss['home_z'] + 10)
    game.players = {player['id']: player}
    update_bosses(game, .1, 1.0)
    assert boss['target_id'] == player['id']

    player['hp'] = 0
    update_bosses(game, .1, 1.1)
    assert boss['target_id'] == '' and boss['action'] in ('return', 'idle')

    player['hp'] = 100
    monkeypatch.setattr(bosses_module, 'safe_zone_at', lambda x, z: (x, z) == (player['x'], player['z']))
    update_bosses(game, .1, 1.2)
    assert boss['target_id'] == ''

    game.players = {}
    soldier = _target('soldier', boss['home_x'] + 4, boss['home_z'] + 8)
    game.soldiers = {soldier['id']: soldier}
    monkeypatch.setattr(bosses_module, 'safe_zone_at', lambda *_args: False)
    update_bosses(game, .1, 1.3)
    assert boss['target_id'] == soldier['id']


def test_pending_leap_cancels_when_target_exits_and_legacy_position_walks_home(monkeypatch):
    game = _game(monkeypatch)
    boss = game.bosses['boss-hansel']
    runner = _target('runner', boss['home_x'], boss['home_z'] + 10)
    game.players = {runner['id']: runner}
    update_bosses(game, .1, 1.0)
    begin_attack(boss, 'leap', runner, 2.0)
    assert boss['pending'] is not None
    runner['z'] = boss['home_z'] + boss['territory_radius'] + 3
    update_bosses(game, .1, 2.1)
    assert boss['pending'] is None and boss['target_id'] == '' and boss['action'] in ('return', 'idle')

    boss.update(x=boss['home_x'] + 55, z=boss['home_z'], hp=4321)
    game.players = {}
    for tick in range(220):
        update_bosses(game, .1, 3.0 + tick * .1)
    assert math.hypot(boss['x']-boss['home_x'], boss['z']-boss['home_z']) < .3
    assert boss['action'] == 'idle' and boss['hp'] == 4321


def test_real_world_collision_and_los_return_hansel_home_without_healing():
    """Use the actual world collision/LOS functions for a clear home corridor."""
    game = Game(_noop_save)
    boss = game.bosses['boss-hansel']
    runner = _target('runner', 80.0, 20.0)
    game.players = {runner['id']: runner}
    boss['next_attack'] = 10_000
    hp_before = boss['hp']

    for tick in range(30):
        update_bosses(game, .1, float(tick))
    assert boss['target_id'] == runner['id']
    assert boss['z'] > boss['home_z']

    runner['z'] = 100.0
    for tick in range(30, 150):
        update_bosses(game, .1, float(tick))
    assert boss['target_id'] == ''
    assert math.hypot(boss['x']-boss['home_x'], boss['z']-boss['home_z']) < .3
    assert boss['hp'] == hp_before

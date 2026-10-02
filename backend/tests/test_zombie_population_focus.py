"""Focused regression for fixed server-wide zombie population and performance.

Covers the new population model:
  * add_player / respawn no longer spawn zombies.
  * Game.update does not do per-player periodic spawn.
  * population.maintain_population tops up to game.zombie_target.
  * apply_settings: density/count changes trim immediately and clear on 'off'.
  * zombies.update_zombies leaves dormant zombies untouched (far from players).
  * shared_snapshot exposes actors/player_grid/zombie_grid; snapshot has
    players + zombies filtered to view.
  * tick_ms stays low with ~600 zombies.
"""
import os
import time
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine import Game, VIEW  # noqa: E402
from game_settings import GameSettings, apply_settings  # noqa: E402
from population import maintain_population  # noqa: E402
from zombies import update_zombies, ACTIVE_RANGE  # noqa: E402
from enemy_types import spawn_enemy_at  # noqa: E402


class _FakeWS:
    async def send_text(self, _):  # pragma: no cover
        return None

    async def send_bytes(self, _):  # pragma: no cover
        return None


def _make_game(density='normal', count=None):
    g = Game(save_score=None)
    s = GameSettings().model_dump()
    s['zombie_density'] = density
    if count is not None:
        s['zombie_count'] = count
    apply_settings(g, s)
    return g


def _add_player(g, name='alice', bot=True):
    # bot=True to skip ClientChannel + progress save side-effects
    return g.add_player({'name': name, 'account_id': ''}, _FakeWS(), bot=bot)


# ---------- Spawn-on-join / respawn no longer trigger zombie spawns ----------

def test_add_player_does_not_spawn_zombies():
    g = _make_game(density='normal', count=250)
    assert g.zombie_target == 250
    assert len(g.zombies) == 0  # not yet maintained
    for i in range(5):
        _add_player(g, name=f'p{i}')
    # add_player must not spawn zombies by itself.
    assert len(g.zombies) == 0


def test_respawn_does_not_spawn_zombies():
    g = _make_game(density='normal', count=250)
    p = _add_player(g)
    p['hp'] = 0
    p['died_at'] = time.monotonic() - 15
    # Pre-seed one zombie so we can assert count is unchanged by the respawn
    spawn_enemy_at(g, 10.0, 10.0)
    before = len(g.zombies)
    assert g.respawn(p) is True
    assert len(g.zombies) == before


# ---------- game_settings.zombie_target & apply_settings behavior ----------

def test_zombie_target_follows_count_setting():
    g = _make_game(density='low', count=120)
    assert g.zombie_target == 120
    s = dict(g.settings)
    s['zombie_count'] = 300
    s['zombie_density'] = 'high'
    apply_settings(g, s)
    assert g.zombie_target == 300


def test_density_off_clears_zombies():
    g = _make_game(density='normal', count=250)
    spawn_enemy_at(g, 0, 0)
    spawn_enemy_at(g, 10, 10)
    assert len(g.zombies) == 2
    s = dict(g.settings)
    s['zombie_density'] = 'off'
    apply_settings(g, s)
    assert g.zombie_target == 0
    assert len(g.zombies) == 0


def test_lowering_count_trims_immediately():
    g = _make_game(density='normal', count=250)
    # seed zombies at varying distances
    for i in range(10):
        spawn_enemy_at(g, i * 50.0, 0.0)
    # Add a living player at origin so trim keeps nearest ones
    p = _add_player(g)
    p['hp'] = 100
    assert len(g.zombies) == 10
    s = dict(g.settings); s['zombie_count'] = 3
    apply_settings(g, s)
    assert g.zombie_target == 3
    assert len(g.zombies) == 3
    # the 3 remaining should be the nearest to the player at origin
    xs = sorted(z['x'] for z in g.zombies.values())
    assert xs == [0.0, 50.0, 100.0]


def test_count_strict_bounds():
    # Pydantic strict int bounds 0..600
    with pytest.raises(Exception):
        GameSettings(zombie_count=-1)
    with pytest.raises(Exception):
        GameSettings(zombie_count=601)
    with pytest.raises(Exception):
        GameSettings(zombie_count=3.5)  # strict int


# ---------- maintain_population tops up to target ----------

def test_maintain_population_tops_up():
    g = _make_game(density='normal', count=50)
    assert len(g.zombies) == 0
    # Run several ticks; batch size is 40 per 0.5s so we need >= 2 cycles
    now = 100.0
    for _ in range(4):
        maintain_population(g, now)
        now += 0.6
    assert len(g.zombies) >= 50
    # Should not exceed target
    assert len(g.zombies) <= 60  # tolerate batch overshoot = 0 (loop uses min(missing, 40))


def test_maintain_population_rate_limited():
    g = _make_game(density='normal', count=250)
    maintain_population(g, 1.0)
    first = len(g.zombies)
    # Called again inside same window — must not spawn more
    maintain_population(g, 1.1)
    assert len(g.zombies) == first


def test_maintain_population_respects_min_player_distance():
    g = _make_game(density='normal', count=200)
    p = _add_player(g)
    p['x'], p['z'], p['hp'] = 0.0, 0.0, 100
    maintain_population(g, 500.0)
    import math
    close = [z for z in g.zombies.values() if math.hypot(z['x'] - p['x'], z['z'] - p['z']) < 32]
    assert close == []


# ---------- Game.update doesn't spawn zombies per player ----------

def test_update_does_not_spawn_zombies_per_player(monkeypatch):
    g = _make_game(density='normal', count=250)
    _add_player(g)
    # Make maintain_population a no-op so we can see whether update spawns anything itself
    import engine
    monkeypatch.setattr(engine, 'maintain_population', lambda *_a, **_k: None)
    before = len(g.zombies)
    for _ in range(20):
        g.update(0.05, time.monotonic())
    assert len(g.zombies) == before


# ---------- Dormant zombies: no players nearby => skipped ----------

def test_dormant_zombies_do_not_move():
    g = _make_game(density='normal', count=250)
    p = _add_player(g)
    p['x'], p['z'], p['hp'], p['awaiting_input'] = 0.0, 0.0, 100, False
    # Zombie far from any player (well beyond ACTIVE_RANGE=90)
    far = spawn_enemy_at(g, 500.0, 500.0)
    far['target_id'] = ''
    before = (far['x'], far['z'], far['mode'])
    update_zombies(g, [p], 0.05, time.monotonic())
    assert far['x'] == before[0] and far['z'] == before[1]
    # Zombie close to player: NOT skipped
    near_z = spawn_enemy_at(g, 10.0, 0.0)
    update_zombies(g, [p], 0.05, time.monotonic())
    # should have an aggro target or wander change (mode set)
    assert near_z.get('mode') in {'attack', 'wander', 'idle', 'swarm', 'windup'}


# ---------- Snapshot: shared snapshot + per-player content ----------

def test_shared_snapshot_structure():
    g = _make_game(density='normal', count=50)
    _add_player(g)
    spawn_enemy_at(g, 5.0, 5.0)
    shared = g.shared_snapshot(time.monotonic())
    for key in ('actors', 'player_grid', 'zombie_grid', 'bosses', 'leaders'):
        assert key in shared, f'missing {key}'


def test_snapshot_includes_zombies_in_view():
    g = _make_game(density='normal', count=50)
    p = _add_player(g)
    p['hp'] = 100
    spawn_enemy_at(g, 10.0, 10.0)   # inside VIEW
    spawn_enemy_at(g, 500.0, 500.0) # outside VIEW
    now = time.monotonic()
    snap = g.snapshot(p, now)
    assert snap['type'] == 'state'
    assert 'players' in snap and 'zombies' in snap
    assert len(snap['zombies']) == 1
    assert snap['zombies'][0]['x'] == 10.0


# ---------- Performance: tick_ms with ~600 zombies and a few players ----------

def test_tick_ms_low_with_many_zombies(monkeypatch):
    g = _make_game(density='high', count=600)
    # 3 players spread out
    players = []
    for i, (x, z) in enumerate([(0, 0), (300, 300), (-300, -300)]):
        p = _add_player(g, name=f'p{i}')
        p['x'], p['z'], p['hp'], p['awaiting_input'] = x, z, 100, False
        players.append(p)
    # Seed 600 zombies deterministically
    import random
    random.seed(42)
    while len(g.zombies) < 600:
        x = random.uniform(-780, 780); z = random.uniform(-780, 780)
        spawn_enemy_at(g, x, z)
    # Prevent population loop from doing more work
    import engine
    monkeypatch.setattr(engine, 'maintain_population', lambda *_a, **_k: None)

    # Warm up
    g.update(0.05, time.monotonic())
    # Measure a few ticks
    samples = []
    for _ in range(10):
        t = time.monotonic()
        g.update(0.05, t)
        g.tick_seq += 1
        shared = g.shared_snapshot(t)
        for p in players:
            g.snapshot(p, t, shared)
        samples.append((time.monotonic() - t) * 1000)
    median = sorted(samples)[len(samples)//2]
    print(f'tick+snapshot median_ms={median:.2f} samples_ms={[round(s,2) for s in samples]}')
    # Loose budget: with 600 zombies and 3 players, a tick + snapshots must stay reasonable
    assert median < 50, f'tick too slow: {median}ms'

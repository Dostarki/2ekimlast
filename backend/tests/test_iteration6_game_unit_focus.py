"""Iteration-6 deterministic unit tests for combat, respawn, settings, spawning, and bot mechanics."""

import math
import asyncio
import random
import sys

import pytest

sys.path.insert(0, "/app/backend")

import bots
import combat
import engine as engine_module
import spawning
from engine import Game
from game_settings import GameSettings, apply_settings
from inventory import equip_weapon
from world import WEAPONS, free, safe_zone_at


async def _noop_save_score(_player):
    return None


def _outside_safe_spot(*, base: int = 120):
    """Pick a deterministic free coordinate outside sanctuary for combat tests."""
    candidates = [(base, base), (base + 8, base), (base, base + 8), (base + 12, base + 6), (-base, base)]
    for x, z in candidates:
        if free(x, z) and not safe_zone_at(x, z):
            return float(x), float(z)
    pytest.skip("No deterministic free coordinate found outside safe zone")


def _player(pid: str, *, name: str | None = None, weapon: str = "glock18", x: float = 0.0, z: float = 0.0, hp: float = 100.0):
    return {
        "id": pid,
        "name": name or pid,
        "weapon": weapon,
        "skin": "soldier",
        "x": x,
        "z": z,
        "angle": 0.0,
        "hp": hp,
        "ammo": WEAPONS[weapon]["mag"],
        "reserve": WEAPONS[weapon]["reserve"],
        "score": 0,
        "kills": 0,
        "pvp": 0,
        "stamina": 100,
        "reload_until": 0,
        "last_shot": -999,
        "killer": "",
        "protected_until": 0,
        "awaiting_input": False,
        "input_time": 0,
        "born": 0,
        "died_at": 0,
        "last_spawn": 0,
        "trigger": False,
        "statuses": {},
        "input_seq": 0,
        "ack_seq": 0,
        "vx": 0,
        "vz": 0,
        "controls": {"x": 0, "z": 0, "fire": False, "sprint": False},
        "inventory": {k: {"ammo": w["mag"], "reserve": w["reserve"]} for k, w in WEAPONS.items()},
    }


# Module: heavy weapons x1.5 contract values
def test_heavy_weapon_values_match_requested_balance():
    assert WEAPONS["rocket"]["damage"] == 330
    assert WEAPONS["minigun"]["damage"] == 24
    assert WEAPONS["flamethrower"]["damage"] == 13.5
    assert WEAPONS["lava"]["damage"] == 67.5


# Module: heavy categories actual damage path (minigun/flame/rocket/lava+zone)
def test_heavy_damage_paths_apply_on_real_combat_pipeline(monkeypatch):
    game = Game(_noop_save_score)
    game.persist = lambda _p: None
    sx, sz = _outside_safe_spot(base=140)
    shooter = _player("s", weapon="minigun", x=sx, z=sz)
    target = _player("t", x=sx, z=sz + 5)
    game.players = {"s": shooter, "t": target}
    monkeypatch.setattr(combat, "wall_distance", lambda *_a, **_k: 1.0)
    monkeypatch.setattr(random, "uniform", lambda _a, _b: 0)

    combat.shoot(game, shooter, now=1.0)
    assert target["hp"] == pytest.approx(100 - WEAPONS["minigun"]["damage"])

    target["hp"] = 100
    shooter["weapon"] = "flamethrower"
    shooter["ammo"] = WEAPONS["flamethrower"]["mag"]
    shooter["reserve"] = WEAPONS["flamethrower"]["reserve"]
    shooter["last_shot"] = -999
    combat.shoot(game, shooter, now=2.0)
    assert target["hp"] == pytest.approx(100 - WEAPONS["flamethrower"]["damage"])

    target["hp"] = 500
    combat.explode(game, {"id": "r1", "kind": "rocket", "x": sx, "z": sz + 5, "owner": "s"}, now=3.0)
    hp_after_rocket = target["hp"]
    assert hp_after_rocket < 500

    target.update(hp=500, x=sx, z=sz + 2)
    combat.explode(game, {"id": "l1", "kind": "lava", "x": sx, "z": sz, "owner": "s"}, now=4.0)
    assert len(game.fires) == 1
    hp_after_lava_blast = target["hp"]
    combat.update_projectiles(game, dt=0.1, now=4.5)
    assert target["hp"] < hp_after_lava_blast


# Module: 10s server-side respawn gate + glock/full inventory reset
def test_respawn_gate_10s_then_success_resets_player(monkeypatch):
    game = Game(_noop_save_score)
    bot = game.add_player({"name": "BOT1", "weapon": "ak47", "skin": "fbi"}, None, bot=True)
    bot["hp"] = 0
    bot["died_at"] = 100.0
    old_id = bot["id"]

    monkeypatch.setattr(engine_module.time, "monotonic", lambda: 109.9)
    assert game.respawn(bot) is False
    assert bot["id"] == old_id

    monkeypatch.setattr(engine_module.time, "monotonic", lambda: 110.1)
    assert game.respawn(bot) is True
    assert bot["id"] != old_id
    assert bot["hp"] == 100
    assert bot["weapon"] == "glock18"
    # Runtime contract: respawn preserves unlocked inventory (no full unlock reset).
    assert set(bot["inventory"].keys()) == {"glock18"}
    assert free(bot["x"], bot["z"])


# Module: equip restrictions for dead/cooldown and reload-cancel does not refill
def test_equip_denied_when_dead_or_cooldown_and_reload_cancel_no_refill():
    p = _player("p", weapon="glock18")
    p["hp"] = 0
    assert equip_weapon(p, "ak47", now=1.0) is False

    p["hp"] = 100
    assert equip_weapon(p, "ak47", now=2.0) is True
    assert equip_weapon(p, "m4", now=2.1) is False

    p["weapon"] = "ak47"
    p["ammo"] = 0
    p["reserve"] = 60
    p["inventory"]["ak47"] = {"ammo": 0, "reserve": 60}
    p["inventory"]["m4"] = {"ammo": 7, "reserve": 90}
    p["reload_until"] = 10
    p["weapon_ready_at"] = 0
    p["controls"]["fire"] = True

    assert equip_weapon(p, "m4", now=11.0) is True
    assert p["ammo"] == 7 and p["reserve"] == 90
    assert p["reload_until"] == 0
    assert p["controls"]["fire"] is False


# Module: random spawn must avoid active entities and blocked cells
def test_spawn_position_is_safe_away_from_players_zombies_and_bosses(monkeypatch):
    class DummyGame:
        pass

    g = DummyGame()
    g.players = {"p1": {"id": "p1", "x": 0, "z": 0, "hp": 100}}
    g.zombies = {"z1": {"id": "z1", "x": 25, "z": 0, "hp": 100}}
    g.bosses = {"b1": {"id": "b1", "x": 80, "z": 0, "hp": 1000}}
    x, z = spawning.spawn_position(g)
    assert free(x, z)
    assert not safe_zone_at(x, z)
    assert -780 <= x <= 780 and -780 <= z <= 780
    assert math.hypot(x - 0, z - 0) >= 12
    assert math.hypot(x - 25, z - 0) >= 20
    assert math.hypot(x - 80, z - 0) >= 65


# Module: boss toggles clear hazards/statuses and re-enable recreates only target boss
def test_apply_settings_boss_toggle_clears_only_owner_and_recreates(monkeypatch):
    game = Game(_noop_save_score)
    game.players = {
        "p1": _player("p1"),
        "p2": _player("p2"),
    }
    game.players["p1"]["statuses"] = {
        "poison": {"source": "boss-hansel", "until": 999},
        "webbed": {"source": "boss-symbiote", "until": 999},
    }
    game.boss_projectiles = [
        {"id": "k1", "owner": "boss-hansel"},
        {"id": "k2", "owner": "boss-symbiote"},
    ]
    game.boss_zones = [
        {"id": "z1", "owner": "boss-hansel"},
        {"id": "z2", "owner": "boss-symbiote"},
    ]
    game.events = [
        {"type": "boss_impact", "owner": "boss-hansel"},
        {"type": "boss_impact", "owner": "boss-symbiote"},
    ]

    updated = GameSettings(
        bosses={"hansel": False, "symbiote": True, "xenomorph": True, "ash_titan": True},
        time_of_day="day",
        zombie_density="normal",
        bot_count=0,
    ).model_dump()
    apply_settings(game, updated)
    assert "boss-hansel" not in game.bosses
    assert "boss-symbiote" in game.bosses
    assert all(e["owner"] != "boss-hansel" for e in game.boss_projectiles)
    assert all(e["owner"] != "boss-hansel" for e in game.boss_zones)
    assert all(e.get("owner") != "boss-hansel" for e in game.events)
    assert "poison" not in game.players["p1"]["statuses"]
    assert "webbed" in game.players["p1"]["statuses"]

    reenable = GameSettings(
        bosses={"hansel": True, "symbiote": True, "xenomorph": True, "ash_titan": True},
        time_of_day="day",
        zombie_density="normal",
        bot_count=0,
    ).model_dump()
    apply_settings(game, reenable)
    assert "boss-hansel" in game.bosses


# Module: density=off clears population/statuses and blocks future zombie spawns
def test_density_off_clears_world_and_blocks_future_spawn(monkeypatch):
    game = Game(_noop_save_score)
    p = _player("p1")
    p["statuses"] = {
        "poison": {"source": "z1", "until": 999, "next_tick": 10, "damage": 4},
        "bleeding": {"source": "z2", "until": 999, "next_tick": 10, "damage": 3},
    }
    p["awaiting_input"] = False
    p["last_spawn"] = 0
    game.players = {p["id"]: p}
    game.zombies = {"z1": {"id": "z1", "x": 0, "z": 1, "hp": 100}}
    game.swarms = [{"id": "s1", "owner": "z1", "x": 0, "z": 1}]

    settings = GameSettings(zombie_density="off", bot_count=0).model_dump()
    apply_settings(game, settings)
    assert game.zombie_factor == 0
    assert game.zombies == {}
    assert game.swarms == []
    assert "poison" not in p["statuses"]
    assert "bleeding" not in p["statuses"]

    calls = {"spawn": 0}
    monkeypatch.setattr(game, "spawn_zombies", lambda *_a, **_k: calls.__setitem__("spawn", calls["spawn"] + 1))
    monkeypatch.setattr(engine_module, "update_bots", lambda *_a, **_k: None)
    monkeypatch.setattr(engine_module, "update_zombies", lambda *_a, **_k: None)
    monkeypatch.setattr(engine_module, "update_projectiles", lambda *_a, **_k: None)
    monkeypatch.setattr(engine_module, "update_statuses", lambda *_a, **_k: None)
    monkeypatch.setattr(engine_module, "update_bosses", lambda *_a, **_k: None)
    game.update(dt=0.1, now=100.0)
    assert calls["spawn"] == 0


# Module: low/normal/high densities change spawn cadence thresholds
def test_density_levels_change_spawn_cadence_threshold(monkeypatch):
    game = Game(_noop_save_score)
    # Runtime contract: world target follows configured zombie_count, with factors from density.
    apply_settings(game, GameSettings(zombie_density="low", zombie_count=120, bot_count=0).model_dump())
    assert game.zombie_target == 120
    assert game.zombie_factor == 0.5

    apply_settings(game, GameSettings(zombie_density="normal", zombie_count=250, bot_count=0).model_dump())
    assert game.zombie_target == 250
    assert game.zombie_factor == 1

    apply_settings(game, GameSettings(zombie_density="high", zombie_count=450, bot_count=0).model_dump())
    assert game.zombie_target == 450
    assert game.zombie_factor == 2


# Module: startup persistence simulation via GameSettings validation + apply_settings
def test_saved_settings_validate_and_apply_to_fresh_game_without_service_restart():
    saved = {
        "bosses": {"hansel": True, "symbiote": False, "xenomorph": True, "ash_titan": False},
        "time_of_day": "night",
        "zombie_density": "low",
        "bot_count": 3,
    }
    validated = GameSettings.model_validate(saved).model_dump()
    fresh = Game(_noop_save_score)
    apply_settings(fresh, validated)
    assert fresh.settings == validated
    assert fresh.settings["time_of_day"] == "night"
    assert fresh.settings["zombie_density"] == "low"
    assert fresh.settings["bot_count"] == 3
    assert "boss-symbiote" not in fresh.bosses
    assert "boss-ash_titan" not in fresh.bosses


# Module: bot naming/cap computation and cleanup (no live 200 spawn load)
def test_bot_uniqueness_and_cap_math_and_cleanup(monkeypatch):
    game = Game(_noop_save_score)
    game.spawn_zombies = lambda *_a, **_k: None

    humans = [_player(f"h{i}", name=f"Human{i}") for i in range(2)]
    game.players = {p["id"]: p for p in humans}
    bot1 = game.add_player({"name": "BotSeed1", "weapon": "glock18", "skin": "soldier"}, None, bot=True)
    bot2 = game.add_player({"name": "BotSeed2", "weapon": "glock18", "skin": "soldier"}, None, bot=True)
    assert bot1["name"] != bot2["name"]

    game.projectiles = [{"id": "p1", "owner": bot1["id"]}, {"id": "p2", "owner": "other"}]
    game.fires = [{"id": "f1", "owner": bot1["id"]}, {"id": "f2", "owner": "other"}]
    bots.remove_bot(game, bot1)
    assert all(p["owner"] != bot1["id"] for p in game.projectiles)
    assert all(f["owner"] != bot1["id"] for f in game.fires)

    game.settings["bot_count"] = 200
    game.players = {f"h{i}": _player(f"h{i}", name=f"Human{i}") for i in range(199)}
    calls = {"added": 0}

    def _fake_add_player(_session, _ws, bot=False):
        calls["added"] += 1
        return {"id": f"b{calls['added']}", "name": f"B{calls['added']}", "bot": bot, "brain_at": 0}

    monkeypatch.setattr(game, "add_player", _fake_add_player)
    game.next_bot_balance = 0
    bots.balance_bots(game, now=1.0)
    assert calls["added"] == 1


# Module: dead bots auto-respawn after 10s and snapshot keeps bot flag private
def test_bot_auto_respawn_after_10s_and_snapshot_hides_bot_flag(monkeypatch):
    game = Game(_noop_save_score)
    game.spawn_zombies = lambda *_a, **_k: None

    me = _player("me", name="Human", weapon="glock18")
    other_bot = _player("bot1", name="NomadBot", weapon="glock18")
    other_bot["bot"] = True
    other_bot["hp"] = 0
    other_bot["died_at"] = 5.0
    game.players = {"me": me, "bot1": other_bot}

    monkeypatch.setattr(bots, "balance_bots", lambda *_a, **_k: None)
    bots.update_bots(game, now=14.9)
    assert other_bot["hp"] == 0
    old = other_bot["id"]
    bots.update_bots(game, now=15.1)
    assert other_bot["hp"] == 100
    assert other_bot["id"] != old

    snapshot = game.snapshot(me, now=15.2)
    assert snapshot["online"] == len(game.players)
    assert all("bot" not in actor for actor in snapshot["players"])


# Module: bot add stagger (2 per 250ms) and immediate removal on lower target
def test_bot_add_stagger_and_immediate_removal_behavior(monkeypatch):
    game = Game(_noop_save_score)
    game.spawn_zombies = lambda *_a, **_k: None
    game.settings["bot_count"] = 3
    game.players = {"h1": _player("h1"), "h2": _player("h2")}

    seq = {"n": 0}

    def _fake_add_player(_session, _ws, bot=False):
        seq["n"] += 1
        pid = f"b{seq['n']}"
        created = _player(pid, name=f"Bot{seq['n']}")
        created["bot"] = bot
        game.players[pid] = created
        return created

    monkeypatch.setattr(game, "add_player", _fake_add_player)
    monkeypatch.setattr(bots.random, "choice", lambda arr: arr[0])
    monkeypatch.setattr(bots.random, "random", lambda: 0.1)

    game.next_bot_balance = 0
    bots.balance_bots(game, now=0.0)
    assert sum(1 for p in game.players.values() if p.get("bot")) == 2

    bots.balance_bots(game, now=0.1)
    assert sum(1 for p in game.players.values() if p.get("bot")) == 2

    bots.balance_bots(game, now=0.3)
    assert sum(1 for p in game.players.values() if p.get("bot")) == 3

    game.settings["bot_count"] = 0
    bots.balance_bots(game, now=0.6)
    assert sum(1 for p in game.players.values() if p.get("bot")) == 0


@pytest.mark.parametrize('with_bot', [False, True])
def test_concurrent_admission_rechecks_cap_after_accept_and_evicts_atomically(with_bot):
    async def flow():
        game = Game(_noop_save_score)
        game.spawn_zombies = lambda *_a, **_k: None
        game.players = {f'h{i}': _player(f'h{i}') for i in range(199)}
        if with_bot:
            game.players['b'] = {**_player('b'), 'bot': True}
        ready = asyncio.Event()
        waiting = 0

        async def handshake(i):
            nonlocal waiting
            # Both connections pass the pre-accept check with 199 humans.
            assert sum(not p.get('bot') for p in game.players.values()) == 199
            waiting += 1
            if waiting == 2:
                ready.set()
            await ready.wait()
            return await game.admit_player({'name': f'New{i}', 'skin': 'soldier'}, None)

        admitted = await asyncio.gather(handshake(1), handshake(2))
        assert sum(p is not None for p in admitted) == 1
        assert len(game.players) == 200
        assert sum(not p.get('bot') for p in game.players.values()) == 200
        assert 'b' not in game.players
    asyncio.run(flow())


def test_random_spawn_spread_over_400_samples():
    game = Game(_noop_save_score)
    points = [spawning.spawn_position(game) for _ in range(400)]
    assert all(free(x, z) for x, z in points)
    assert all(not safe_zone_at(x, z) for x, z in points)
    assert all(-780 <= x <= 780 and -780 <= z <= 780 for x, z in points)
    quadrants = {
        'NE': sum(1 for x, z in points if x >= 0 and z >= 0),
        'NW': sum(1 for x, z in points if x < 0 and z >= 0),
        'SE': sum(1 for x, z in points if x >= 0 and z < 0),
        'SW': sum(1 for x, z in points if x < 0 and z < 0),
    }
    assert all(count > 0 for count in quadrants.values())
    assert sum(1 for x, z in points if math.hypot(x, z) < 25) == 0


def test_bot_generated_nicknames_are_unique_fictional_foreign_handles():
    game = Game(_noop_save_score)
    for i in range(200):
        name = bots.nickname(game)
        assert name.isascii() and name.isalpha()
        assert name not in {p['name'] for p in game.players.values()}
        assert any(name == first+last for first in bots.FIRST for last in bots.LAST)
        game.players[str(i)] = {'name': name}


def test_bot_brain_moves_and_fires_using_real_combat_and_ammunition(monkeypatch):
    game = Game(_noop_save_score)
    game.spawn_zombies = lambda *_a, **_k: None
    game.persist = lambda *_a: None
    game.zombie_factor = 0
    game.bosses.clear()
    p = game.add_player({'name': 'RavenRidge', 'skin': 'fbi'}, None, bot=True)
    now = engine_module.time.monotonic()
    sx, sz = _outside_safe_spot(base=220)
    p.update(x=sx, z=sz, born=now-2, protected_until=0, awaiting_input=False, brain_at=0)
    # Manually spawned test bots must unlock weapons before AI auto-equip runs.
    p['inventory']['ak47'] = {'ammo': WEAPONS['ak47']['mag'], 'reserve': WEAPONS['ak47']['reserve']}
    target = _player('human', name='Target', x=sx, z=sz + 10, hp=1000)
    target.update(born=now, input_time=now, last_spawn=now)
    game.players[target['id']] = target
    game.settings['bot_count'] = 1
    monkeypatch.setattr(bots, 'wall_distance', lambda *_a, **_k: 1.0)
    monkeypatch.setattr(combat, 'wall_distance', lambda *_a, **_k: 1.0)
    monkeypatch.setattr(bots.random, 'random', lambda: .5)
    monkeypatch.setattr(bots.random, 'uniform', lambda a, b: (a+b)/2)
    monkeypatch.setattr(bots.random, 'choice', lambda seq: seq[0])
    for i in range(50):
        game.update(.05, now+i*.05)
    assert math.hypot(p['x'], p['z']) > .1
    assert p['weapon'] == 'ak47'
    assert p['ammo'] < WEAPONS[p['weapon']]['mag']
    assert target['hp'] < 1000
    assert any(e['type'] == 'shot' and e['owner'] == p['id'] for e in game.events)

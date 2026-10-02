"""Focused boss feature tests: API contract, WS sync, and isolated combat/respawn mechanics."""

import asyncio
import contextlib
import json
import math
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
import websockets

sys.path.insert(0, "/app/backend")

import combat as combat_module
from boss_catalog import BOSS_TYPES, boss_died, create_boss, initial_bosses
from boss_combat import update_boss_hazards
from bosses import begin_attack, resolve_attack, update_bosses
from combat import shoot
from engine import Game


def _base_url() -> str:
    base = os.environ.get("REACT_APP_BACKEND_URL", "").strip()
    if not base:
        env_file = Path("/app/frontend/.env")
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.startswith("REACT_APP_BACKEND_URL="):
                    base = line.split("=", 1)[1].strip()
                    if base:
                        os.environ["REACT_APP_BACKEND_URL"] = base
                    break
    if not base:
        raise RuntimeError("REACT_APP_BACKEND_URL is required for public endpoint testing")
    return base.rstrip("/")


BASE_URL = _base_url()


async def _noop_save_score(_player):
    return None


def _ws_url(token: str) -> str:
    parsed = urlparse(BASE_URL)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return f"{scheme}://{parsed.netloc}/api/ws/{token}"


def _player(pid: str, x: float, z: float, *, weapon: str = "ak47", hp: int = 100):
    return {
        "id": pid,
        "name": pid,
        "weapon": weapon,
        "skin": "soldier",
        "x": x,
        "z": z,
        "y": 0.0,
        "angle": 0.0,
        "hp": hp,
        "ammo": 30,
        "reserve": 120,
        "score": 0,
        "kills": 0,
        "pvp": 0,
        "stamina": 100,
        "reload_until": 0,
        "last_shot": -999.0,
        "protected_until": 0,
        "awaiting_input": False,
        "input_time": 0,
        "born": 0,
        "died_at": 0,
        "last_spawn": 0,
        "trigger": False,
        "killer": "",
        "statuses": {},
        "vx": 0,
        "vz": 0,
        "controls": {"x": 0, "z": 0, "fire": False, "sprint": False},
    }


async def _recv_state(ws, timeout=6.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
        if msg.get("type") == "state":
            return msg
    raise AssertionError("Timed out waiting for state message")


# Module: public /api/bosses contract + fixed initial roster/positions/hp
def test_public_bosses_contract_all_four_alive_with_expected_stats():
    response = requests.get(f"{BASE_URL}/api/bosses", timeout=15)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 4
    by_type = {b["boss_type"]: b for b in data}
    assert set(by_type.keys()) == {"hansel", "symbiote", "xenomorph", "ash_titan"}
    assert all(item["alive"] is True for item in data)
    assert by_type["hansel"]["max_hp"] == 5000 and by_type["hansel"]["hp"] == 5000
    assert by_type["symbiote"]["max_hp"] == 6000 and by_type["symbiote"]["hp"] == 6000
    assert by_type["xenomorph"]["max_hp"] == 10000 and by_type["xenomorph"]["hp"] == 10000
    assert by_type["ash_titan"]["max_hp"] == 8000 and by_type["ash_titan"]["hp"] == 8000
    assert (by_type["hansel"]["x"], by_type["hansel"]["z"]) == (80, 0)
    assert (by_type["symbiote"]["x"], by_type["symbiote"]["z"]) == (-80, 0)
    assert (by_type["xenomorph"]["x"], by_type["xenomorph"]["z"]) == (0, 80)
    assert (by_type["ash_titan"]["x"], by_type["ash_titan"]["z"]) == (0, -80)


# Module: real two-client websocket state sync uses shared global bosses
def test_two_real_ws_clients_observe_same_shared_boss_snapshot():
    async def _flow():
        suffix = str(int(time.time()) % 100000)
        j1 = requests.post(f"{BASE_URL}/api/join", json={"name": f"B1{suffix}", "weapon": "ak47"}, timeout=15)
        j2 = requests.post(f"{BASE_URL}/api/join", json={"name": f"B2{suffix}", "weapon": "m4"}, timeout=15)
        assert j1.status_code == 200 and j2.status_code == 200
        ws1 = await websockets.connect(_ws_url(j1.json()["token"]), open_timeout=10)
        ws2 = await websockets.connect(_ws_url(j2.json()["token"]), open_timeout=10)
        try:
            assert json.loads(await asyncio.wait_for(ws1.recv(), timeout=6))["type"] == "welcome"
            assert json.loads(await asyncio.wait_for(ws2.recv(), timeout=6))["type"] == "welcome"
            s1 = await _recv_state(ws1)
            s2 = await _recv_state(ws2)
            b1 = {(b["id"], b["hp"], b["x"], b["z"], b["generation"]) for b in s1.get("bosses", [])}
            b2 = {(b["id"], b["hp"], b["x"], b["z"], b["generation"]) for b in s2.get("bosses", [])}
            assert len(b1) == 4 and len(b2) == 4
            assert b1 == b2
        finally:
            with contextlib.suppress(Exception):
                await ws1.close()
            with contextlib.suppress(Exception):
                await ws2.close()

    asyncio.run(_flow())


# Module: death bookkeeping and randomized respawn window only once per death
def test_boss_death_sets_single_respawn_window_and_respawns_full_hp(monkeypatch):
    game = Game(_noop_save_score)
    boss = game.bosses["boss-hansel"]
    boss["hp"] = 0
    game.boss_projectiles.append({"id": "p1", "owner": boss["id"], "kind": "rocket"})
    game.boss_zones.append({"id": "z1", "owner": boss["id"], "x": 0, "z": 0, "r": 2, "until": 999, "next_tick": 0})
    monkeypatch.setattr("boss_catalog.random.uniform", lambda _a, _b: 420.0)

    boss_died(game, boss, now=100.0)
    first_respawn_at = boss["respawn_at"]
    boss_died(game, boss, now=101.0)

    assert first_respawn_at == 520.0
    assert boss["respawn_at"] == first_respawn_at
    assert game.boss_projectiles == []
    assert game.boss_zones == []

    update_bosses(game, dt=0.1, now=519.9)
    assert game.bosses["boss-hansel"]["hp"] == 0
    update_bosses(game, dt=0.1, now=520.1)
    reborn = game.bosses["boss-hansel"]
    assert reborn["hp"] == 5000 and reborn["max_hp"] == 5000
    assert reborn["generation"] == 2
    assert (reborn["x"], reborn["z"]) == BOSS_TYPES["hansel"]["home"]


# Module: Hansel target detection within 50m with LOS gate and idle otherwise
def test_hansel_detection_requires_50m_and_los(monkeypatch):
    game = Game(_noop_save_score)
    boss = game.bosses["boss-hansel"]
    near = _player("p1", boss["x"], boss["z"] + 49.0)
    far = _player("p2", boss["x"], boss["z"] + 51.0)
    game.players = {far["id"]: far}

    monkeypatch.setattr("bosses.wall_distance", lambda *_a, **_k: 1.0)
    update_bosses(game, dt=0.1, now=9.8)
    assert boss["target_id"] == ""
    assert boss["action"] == "idle"

    game.players[near["id"]] = near
    update_bosses(game, dt=0.1, now=10.0)
    assert boss["target_id"] == "p1"

    game.players = {near["id"]: near}
    monkeypatch.setattr("bosses.wall_distance", lambda *_a, **_k: 0.1)
    boss["target_id"] = ""
    update_bosses(game, dt=0.1, now=10.2)
    assert boss["target_id"] == ""


# Module: Hansel laser/rockets/leap mechanics (LOS, projectile count, jump arc + landing AoE)
def test_hansel_laser_rockets_and_leap_damage(monkeypatch):
    game = Game(_noop_save_score)
    boss = create_boss("hansel")
    target = _player("p", boss["x"], boss["z"] + 20.0)
    game.players[target["id"]] = target

    begin_attack(boss, "laser", target, now=1.0)
    monkeypatch.setattr("boss_combat.wall_distance", lambda *_a, **_k: 1.0)
    hp_before = target["hp"]
    resolve_attack(game, boss, now=2.2)
    assert target["hp"] < hp_before

    target["hp"] = 100
    begin_attack(boss, "laser", target, now=3.0)
    monkeypatch.setattr("boss_combat.wall_distance", lambda *_a, **_k: 0.2)
    resolve_attack(game, boss, now=4.2)
    assert target["hp"] == 100

    begin_attack(boss, "rockets", target, now=5.0)
    resolve_attack(game, boss, now=6.0)
    assert len(game.boss_projectiles) == 3
    monkeypatch.setattr("boss_combat.wall_distance", lambda *_a, **_k: 1.0)
    hp_before = target["hp"]
    for _ in range(30):
        update_boss_hazards(game, dt=0.1, now=6.2)
        if target["hp"] < hp_before:
            break
    assert target["hp"] < hp_before

    target["hp"] = 100
    begin_attack(boss, "leap", target, now=7.0)
    resolve_attack(game, boss, now=7.9)
    assert boss["action"] == "leap"
    hp_before = target["hp"]
    update_bosses(type("G", (), {"bosses": {"b": boss}, "players": game.players, "boss_projectiles": [], "boss_zones": [], "events": []})(), dt=0.5, now=8.3)
    assert boss["y"] > 0
    resolve_attack(game, boss, now=9.3)
    assert target["hp"] < hp_before


# Module: Symbiote web status + blink relocation, and webbed slow effect on movement
def test_symbiote_web_and_blink_and_webbed_slow(monkeypatch):
    game = Game(_noop_save_score)
    boss = create_boss("symbiote")
    target = _player("p", boss["x"], boss["z"] + 10.0)
    game.players[target["id"]] = target
    monkeypatch.setattr("boss_combat.wall_distance", lambda *_a, **_k: 1.0)
    monkeypatch.setattr("bosses.free", lambda *_a, **_k: True)
    monkeypatch.setattr("boss_combat.free", lambda *_a, **_k: True)

    begin_attack(boss, "web", target, now=1.0)
    resolve_attack(game, boss, now=2.0)
    assert len(game.boss_projectiles) == 1
    for _ in range(20):
        update_boss_hazards(game, dt=0.1, now=2.2)
        if "webbed" in target["statuses"]:
            break
    assert "webbed" in target["statuses"]

    runner = _player("runner", 0, 0)
    runner["controls"] = {"x": 1.0, "z": 0.0, "fire": False, "sprint": True}
    runner["input_time"] = 10.0
    runner["statuses"] = {"webbed": {"until": 999}}
    game.players[runner["id"]] = runner
    monkeypatch.setattr("engine.move", lambda p, dx, dz: p.update(x=p["x"] + dx, z=p["z"] + dz))
    monkeypatch.setattr("engine.update_zombies", lambda *_a, **_k: None)
    monkeypatch.setattr("engine.update_projectiles", lambda *_a, **_k: None)
    monkeypatch.setattr("engine.update_statuses", lambda *_a, **_k: None)
    monkeypatch.setattr("engine.update_bosses", lambda *_a, **_k: None)
    game.update(dt=0.1, now=10.0)
    assert math.isclose(math.hypot(runner["vx"], runner["vz"]), 4.5, rel_tol=0.01)

    old = (boss["x"], boss["z"])
    begin_attack(boss, "blink", target, now=3.0)
    resolve_attack(game, boss, now=3.9)
    resolve_attack(game, boss, now=4.5)
    assert (boss["x"], boss["z"]) != old
    assert math.hypot(boss["x"] - target["x"], boss["z"] - target["z"]) <= 12


# Module: Xenomorph ability damage variants (leap/claw/bite/tail)
def test_xenomorph_distinct_attacks_apply_damage(monkeypatch):
    game = Game(_noop_save_score)
    game.persist = lambda _p: None
    boss = create_boss("xenomorph")
    target = _player("p", boss["x"], boss["z"] + 3.0, hp=500)
    game.players[target["id"]] = target
    monkeypatch.setattr("boss_combat.wall_distance", lambda *_a, **_k: 1.0)
    monkeypatch.setattr("bosses.free", lambda *_a, **_k: True)

    total_before = target["hp"]
    begin_attack(boss, "claw", target, now=1.0)
    resolve_attack(game, boss, now=1.9)
    hp_after_claw = target["hp"]
    begin_attack(boss, "bite", target, now=2.0)
    resolve_attack(game, boss, now=2.9)
    hp_after_bite = target["hp"]
    begin_attack(boss, "tail", target, now=3.0)
    resolve_attack(game, boss, now=3.9)
    hp_after_tail = target["hp"]
    begin_attack(boss, "leap", target, now=4.0)
    resolve_attack(game, boss, now=4.9)
    resolve_attack(game, boss, now=6.2)

    assert hp_after_claw < total_before
    assert hp_after_bite < hp_after_claw
    assert hp_after_tail < hp_after_bite
    assert target["hp"] < hp_after_tail


# Module: Ash Titan quake/lava/slam and hazard lifecycle expiry
def test_ash_titan_quake_lava_slam_and_zone_expiry(monkeypatch):
    game = Game(_noop_save_score)
    boss = create_boss("ash_titan")
    target = _player("p", boss["x"], boss["z"] + 2.0)
    game.players[target["id"]] = target
    monkeypatch.setattr("boss_combat.wall_distance", lambda *_a, **_k: 1.0)
    monkeypatch.setattr("bosses.free", lambda *_a, **_k: True)

    hp_before = target["hp"]
    begin_attack(boss, "quake", target, now=1.0)
    resolve_attack(game, boss, now=2.2)
    assert target["hp"] < hp_before

    hp_before = target["hp"]
    begin_attack(boss, "slam", target, now=2.5)
    resolve_attack(game, boss, now=3.4)
    assert target["hp"] < hp_before

    begin_attack(boss, "lava", target, now=4.0)
    resolve_attack(game, boss, now=4.9)
    assert len(game.boss_zones) >= 1
    hp_before = target["hp"]
    update_boss_hazards(game, dt=0.6, now=5.5)
    assert target["hp"] < hp_before

    update_boss_hazards(game, dt=0.2, now=13.2)
    assert len(game.boss_zones) == 0


# Module: player weapons can damage large bosses; dead bosses stop taking damage and get respawn timer
def test_player_shots_damage_boss_and_dead_boss_not_targetable(monkeypatch):
    game = Game(_noop_save_score)
    boss = create_boss("hansel")
    game.bosses = {boss["id"]: boss}
    player = _player("shooter", boss["x"], boss["z"] - 30.0, weapon="ak47")
    player["angle"] = 0.0
    game.players[player["id"]] = player
    monkeypatch.setattr(combat_module, "wall_distance", lambda *_a, **_k: 1.0)
    monkeypatch.setattr("boss_catalog.random.uniform", lambda _a, _b: 333.0)

    hp_before = boss["hp"]
    for i in range(10):
        shoot(game, player, now=1.0 + i)
    assert boss["hp"] < hp_before

    boss["hp"] = 1
    shoot(game, player, now=100.0)
    assert boss["hp"] == 0
    assert boss["respawn_at"] == 433.0
    score_after_kill = player["score"]
    shoot(game, player, now=101.0)
    assert player["score"] == score_after_kill


# Module: initial roster integrity in isolated game state (4 distinct homes, all alive)
def test_isolated_game_starts_with_four_distinct_alive_bosses():
    bosses = initial_bosses()
    assert len(bosses) == 4
    homes = {(b["x"], b["z"]) for b in bosses.values()}
    assert homes == {(80.0, 0.0), (-80.0, 0.0), (0.0, 80.0), (0.0, -80.0)}
    assert all(b["hp"] == b["max_hp"] and b["hp"] > 0 for b in bosses.values())



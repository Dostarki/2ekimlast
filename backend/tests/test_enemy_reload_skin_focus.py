"""Focused DEADZONE assertions for enemy contracts + short public websocket checks."""

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

from combat import hurt
from enemy_attacks import launch_swarm, update_flame
from enemy_types import ENEMY_TYPES, spawn_enemies
from engine import Game
from zombies import update_zombies


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
        raise RuntimeError("REACT_APP_BACKEND_URL is required for public endpoint checks")
    return base.rstrip("/")


BASE_URL = _base_url()


async def _noop_save_score(_player):
    return None


def _ws_url(token: str) -> str:
    parsed = urlparse(BASE_URL)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return f"{scheme}://{parsed.netloc}/api/ws/{token}"


def _player(pid: str, x: float, z: float, hp: int = 100):
    return {
        "id": pid,
        "name": pid,
        "weapon": "ak47",
        "skin": "soldier",
        "x": x,
        "z": z,
        "angle": 0.0,
        "hp": hp,
        "awaiting_input": False,
        "protected_until": 0,
        "ammo": 30,
        "reserve": 120,
        "score": 0,
        "kills": 0,
        "pvp": 0,
        "reload_until": 0,
        "last_shot": -999,
        "controls": {"x": 0, "z": 0, "fire": False, "sprint": False},
        "input_time": 0,
        "vx": 0,
        "vz": 0,
        "statuses": {},
    }


async def _recv_state(ws, timeout=6.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
        if msg.get("type") == "state":
            return msg
    raise AssertionError("Timed out waiting for state")


async def _connect(name: str, weapon: str = "ak47", skin: str = "soldier"):
    joined = requests.post(f"{BASE_URL}/api/join", json={"name": name, "weapon": weapon, "skin": skin}, timeout=15)
    assert joined.status_code == 200
    ws = await websockets.connect(_ws_url(joined.json()["token"]), open_timeout=10)
    welcome = json.loads(await asyncio.wait_for(ws.recv(), timeout=6))
    assert welcome.get("type") == "welcome"
    state = await _recv_state(ws)
    return ws, welcome, state


# Module: enemy profile constants requested in latest balancing update
def test_enemy_profiles_hp_detection_and_ranges():
    assert ENEMY_TYPES["immolator"]["hp"] == 950
    assert ENEMY_TYPES["hive"]["hp"] == 420
    assert ENEMY_TYPES["normal"]["detection"] == 15
    assert ENEMY_TYPES["immolator"]["detection"] == 20
    assert ENEMY_TYPES["immolator"]["flame_range"] == 25
    assert ENEMY_TYPES["hive"]["swarm_count"] == 3
    assert ENEMY_TYPES["hive"]["swarm_cooldown"] == 3.5


# Module: spawn distribution contract (every 10th successful spawn is fiery)
def test_every_10th_successful_spawn_is_immolator(monkeypatch):
    game = Game(_noop_save_score)
    player = _player("p", 0.0, 0.0)
    attempts = {"n": 0}

    def controlled_free(_x, _z):
        attempts["n"] += 1
        return attempts["n"] > 3

    monkeypatch.setattr("enemy_types.free", controlled_free)
    spawn_enemies(game, player, 30)
    assert len(game.zombies) == 30
    immolators = sorted(int(zid[1:]) for zid, z in game.zombies.items() if z["enemy_type"] == "immolator")
    assert immolators == [10, 20, 30]


# Module: hive swarm cadence (triple launch, 3.5s cooldown, cap=6)
def test_hive_launch_swarm_triple_with_cap_and_cooldown():
    game = Game(_noop_save_score)
    now = 50.0
    hive = {"id": "h1", "enemy_type": "hive", "x": 0.0, "z": 0.0, "last_special": -999, "attack_until": 0, "hp": 420}
    target = _player("p1", 5.0, 0.0)

    launch_swarm(game, hive, target, now)
    assert len(game.swarms) == 3

    launch_swarm(game, hive, target, now + 1.0)
    assert len(game.swarms) == 3

    launch_swarm(game, hive, target, now + 3.6)
    assert len(game.swarms) == 6

    launch_swarm(game, hive, target, now + 7.3)
    assert len(game.swarms) == 6


# Module: hive death cleanup must remove all swarms and poison same tick
def test_hive_death_clears_all_swarm_entries_and_source_poison_same_tick():
    game = Game(_noop_save_score)
    hive = {"id": "h1", "enemy_type": "hive", "x": 0.0, "z": 0.0, "hp": 420, "zombie": True}
    victim = _player("victim", 1.0, 1.0)
    victim["statuses"] = {"poison": {"source": "h1", "name": "Kovan zehri", "until": 999, "next_tick": 10, "damage": 4}}
    game.zombies[hive["id"]] = hive
    game.players[victim["id"]] = victim
    game.swarms.extend([
        {"id": "s1", "owner": "h1", "target": victim["id"], "x": 0.0, "z": 0.0, "until": 999, "last_hit": 0},
        {"id": "s2", "owner": "h1", "target": victim["id"], "x": 0.0, "z": 0.0, "until": 999, "last_hit": 0},
    ])

    hurt(game, hive, amount=500, owner=None, now=10.0)
    assert hive["hp"] == 0
    assert [s for s in game.swarms if s["owner"] == "h1"] == []
    assert "poison" not in victim["statuses"]


# Module: normal detection 15m + persistent target memory beyond range/LOS + memory clear on death/disconnect
def test_detection_memory_persistence_and_memory_stop_conditions(monkeypatch):
    game = Game(_noop_save_score)
    now = 100.0
    enemy = {
        "id": "z1",
        "x": 0.0,
        "z": 0.0,
        "angle": 0.0,
        "hp": 100,
        "zombie": True,
        "enemy_type": "normal",
        "variant": 0,
        "speed": 2.2,
        "last_attack": 0,
        "mode": "wander",
        "wander_until": 0,
        "target_id": "",
    }
    player = _player("p1", 0.0, 14.0)
    game.zombies[enemy["id"]] = enemy
    game.players[player["id"]] = player

    monkeypatch.setattr("zombies.wall_distance", lambda *_args, **_kwargs: 1.0)
    update_zombies(game, [player], dt=0.1, now=now)
    assert enemy["target_id"] == player["id"]

    # Move far beyond 125m and force LOS blocked; remembered target should persist.
    player["x"], player["z"] = 0.0, 140.0
    monkeypatch.setattr("zombies.wall_distance", lambda *_args, **_kwargs: 0.2)
    update_zombies(game, [player], dt=0.1, now=now + 0.1)
    assert enemy["target_id"] == player["id"]

    # Player death clears memory.
    player["hp"] = 0
    monkeypatch.setattr("zombies.wall_distance", lambda *_args, **_kwargs: 1.0)
    update_zombies(game, [], dt=0.1, now=now + 0.2)
    assert enemy["target_id"] == ""

    # Re-acquire then disconnect clears memory as well.
    player["hp"] = 100
    player["x"], player["z"] = 0.0, 10.0
    update_zombies(game, [player], dt=0.1, now=now + 0.3)
    assert enemy["target_id"] == player["id"]
    game.players.pop(player["id"], None)
    update_zombies(game, [], dt=0.1, now=now + 0.4)
    assert enemy["target_id"] == ""


# Module: latest immolator flame range: 24m yes, 26m no, LOS blocks
def test_immolator_flame_damage_24m_not_26m_and_los_blocks(monkeypatch):
    game = Game(_noop_save_score)
    now = 200.0
    enemy = {
        "id": "im1",
        "enemy_type": "immolator",
        "x": 0.0,
        "z": 0.0,
        "angle": 0.0,
        "last_flame": 0,
        "flame_until": now + 1.0,
        "windup_until": 0,
        "mode": "attack",
        "last_attack": 0,
    }
    inside = _player("inside", 0.0, 24.0)
    outside = _player("outside", 0.0, 26.0)
    game.players[inside["id"]] = inside
    game.players[outside["id"]] = outside

    monkeypatch.setattr("enemy_attacks.wall_distance", lambda *_args, **_kwargs: 1.0)
    updated = update_flame(game, enemy, [inside, outside], now)
    assert updated is True
    assert inside["hp"] == 94
    assert outside["hp"] == 100

    # LOS blocked => no further damage even in-range.
    enemy["last_flame"] = now - 1
    inside["hp"] = 100
    monkeypatch.setattr("enemy_attacks.wall_distance", lambda *_args, **_kwargs: 0.2)
    update_flame(game, enemy, [inside], now + 0.2)
    assert inside["hp"] == 100


# Module: short public /api/join + websocket contract (skins, invalid skin, remote reload fields)
def test_public_join_skin_and_remote_reload_snapshot_contract():
    invalid_skin = requests.post(
        f"{BASE_URL}/api/join",
        json={"name": f"Bad{int(time.time())%10000}", "weapon": "ak47", "skin": "invalid_skin"},
        timeout=15,
    )
    assert invalid_skin.status_code == 422

    async def _flow():
        suffix = str(int(time.time()) % 100000)
        ws1, w1, s1 = await _connect(name=f"SkinA{suffix}", weapon="ak47", skin="soldier")
        ws2, _w2, _s2 = await _connect(name=f"SkinB{suffix}", weapon="ak117", skin="fbi")
        try:
            seen_skin = False
            remote_reload_seen = False
            for _ in range(80):
                # fire once to reduce ammo before reload request
                await ws1.send(json.dumps({"type": "input", "x": 0, "z": 0, "angle": s1["me"]["angle"], "fire": True}))
                await asyncio.sleep(0.06)
                await ws1.send(json.dumps({"type": "input", "x": 0, "z": 0, "angle": s1["me"]["angle"], "reload": True}))

                s1 = await _recv_state(ws1)
                s2 = await _recv_state(ws2)

                remote = next((p for p in s2.get("players", []) if p.get("id") == w1["id"]), None)
                if remote and remote.get("skin") == "soldier":
                    seen_skin = True
                if remote and remote.get("reload_duration", 0) > 0 and remote.get("reloading", 0) > 0:
                    remote_reload_seen = True
                    break
            assert seen_skin is True
            assert remote_reload_seen is True
        finally:
            with contextlib.suppress(Exception):
                await ws1.close()
            with contextlib.suppress(Exception):
                await ws2.close()

    asyncio.run(_flow())

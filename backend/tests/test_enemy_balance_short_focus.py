"""Short focused backend checks for latest enemy/audio/skin contracts (no long suites)."""

import asyncio
import contextlib
import hashlib
import json
import math
import os
import sys
import time
import wave
from array import array
from pathlib import Path
from urllib.parse import urlparse

import requests
import websockets

sys.path.insert(0, "/app/backend")

import combat as combat_module
import enemy_attacks as enemy_attacks_module
import enemy_navigation as enemy_navigation_module
import zombies as zombies_module
from combat import hurt
from enemy_attacks import launch_swarm, update_flame, update_swarms
from enemy_damage import update_statuses
from enemy_types import ENEMY_TYPES, make_enemy, spawn_enemies
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


def _player(pid: str, x: float, z: float, *, hp: int = 100, skin: str = "soldier"):
    return {
        "id": pid,
        "name": pid,
        "weapon": "ak47",
        "skin": skin,
        "x": x,
        "z": z,
        "angle": 0.0,
        "hp": hp,
        "ammo": 30,
        "reserve": 120,
        "score": 0,
        "kills": 0,
        "pvp": 0,
        "reload_until": 0,
        "last_shot": -999,
        "awaiting_input": False,
        "protected_until": 0,
        "input_time": 0,
        "born": 0,
        "died_at": 0,
        "killer": "",
        "vx": 0,
        "vz": 0,
        "statuses": {},
        "controls": {"x": 0, "z": 0, "fire": False, "sprint": False},
    }


def _ws_url(token: str) -> str:
    parsed = urlparse(BASE_URL)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return f"{scheme}://{parsed.netloc}/api/ws/{token}"


async def _recv_state(ws, timeout=6.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
        if msg.get("type") == "state":
            return msg
    raise AssertionError("Timed out waiting for state")


# Module: external health endpoints
def test_root_and_status_public_health():
    root = requests.get(f"{BASE_URL}/api/", timeout=12)
    assert root.status_code == 200
    root_data = root.json()
    assert root_data["name"] in ("DEADZONE", "LastZHood")
    assert root_data["status"] == "online"

    status = requests.get(f"{BASE_URL}/api/status", timeout=12)
    assert status.status_code == 200
    status_data = status.json()
    assert status_data["tick_rate"] == 20
    assert status_data["capacity"] == 200


# Module: enemy constants + speed profiles + spawn distribution contract
def test_enemy_profiles_and_spawn_distribution(monkeypatch):
    assert ENEMY_TYPES["immolator"]["hp"] == 950
    assert ENEMY_TYPES["hive"]["hp"] == 420
    assert ENEMY_TYPES["normal"]["detection"] == 15
    assert ENEMY_TYPES["immolator"]["flame_range"] == 25
    assert ENEMY_TYPES["normal"]["speed"] == 2.2
    assert ENEMY_TYPES["immolator"]["speed"] == 7.8
    assert ENEMY_TYPES["hellhound"]["speed"] == 9.2
    assert ENEMY_TYPES["hive"]["speed"] == 2.2
    assert ENEMY_TYPES["armored"]["speed"] == 2.5
    assert make_enemy(2, 0, 0)["speed"] == 6.8  # normal runner

    game = Game(_noop_save_score)
    monkeypatch.setattr("enemy_types.free", lambda *_args, **_kwargs: True)
    spawn_enemies(game, _player("p", 0, 0), 20)
    assert len(game.zombies) == 20
    immolators = [z for z in game.zombies.values() if z["enemy_type"] == "immolator"]
    hounds = [z for z in game.zombies.values() if z["enemy_type"] == "hellhound"]
    assert len(immolators) == 2
    assert len(hounds) == 3
    assert len({h["pack"] for h in hounds}) == 1


# Module: target memory + obstacle chase sanity
def test_permanent_pursuit_memory_and_forget_rules(monkeypatch):
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
        "speed": 6.8,
        "last_attack": -999,
        "mode": "wander",
        "wander_until": 0,
        "target_id": "",
    }
    player = _player("p1", 0.0, 14.5)
    game.zombies[enemy["id"]] = enemy
    game.players[player["id"]] = player

    monkeypatch.setattr(zombies_module, "wall_distance", lambda *_a, **_k: 1.0)
    update_zombies(game, [player], dt=0.1, now=now)
    assert enemy["target_id"] == player["id"]

    player["x"], player["z"] = 0.0, 140.0
    monkeypatch.setattr(zombies_module, "wall_distance", lambda *_a, **_k: 0.1)
    update_zombies(game, [player], dt=0.1, now=now + 0.1)
    assert enemy["target_id"] == player["id"]

    player["hp"] = 0
    update_zombies(game, [], dt=0.1, now=now + 0.2)
    assert enemy["target_id"] == ""

    player["hp"] = 100
    player["x"], player["z"] = 0.0, 10.0
    game.players[player["id"]] = player
    monkeypatch.setattr(zombies_module, "wall_distance", lambda *_a, **_k: 1.0)
    update_zombies(game, [player], dt=0.1, now=now + 0.3)
    assert enemy["target_id"] == player["id"]
    game.players.pop(player["id"], None)
    update_zombies(game, [], dt=0.1, now=now + 0.4)
    assert enemy["target_id"] == ""


def test_obstacle_chase_uses_path_segments(monkeypatch):
    game = Game(_noop_save_score)
    game.path_budget = 2
    enemy = {"id": "z", "x": 0.0, "z": 0.0, "angle": 0.0, "path": [], "next_path": 0}
    target = _player("p", 12.0, 0.0)

    monkeypatch.setattr(enemy_navigation_module, "wall_distance", lambda *_a, **_k: 0.2)
    monkeypatch.setattr(enemy_navigation_module, "path_to", lambda *_a, **_k: [(0.0, 6.0), (2.0, 10.0)])
    enemy_navigation_module.chase(game, enemy, target, speed=3.0, dt=1.0, now=1.0)
    assert enemy["z"] > 2.0
    assert enemy.get("path")


# Module: immolator flame rules (range, LOS block, no fireball projectile)
def test_flame_damage_works_inside_25_blocks_behind_wall_and_no_projectile(monkeypatch):
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
    inside = _player("in", 0.0, 24.9)
    outside = _player("out", 0.0, 25.2)

    monkeypatch.setattr(enemy_attacks_module, "wall_distance", lambda *_a, **_k: 1.0)
    update_flame(game, enemy, [inside, outside], now)
    assert inside["hp"] == 94
    assert outside["hp"] == 100
    assert game.projectiles == []
    assert any(e.get("type") == "enemy_attack" and e.get("kind") == "flame" for e in game.events)

    enemy["last_flame"] = now - 1
    inside["hp"] = 100
    monkeypatch.setattr(enemy_attacks_module, "wall_distance", lambda *_a, **_k: 0.2)
    update_flame(game, enemy, [inside], now + 0.2)
    assert inside["hp"] == 100


# Module: fiery death explosion contract + one-time trigger + chain reaction behavior
def test_immolator_death_explosion_radius_falloff_and_no_duplicate(monkeypatch):
    game = Game(_noop_save_score)
    game.persist = lambda _p: None
    monkeypatch.setattr(combat_module, "wall_distance", lambda *_a, **_k: 1.0)

    immolator = {"id": "im1", "enemy_type": "immolator", "x": 0.0, "z": 0.0, "hp": 1, "zombie": True}
    game.zombies["im1"] = immolator
    p_near = _player("near", 0.0, 1.0)
    p_edge = _player("edge", 0.0, 5.9)
    p_out = _player("out", 0.0, 6.2)
    game.players.update({p_near["id"]: p_near, p_edge["id"]: p_edge, p_out["id"]: p_out})

    hurt(game, immolator, 20, owner=None, now=1.0)
    first = [e for e in game.events if e.get("type") == "explosion" and e.get("kind") == "enemy_fire" and e.get("owner") == ""]
    assert len(first) == 1
    assert first[0]["x"] == 0.0 and first[0]["z"] == 0.0 and first[0]["r"] == 6
    assert p_near["hp"] < p_edge["hp"] < 100
    assert p_out["hp"] == 100

    # Re-hitting dead target should not emit duplicate explosion.
    events_before = len([e for e in game.events if e.get("type") == "explosion" and e.get("kind") == "enemy_fire"])
    hurt(game, immolator, 10, owner=None, now=1.1)
    events_after = len([e for e in game.events if e.get("type") == "explosion" and e.get("kind") == "enemy_fire"])
    assert events_after == events_before

    # Chain reaction sanity: a nearby weak immolator can trigger its own explosion once.
    second = {"id": "im2", "enemy_type": "immolator", "x": 4.0, "z": 0.0, "hp": 1, "zombie": True}
    game.zombies["im2"] = second
    hurt(game, second, 5, owner=None, now=2.0)
    chained = [e for e in game.events if e.get("type") == "explosion" and e.get("kind") == "enemy_fire" and e["x"] == 4.0]
    assert len(chained) == 1


# Module: hive swarm cadence + poison + instant cleanup on hive death, preserving other hive swarms
def test_hive_swarm_cadence_poison_and_cleanup_same_tick(monkeypatch):
    game = Game(_noop_save_score)
    game.persist = lambda _p: None
    now = 300.0

    hive1 = {"id": "h1", "enemy_type": "hive", "x": 0.0, "z": 0.0, "hp": 420, "zombie": True, "last_special": -999, "attack_until": 0}
    hive2 = {"id": "h2", "enemy_type": "hive", "x": 20.0, "z": 0.0, "hp": 420, "zombie": True, "last_special": -999, "attack_until": 0}
    target = _player("p1", 0.0, 0.7)
    game.zombies.update({"h1": hive1, "h2": hive2})
    game.players[target["id"]] = target

    launch_swarm(game, hive1, target, now)
    assert len([s for s in game.swarms if s["owner"] == "h1"]) == 3
    launch_swarm(game, hive1, target, now + 1.0)
    assert len([s for s in game.swarms if s["owner"] == "h1"]) == 3
    launch_swarm(game, hive1, target, now + 3.6)
    assert len([s for s in game.swarms if s["owner"] == "h1"]) == 6

    # Poison application from an active nearby swarm.
    first_swarm = next(s for s in game.swarms if s["owner"] == "h1")
    first_swarm["x"], first_swarm["z"], first_swarm["last_hit"] = 0.0, 0.0, now - 10
    monkeypatch.setattr(enemy_attacks_module, "wall_distance", lambda *_a, **_k: 1.0)
    update_swarms(game, dt=0.2, now=now + 4.0)
    assert target["statuses"]["poison"]["source"] == "h1"

    # Other hive keeps its swarm after h1 dies.
    game.swarms.append({"id": "s_other", "owner": "h2", "target": target["id"], "x": 20.0, "z": 0.0, "until": now + 20, "last_hit": 0, "spread": 0})
    hurt(game, hive1, amount=500, owner=None, now=now + 4.1)
    assert [s for s in game.swarms if s["owner"] == "h1"] == []
    assert any(s["owner"] == "h2" for s in game.swarms)
    assert "poison" not in target["statuses"]


# Module: hellhound bleeding + death attribution + respawn behavior
def test_hellhound_bleed_and_respawn_status_skin_contract(monkeypatch):
    game = Game(_noop_save_score)
    game.persist = lambda _p: None
    now = 400.0
    dog = {
        "id": "d1",
        "x": 0.0,
        "z": 0.0,
        "angle": 0.0,
        "hp": 85,
        "zombie": True,
        "enemy_type": "hellhound",
        "variant": 0,
        "speed": 9.2,
        "last_attack": -999,
        "mode": "wander",
        "wander_until": 0,
        "target_id": "",
    }
    victim = _player("p1", 0.0, 1.0, hp=100, skin="fbi")
    game.zombies[dog["id"]] = dog
    game.players[victim["id"]] = victim

    monkeypatch.setattr(zombies_module, "wall_distance", lambda *_a, **_k: 1.0)
    update_zombies(game, [victim], dt=0.1, now=now)
    bleed = victim["statuses"]["bleeding"]
    assert bleed["source"] == "d1"
    assert bleed["damage"] == 3
    assert math.isclose(bleed["until"], now + 5, rel_tol=0, abs_tol=0.001)

    victim["hp"] = 2
    bleed["next_tick"] = now + 0.1
    update_statuses(game, now + 0.2)
    assert victim["hp"] == 0
    assert victim["killer"] == "Hellhound · Bleeding"

    game.respawn(victim)
    assert victim["skin"] == "fbi"
    assert victim["statuses"] == {}


# Module: /api/join skin validation + short 2-client websocket skin/reload contract
def test_join_skin_validation_default_and_short_two_client_reload_observation():
    skins = ["soldier", "fbi", "civilian", "terrorist", "gang_male", "gang_female"]
    suffix = str(int(time.time()) % 100000)

    for i, skin in enumerate(skins):
        joined = requests.post(
            f"{BASE_URL}/api/join",
            json={"name": f"SK{i}{suffix}", "weapon": "ak47", "skin": skin},
            timeout=15,
        )
        assert joined.status_code == 200
        assert isinstance(joined.json().get("token"), str)

    invalid = requests.post(
        f"{BASE_URL}/api/join",
        json={"name": f"BAD{suffix}", "weapon": "ak47", "skin": "bad_skin"},
        timeout=15,
    )
    assert invalid.status_code == 422

    async def _flow():
        j1 = requests.post(
            f"{BASE_URL}/api/join",
            json={"name": f"P1{suffix}", "weapon": "ak47", "skin": "fbi"},
            timeout=15,
        )
        j2 = requests.post(
            f"{BASE_URL}/api/join",
            json={"name": f"P2{suffix}", "weapon": "ak117"},
            timeout=15,
        )
        assert j1.status_code == 200 and j2.status_code == 200

        ws1 = await websockets.connect(_ws_url(j1.json()["token"]), open_timeout=10)
        ws2 = await websockets.connect(_ws_url(j2.json()["token"]), open_timeout=10)
        try:
            w1 = json.loads(await asyncio.wait_for(ws1.recv(), timeout=6))
            w2 = json.loads(await asyncio.wait_for(ws2.recv(), timeout=6))
            assert w1["type"] == "welcome" and w2["type"] == "welcome"

            s1 = await _recv_state(ws1)
            s2 = await _recv_state(ws2)
            assert s1["me"]["skin"] == "fbi"
            assert s2["me"]["skin"] == "soldier"

            remote_reload_seen = False
            for _ in range(60):
                await ws1.send(json.dumps({"type": "input", "x": 0, "z": 0, "angle": s1["me"]["angle"], "fire": True}))
                await asyncio.sleep(0.06)
                await ws1.send(json.dumps({"type": "input", "x": 0, "z": 0, "angle": s1["me"]["angle"], "reload": True}))
                s1 = await _recv_state(ws1)
                s2 = await _recv_state(ws2)
                remote = next((p for p in s2.get("players", []) if p.get("id") == w1["id"]), None)
                if remote and remote.get("skin") == "fbi" and remote.get("reload_duration", 0) > 0 and remote.get("reloading", 0) > 0:
                    remote_reload_seen = True
                    break
            assert remote_reload_seen is True
        finally:
            with contextlib.suppress(Exception):
                await ws1.close()
            with contextlib.suppress(Exception):
                await ws2.close()

    asyncio.run(_flow())


# Module: creature audio assets and credit/source checks
def test_creature_audio_assets_credits_and_distinct_enemy_files():
    creatures = Path("/app/frontend/public/audio/creatures")
    files = sorted(creatures.glob("*.wav"))
    assert len(files) == 26

    hashes = {}
    for file in files:
        with wave.open(str(file), "rb") as wf:
            frames = wf.getnframes()
            assert frames > 0
            payload = wf.readframes(frames)
            samples = array("h")
            samples.frombytes(payload)
            assert max(abs(v) for v in samples) > 0
        hashes[file.name] = hashlib.sha256(file.read_bytes()).hexdigest()

    assert len({hashes[f"{kind}-attack.wav"] for kind in ["normal", "immolator", "hive", "armored", "hellhound"]}) >= 4

    credits = Path("/app/frontend/public/audio/CREDITS.txt").read_text(encoding="utf-8")
    assert "real voice performances" in credits
    assert "oscillator-generated sounds were removed" in credits
    assert "freesound.org/people/umnachtung" in credits
    assert "bigsoundbank.com/barking-dogs" in credits

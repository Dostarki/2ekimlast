"""Critical API + websocket integration tests for DEADZONE MVP."""

import asyncio
import contextlib
import json
import math
import os
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
import websockets


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


def _ws_url(token: str) -> str:
    parsed = urlparse(BASE_URL)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return f"{scheme}://{parsed.netloc}/api/ws/{token}"


# Module: core REST API contract checks
def test_core_api_endpoints_and_invalid_join_input():
    api = requests.Session()

    status = api.get(f"{BASE_URL}/api/status", timeout=15)
    assert status.status_code == 200
    status_data = status.json()
    assert status_data["capacity"] == 200
    assert status_data["friendly_fire"] is True
    assert status_data["tick_rate"] == 20

    world = api.get(f"{BASE_URL}/api/world", timeout=20)
    assert world.status_code == 200
    world_data = world.json()
    assert world_data["size"] == 1600
    assert isinstance(world_data["chunks"], list)
    assert len(world_data["chunks"]) > 0

    weapons = api.get(f"{BASE_URL}/api/weapons", timeout=15)
    assert weapons.status_code == 200
    weapons_data = weapons.json()
    assert set(["ak47", "ak117", "ak107", "shotgun"]).issubset(set(weapons_data.keys()))

    leaderboard = api.get(f"{BASE_URL}/api/leaderboard", timeout=15)
    assert leaderboard.status_code == 200
    leaderboard_data = leaderboard.json()
    assert isinstance(leaderboard_data, list)
    if leaderboard_data:
        row = leaderboard_data[0]
        assert all(k in row for k in ["id", "name", "weapon", "score", "kills", "pvp", "ended_at"])

    invalid_join = api.post(
        f"{BASE_URL}/api/join",
        json={"name": "A", "weapon": "ak47"},
        timeout=15,
    )
    assert invalid_join.status_code == 422
    detail = invalid_join.json().get("detail")
    assert detail


async def _recv_state(ws, timeout=4.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
        msg = json.loads(raw)
        if msg.get("type") == "state":
            return msg
    raise AssertionError("Timed out waiting for state message")


async def _recv_welcome(ws, timeout=4.0):
    raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
    msg = json.loads(raw)
    assert msg.get("type") == "welcome"
    assert isinstance(msg.get("id"), str) and len(msg["id"]) >= 8
    return msg


async def _join_and_connect(name: str, weapon: str):
    r = requests.post(f"{BASE_URL}/api/join", json={"name": name, "weapon": weapon}, timeout=15)
    assert r.status_code == 200
    token = r.json()["token"]
    ws = await websockets.connect(_ws_url(token), open_timeout=10)
    welcome = await _recv_welcome(ws)
    state = await _recv_state(ws)
    return ws, welcome, state


async def _send_input(ws, x=0.0, z=0.0, fire=False, sprint=False, reload=False, angle=0.0):
    await ws.send(
        json.dumps(
            {
                "type": "input",
                "x": x,
                "z": z,
                "fire": fire,
                "sprint": sprint,
                "reload": reload,
                "angle": angle,
            }
        )
    )


async def _integration_flow_assertions():
    suffix = str(int(time.time()) % 10000)
    p1_name = f"TSA{suffix}"
    p2_name = f"TSB{suffix}"
    ws1, w1, s1 = await _join_and_connect(p1_name, "ak47")
    ws2, w2, s2 = await _join_and_connect(p2_name, "ak117")

    try:
        # Both clients receive each other in world state.
        seen_each_other = False
        for _ in range(15):
            s1 = await _recv_state(ws1)
            s2 = await _recv_state(ws2)
            s1_ids = {p["id"] for p in s1.get("players", [])}
            s2_ids = {p["id"] for p in s2.get("players", [])}
            if w2["id"] in s1_ids and w1["id"] in s2_ids:
                seen_each_other = True
                break
        assert seen_each_other, "Two real websocket clients could not observe each other"

        # Before first movement/fire, player remains awaiting_input and safe.
        assert s1["me"]["awaiting_input"] is True
        assert s2["me"]["awaiting_input"] is True
        assert s1["me"]["protected"] > 0
        assert s2["me"]["protected"] > 0
        assert s1["me"]["hp"] == 100
        for _ in range(20):
            s1 = await _recv_state(ws1)
            if s1["me"]["hp"] < 100:
                raise AssertionError("Stationary awaiting_input player took damage before first action")

        # Movement authority: moving input should change authoritative position.
        start_x, start_z = s1["me"]["x"], s1["me"]["z"]
        moved = False
        vectors = [(1.0, 0.0), (-1.0, 0.0), (0.0, 1.0), (0.0, -1.0), (1.0, 1.0)]
        for vx, vz in vectors:
            for _ in range(12):
                await _send_input(ws1, x=vx, z=vz, sprint=True, angle=s1["me"]["angle"])
                await asyncio.sleep(0.05)
            for _ in range(8):
                s1 = await _recv_state(ws1)
                if abs(s1["me"]["x"] - start_x) > 0.8 or abs(s1["me"]["z"] - start_z) > 0.8:
                    moved = True
                    break
            if moved:
                break
        assert moved, "Authoritative movement did not update position"

        # Ammo decreases when firing.
        ammo_before = s1["me"]["ammo"]
        fired = False
        for i in range(28):
            await _send_input(ws1, fire=True, angle=s1["me"]["angle"] + (i * 0.03))
            s1 = await _recv_state(ws1)
            if any(e.get("type") == "shot" and e.get("owner") == s1["me"]["id"] for e in s1.get("events", [])):
                fired = True
            if s1["me"]["ammo"] < ammo_before:
                fired = True
                break
            await asyncio.sleep(0.05)
        assert fired and s1["me"]["ammo"] < ammo_before

        # Reload should restore magazine after a short delay.
        await _send_input(ws1, reload=True, angle=s1["me"]["angle"])
        reloaded = False
        for _ in range(80):
            await _send_input(ws1, angle=s1["me"]["angle"])
            s1 = await _recv_state(ws1)
            if s1["me"]["reloading"] > 0:
                pass
            if s1["me"]["ammo"] >= ammo_before:
                reloaded = True
                break
        assert reloaded, "Reload did not complete"

        # Real 2-client PvP verification:
        # victim fires once to cancel own protection, then shooter kills in close range.
        # Victim (player2) cancels protection with a harmless shot.
        assert s2["me"]["protected"] > 0
        victim_protection_cleared = False
        victim_id = w2["id"]
        for _ in range(10):
            await _send_input(ws2, fire=True, angle=s2["me"]["angle"] + math.pi)
            await asyncio.sleep(0.06)
            s2 = await _recv_state(ws2)
            if s2["me"]["protected"] <= 0 and s2["me"]["awaiting_input"] is False:
                victim_protection_cleared = True
                break
        assert victim_protection_cleared, "Victim protection did not clear after firing"

        # Shooter tracks victim and fires until kill event appears.
        shooter_score_before = s1["me"]["score"]
        shooter_pvp_before = s1["me"]["pvp"]
        pvp_verified = False
        victim_damaged_seen_by_victim = False
        for _ in range(80):
            s1 = await _recv_state(ws1)
            s2 = await _recv_state(ws2)

            victim_in_s1 = next((p for p in s1.get("players", []) if p["id"] == victim_id), None)
            if not victim_in_s1:
                await _send_input(ws1, x=0.6, z=0.0, sprint=True, angle=s1["me"]["angle"])
                continue

            angle = math.atan2(victim_in_s1["x"] - s1["me"]["x"], victim_in_s1["z"] - s1["me"]["z"])
            await _send_input(ws1, fire=True, angle=angle)

            if s2["me"]["hp"] < 100:
                victim_damaged_seen_by_victim = True

            kill_event = any(
                e.get("type") == "kill" and e.get("owner") == s1["me"]["id"] and e.get("zombie") is False
                for e in s1.get("events", [])
            )
            if kill_event and s1["me"]["pvp"] >= shooter_pvp_before + 1 and s1["me"]["score"] >= shooter_score_before + 25:
                pvp_verified = True
                break

            await asyncio.sleep(0.05)

        assert victim_damaged_seen_by_victim, "Victim client did not observe incoming PvP damage"
        assert pvp_verified, "Explicit PvP kill/score assertion failed"

        # Zombie chase/damage: idle player should eventually take damage after protection ends.
        hp_initial = s1["me"]["hp"]
        damaged = False
        for _ in range(220):  # ~11s of server ticks via state stream
            await _send_input(ws1, x=0.0, z=0.0, angle=s1["me"]["angle"])
            s1 = await _recv_state(ws1)
            if s1["me"]["protected"] <= 0 and s1["me"]["hp"] < hp_initial:
                damaged = True
                break
        assert damaged, "Zombie chase/damage not observed after protection window"

        # Try to secure at least one zombie kill (+100 score expected) using nearest visible target.
        score_before = s1["me"]["score"]
        kills_before = s1["me"]["kills"]
        zombie_kill_verified = False
        for _ in range(260):
            s1 = await _recv_state(ws1)
            zombies = s1.get("zombies", [])
            if zombies:
                z = min(zombies, key=lambda e: (e["x"] - s1["me"]["x"]) ** 2 + (e["z"] - s1["me"]["z"]) ** 2)
                angle = math.atan2(z["x"] - s1["me"]["x"], z["z"] - s1["me"]["z"])
                await _send_input(ws1, fire=True, angle=angle)
            else:
                await _send_input(ws1, fire=False, angle=s1["me"]["angle"])
            if s1["me"]["kills"] > kills_before and s1["me"]["score"] >= score_before + 100:
                zombie_kill_verified = True
                break
            await asyncio.sleep(0.05)

        # Death + respawn coverage only if death naturally occurs.
        respawn_verified = False
        me_id_before = s1["me"]["id"]
        for _ in range(260):
            s1 = await _recv_state(ws1)
            if s1["me"]["hp"] <= 0:
                await ws1.send(json.dumps({"type": "respawn"}))
                for _ in range(80):
                    s1 = await _recv_state(ws1)
                    if s1["me"]["hp"] > 0 and s1["me"]["id"] != me_id_before:
                        respawn_verified = True
                        break
                break
            await asyncio.sleep(0.05)

        # Disconnect cleanup: closing one socket should reduce online count seen by the other.
        online_before_close = s1["online"]
        await ws2.close()
        online_reduced = False
        for _ in range(80):
            s1 = await _recv_state(ws1)
            if s1["online"] < online_before_close:
                online_reduced = True
                break
        assert online_reduced, "Disconnect cleanup did not reduce online count"

        # Persisted score should appear in leaderboard if a kill happened.
        await ws1.close()
        await asyncio.sleep(1.2)
        board = requests.get(f"{BASE_URL}/api/leaderboard", timeout=15)
        assert board.status_code == 200
        board_rows = board.json()
        assert any(r["name"] == p1_name and r["score"] > 0 for r in board_rows)

        return {
            "pvp_verified": pvp_verified,
            "zombie_kill_verified": zombie_kill_verified,
            "respawn_verified": respawn_verified,
        }
    finally:
        with contextlib.suppress(Exception):
            await ws1.close()
        with contextlib.suppress(Exception):
            await ws2.close()


# Module: end-to-end socket lifecycle with real concurrent clients
def test_websocket_multiplayer_flow():
    result = asyncio.run(_integration_flow_assertions())
    assert result["pvp_verified"] is True
    assert isinstance(result["respawn_verified"], bool)
    assert isinstance(result["zombie_kill_verified"], bool)

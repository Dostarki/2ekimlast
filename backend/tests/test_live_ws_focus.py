"""Module: public API + gerçek websocket akışında seq/ack/ping ve kısa çoklu istemci örneklemi."""

import asyncio
import contextlib
import json
import os
import statistics
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
        raise RuntimeError("REACT_APP_BACKEND_URL is required")
    return base.rstrip("/")


BASE_URL = _base_url()


def _ws_url(token: str) -> str:
    parsed = urlparse(BASE_URL)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return f"{scheme}://{parsed.netloc}/api/ws/{token}"


async def _recv_until(ws, predicate, timeout=6.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
        msg = json.loads(raw)
        if predicate(msg):
            return msg
    raise AssertionError("Timed out while waiting for websocket message")


async def _recv_state(ws, timeout=6.0):
    return await _recv_until(ws, lambda m: m.get("type") == "state", timeout=timeout)


async def _join_player(name: str, weapon: str = "ak47", skin: str = "soldier"):
    res = requests.post(f"{BASE_URL}/api/join", json={"name": name, "weapon": weapon, "skin": skin}, timeout=15)
    assert res.status_code == 200
    token = res.json()["token"]
    ws = await websockets.connect(_ws_url(token), open_timeout=12)
    welcome = await _recv_until(ws, lambda m: m.get("type") == "welcome", timeout=6)
    state = await _recv_state(ws)
    return ws, welcome, state


def test_public_status_tick_fields_present():
    response = requests.get(f"{BASE_URL}/api/status", timeout=12)
    assert response.status_code == 200
    data = response.json()
    assert data["tick_rate"] == 20
    assert "tick_ms" in data
    assert "coalesced_states" in data


def test_two_real_ws_players_seq_ack_move_fire_reload_ping_and_remote_visibility():
    async def _flow():
        ws1, w1, s1 = await _join_player(f"TestNetA{int(time.time())%10000}", "ak47", "soldier")
        ws2, w2, s2 = await _join_player(f"TestNetB{int(time.time())%10000}", "ak117", "fbi")
        try:
            # Monotonic state.seq and server_time.
            seqs, times = [], []
            for _ in range(8):
                s1 = await _recv_state(ws1)
                seqs.append(s1["seq"])
                times.append(s1["server_time"])
            assert all(seqs[i] < seqs[i + 1] for i in range(len(seqs) - 1))
            assert all(times[i] < times[i + 1] for i in range(len(times) - 1))

            # Remote visibility + bosses payload present.
            seen_other = False
            for _ in range(15):
                s1 = await _recv_state(ws1)
                s2 = await _recv_state(ws2)
                if any(p["id"] == w2["id"] for p in s1.get("players", [])) and any(
                    p["id"] == w1["id"] for p in s2.get("players", [])
                ):
                    seen_other = True
                    break
            assert seen_other
            assert isinstance(s1.get("bosses", []), list)

            # Movement start + ack_seq mirror through me.input_seq.
            seq = 500
            start_pos = (s1["me"]["x"], s1["me"]["z"])
            moved = False
            acked = False
            for _ in range(25):
                seq += 1
                await ws1.send(json.dumps({"type": "input", "x": 1, "z": 0, "sprint": True, "fire": False, "angle": s1["me"]["angle"], "seq": seq}))
                s1 = await _recv_state(ws1)
                if abs(s1["me"]["x"] - start_pos[0]) > 0.8:
                    moved = True
                if s1["me"].get("input_seq", 0) >= seq:
                    acked = True
                if moved and acked:
                    break
            assert moved
            assert acked

            # Stop command should settle velocity close to zero.
            for _ in range(12):
                seq += 1
                await ws1.send(json.dumps({"type": "input", "x": 0, "z": 0, "fire": False, "sprint": False, "angle": s1["me"]["angle"], "seq": seq}))
                s1 = await _recv_state(ws1)
            assert abs(s1["me"].get("vx", 0)) < 0.8
            assert abs(s1["me"].get("vz", 0)) < 0.8

            # Fire => ammo drops.
            ammo_before = s1["me"]["ammo"]
            fired = False
            for i in range(30):
                seq += 1
                await ws1.send(json.dumps({"type": "input", "x": 0, "z": 0, "fire": True, "fire_pressed": True, "angle": s1["me"]["angle"] + (i * 0.02), "seq": seq}))
                s1 = await _recv_state(ws1)
                if s1["me"]["ammo"] < ammo_before:
                    fired = True
                    break
            assert fired

            # Reload cycle.
            await ws1.send(json.dumps({"type": "input", "x": 0, "z": 0, "fire": False, "reload": True, "angle": s1["me"]["angle"], "seq": seq + 1}))
            reloaded = False
            for _ in range(90):
                s1 = await _recv_state(ws1)
                if s1["me"]["ammo"] >= ammo_before:
                    reloaded = True
                    break
            assert reloaded

            # Explicit ping/pong RTT on same socket.
            t0 = int(time.time() * 1000)
            wall_start = time.monotonic()
            await ws1.send(json.dumps({"type": "ping", "time": t0}))
            pong = await _recv_until(ws1, lambda m: m.get("type") == "pong" and m.get("time") == t0, timeout=4)
            rtt_ms = (time.monotonic() - wall_start) * 1000
            assert pong["time"] == t0
            assert rtt_ms < 2000
        finally:
            with contextlib.suppress(Exception):
                await ws1.close()
            with contextlib.suppress(Exception):
                await ws2.close()

    asyncio.run(_flow())


def test_six_player_five_second_sample_reports_rtt_p50_p95_state_frequency():
    async def _flow():
        clients = []
        intervals = []
        rtts = []
        tick_ms = []
        state_count = 0
        last_state_time = None
        ping_marks = {}
        collector = None
        try:
            for i in range(6):
                ws, _welcome, _state = await _join_player(f"MiniLoad{i}{int(time.time())%10000}", "ak47", "soldier")
                clients.append(ws)
            collector = clients[0]

            start = time.monotonic()
            next_ping = start
            while time.monotonic() - start < 5.0:
                now = time.monotonic()
                if now >= next_ping:
                    stamp = int(now * 1000)
                    ping_marks[stamp] = now
                    await collector.send(json.dumps({"type": "ping", "time": stamp}))
                    next_ping += 1.0

                raw = await asyncio.wait_for(collector.recv(), timeout=2.0)
                msg = json.loads(raw)
                if msg.get("type") == "state":
                    state_count += 1
                    tick_ms.append(float(msg.get("tick_ms", 0)))
                    if last_state_time is not None:
                        intervals.append(now - last_state_time)
                    last_state_time = now
                elif msg.get("type") == "pong" and msg.get("time") in ping_marks:
                    sent = ping_marks.pop(msg["time"])
                    rtts.append((time.monotonic() - sent) * 1000)

            assert state_count > 20
            assert intervals
            assert tick_ms

            freq = 1 / statistics.mean(intervals)
            p50 = statistics.median(rtts) if rtts else None
            p95 = statistics.quantiles(rtts, n=100, method='inclusive')[94] if len(rtts) >= 20 else None
            print(
                f"WS sample (6 oyuncu/5s): states={state_count}, freq_hz={freq:.2f}, "
                f"rtt_p50={None if p50 is None else round(p50,2)}, "
                f"rtt_p95={None if p95 is None else round(p95,2)}, "
                f"tick_mean_ms={round(statistics.mean(tick_ms),2)}"
            )
        finally:
            for ws in clients:
                with contextlib.suppress(Exception):
                    await ws.close()

    asyncio.run(_flow())

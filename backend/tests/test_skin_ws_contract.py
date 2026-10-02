"""Skin seçim ve websocket senkronizasyon sözleşmesi testleri."""

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
        raise RuntimeError("REACT_APP_BACKEND_URL is required")
    return base.rstrip("/")


BASE_URL = _base_url()
SKINS = ["soldier", "fbi", "civilian", "terrorist", "gang_male", "gang_female"]


def _ws_url(token: str) -> str:
    parsed = urlparse(BASE_URL)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return f"{scheme}://{parsed.netloc}/api/ws/{token}"


def _join(name: str, weapon: str = "ak47", skin: str | None = None):
    payload = {"name": name, "weapon": weapon}
    if skin is not None:
        payload["skin"] = skin
    return requests.post(f"{BASE_URL}/api/join", json=payload, timeout=15)


async def _recv_type(ws, expected_type: str, timeout=6.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
        msg = json.loads(raw)
        if msg.get("type") == expected_type:
            return msg
    raise AssertionError(f"Timed out waiting for {expected_type}")


async def _recv_state(ws, timeout=6.0):
    return await _recv_type(ws, "state", timeout=timeout)


async def _join_and_connect(name: str, weapon: str = "ak47", skin: str | None = None):
    joined = _join(name=name, weapon=weapon, skin=skin)
    assert joined.status_code == 200
    token = joined.json()["token"]
    ws = await websockets.connect(_ws_url(token), open_timeout=10)
    welcome = await _recv_type(ws, "welcome")
    state = await _recv_state(ws)
    return ws, welcome, state


# Module: /api/join skin doğrulama + varsayılan skin davranışı
def test_join_accepts_all_skins_rejects_invalid_and_defaults_to_soldier():
    for i, skin in enumerate(SKINS):
        response = _join(name=f"Skin{i}{int(time.time()) % 10000}", weapon="ak47", skin=skin)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data.get("token"), str) and len(data["token"]) > 8

    invalid = _join(name=f"BadSkin{int(time.time()) % 10000}", weapon="ak47", skin="invalid_skin")
    assert invalid.status_code == 422

    async def _check_default_skin():
        ws, _welcome, state = await _join_and_connect(name=f"Default{int(time.time()) % 10000}", weapon="ak47", skin=None)
        try:
            assert state["me"]["skin"] == "soldier"
        finally:
            with contextlib.suppress(Exception):
                await ws.close()

    asyncio.run(_check_default_skin())


# Module: gerçek iki websocket istemcide skin senkronizasyonu + shot/kill/respawn sözleşmesi
def test_two_clients_observe_skin_shot_and_respawn_keeps_skin_weapon():
    async def _flow():
        suffix = str(int(time.time()) % 100000)
        ws1, w1, s1 = await _join_and_connect(name=f"FBI{suffix}", weapon="m4", skin="fbi")
        ws2, w2, s2 = await _join_and_connect(name=f"GF{suffix}", weapon="rocket", skin="gang_female")

        try:
            # Her iki istemci de karşı oyuncunun skin bilgisini görmeli.
            seen_remote_skins = False
            for _ in range(30):
                s1 = await _recv_state(ws1)
                s2 = await _recv_state(ws2)
                p2 = next((p for p in s1.get("players", []) if p["id"] == w2["id"]), None)
                p1 = next((p for p in s2.get("players", []) if p["id"] == w1["id"]), None)
                if p1 and p2 and p1.get("skin") == "fbi" and p2.get("skin") == "gang_female":
                    seen_remote_skins = True
                    break
            assert seen_remote_skins

            # Yerel skin doğrulaması.
            assert s1["me"]["skin"] == "fbi"
            assert s2["me"]["skin"] == "gang_female"

            # Oyuncu 1 ateş edince oyuncu 2 bunu event/firing olarak görmeli.
            remote_shot_observed = False
            for i in range(25):
                await ws1.send(
                    json.dumps(
                        {
                            "type": "input",
                            "x": 0,
                            "z": 0,
                            "angle": s1["me"]["angle"] + (i * 0.04),
                            "fire": True,
                        }
                    )
                )
                await asyncio.sleep(0.06)
                s2 = await _recv_state(ws2)
                p1 = next((p for p in s2.get("players", []) if p["id"] == w1["id"]), None)
                shot_event = any(e.get("type") == "shot" and e.get("owner") == w1["id"] for e in s2.get("events", []))
                if shot_event or (p1 and p1.get("firing") is True):
                    remote_shot_observed = True
                    break
            assert remote_shot_observed

            # PvP için iki oyuncunun da korumasını kaldır.
            await ws1.send(json.dumps({"type": "input", "x": 0, "z": 0, "angle": s1["me"]["angle"], "fire": True}))
            await ws2.send(json.dumps({"type": "input", "x": 0, "z": 0, "angle": s2["me"]["angle"] + math.pi, "fire": True}))

            # Oyuncu 1, oyuncu 2'yi hedefleyip öldürsün.
            kill_verified = False
            for _ in range(180):
                s1 = await _recv_state(ws1)
                s2 = await _recv_state(ws2)
                p2 = next((p for p in s1.get("players", []) if p["id"] == w2["id"]), None)
                if p2 and p2["hp"] > 0:
                    angle = math.atan2(p2["x"] - s1["me"]["x"], p2["z"] - s1["me"]["z"])
                    await ws1.send(json.dumps({"type": "input", "x": 0.4, "z": 0.0, "sprint": True, "angle": angle, "fire": True}))
                kill_event = next(
                    (
                        e
                        for e in s1.get("events", [])
                        if e.get("type") == "kill" and e.get("owner") == w1["id"] and e.get("target") == f"GF{suffix}"
                    ),
                    None,
                )
                if kill_event:
                    assert kill_event.get("skin") == "gang_female"
                    assert kill_event.get("weapon") == "rocket"
                    kill_verified = True
                    break
                await asyncio.sleep(0.05)
            assert kill_verified

            # Respawn sonrası me.skin ve me.weapon korunmalı.
            dead_seen = False
            for _ in range(60):
                s2 = await _recv_state(ws2)
                if s2["me"]["hp"] <= 0:
                    dead_seen = True
                    break
            assert dead_seen

            await ws2.send(json.dumps({"type": "respawn"}))
            respawn_ok = False
            for _ in range(100):
                s2 = await _recv_state(ws2)
                if s2["me"]["hp"] > 0:
                    if s2["me"]["skin"] == "gang_female" and s2["me"]["weapon"] == "rocket":
                        respawn_ok = True
                        break
                await asyncio.sleep(0.05)
            assert respawn_ok
        finally:
            with contextlib.suppress(Exception):
                await ws1.close()
            with contextlib.suppress(Exception):
                await ws2.close()

    asyncio.run(_flow())

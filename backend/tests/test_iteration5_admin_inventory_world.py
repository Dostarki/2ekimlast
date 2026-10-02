"""Iteration-5 focused tests: admin auth/origin/rate-limit + inventory/world/bot integrations."""

import asyncio
import contextlib
import hashlib
import json
import os
import time
from pathlib import Path
from urllib.parse import urlparse

import pytest
import requests
import websockets
from pymongo import MongoClient
from pymongo.errors import InvalidURI
from dotenv import dotenv_values


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


def _admin_password() -> str:
    return "123123"


def _backend_env() -> dict:
    return dotenv_values('/app/backend/.env')


BASE_URL = _base_url()
ORIGIN = BASE_URL


def _ws_url(token: str) -> str:
    parsed = urlparse(BASE_URL)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return f"{scheme}://{parsed.netloc}/api/ws/{token}"


def _admin_url(path: str) -> str:
    return f"{BASE_URL}/api/admin{path}"


def _admin_login(session: requests.Session, password: str = "123123", origin: str = ORIGIN):
    return session.post(
        _admin_url("/login"),
        json={"password": password},
        headers={"Origin": origin},
        timeout=15,
    )


def _recv_state_sync(ws, timeout=8.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        raw = ws.recv(timeout=timeout)
        msg = json.loads(raw)
        if msg.get("type") == "state":
            return msg
    raise AssertionError("Timed out waiting for state")


async def _join_ws(name: str, weapon: str = "ak47", skin: str = "soldier"):
    r = requests.post(f"{BASE_URL}/api/join", json={"name": name, "weapon": weapon, "skin": skin}, timeout=15)
    assert r.status_code == 200
    token = r.json()["token"]
    ws = await websockets.connect(_ws_url(token), open_timeout=12)
    welcome = json.loads(await asyncio.wait_for(ws.recv(), timeout=8))
    assert welcome.get("type") == "welcome"
    return ws, welcome


def _clear_rate_limit_attempts():
    env = _backend_env()
    mongo_url = env.get("MONGO_URL")
    db_name = env.get("DB_NAME")
    if not mongo_url or not db_name:
        return False
    client = MongoClient(mongo_url, serverSelectionTimeoutMS=4000)
    try:
        db = client[db_name]
        db.login_attempts.delete_one({'identifier': 'admin:operator'})
        return True
    finally:
        client.close()


def _admin_identity_hash_looks_bcrypt():
    env = _backend_env()
    hashed = env.get("ADMIN_PASSWORD_HASH", "")
    return hashed.startswith("$2b$")


def test_admin_unauthorized_and_hash_format_and_indexes():
    """Module: admin unauth contract + bcrypt/hash/index storage checks."""
    s = requests.Session()
    me = s.get(_admin_url("/me"), timeout=15)
    settings = s.get(_admin_url("/settings"), timeout=15)
    status = s.get(_admin_url("/status"), timeout=15)
    assert me.status_code == 401
    assert settings.status_code == 401
    assert status.status_code == 401

    env = _backend_env()
    mongo_url = env.get("MONGO_URL")
    db_name = env.get("DB_NAME")
    if not mongo_url or not db_name:
        pytest.skip("MONGO_URL/DB_NAME unavailable for index assertions")
    try:
        client = MongoClient(mongo_url, serverSelectionTimeoutMS=5000)
    except InvalidURI:
        pytest.skip("MONGO_URL format is not directly consumable in this runner")
    try:
        db = client[db_name]
        account = db.admin_accounts.find_one({"id": "operator"}, {"_id": 0, "password_hash": 1})
        assert account and isinstance(account.get("password_hash"), str)
        assert account["password_hash"].startswith("$2b$")
        idx_sessions = db.admin_sessions.index_information()
        idx_attempts = db.login_attempts.index_information()
        assert any("sid" in i.get("key", [])[0][0] if i.get("key") else False for i in idx_sessions.values())
        assert any("expires_at" in i.get("key", [])[0][0] if i.get("key") else False for i in idx_sessions.values())
        assert any("identifier" in i.get("key", [])[0][0] if i.get("key") else False for i in idx_attempts.values())
        assert any("expires_at" in i.get("key", [])[0][0] if i.get("key") else False for i in idx_attempts.values())
    finally:
        client.close()


def test_admin_login_cookie_flags_invalid_and_origin_guard_and_refresh_logout_revocation():
    """Module: admin auth flow, secure cookies, origin/CSRF guard, refresh + logout revocation."""
    s = requests.Session()

    invalid = _admin_login(s, password="wrong-pass")
    assert invalid.status_code == 401

    no_origin = s.post(_admin_url("/login"), json={"password": _admin_password()}, timeout=15)
    assert no_origin.status_code == 403

    bad_origin = _admin_login(s, password=_admin_password(), origin="https://invalid.invalid")
    assert bad_origin.status_code == 403

    ok = _admin_login(s)
    assert ok.status_code == 200
    payload = ok.json()
    assert payload["role"] == "admin"

    set_cookie = "\n".join(ok.headers.get("Set-Cookie", "").split(", "))
    assert "admin_access=" in set_cookie
    assert "admin_refresh=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Secure" in set_cookie
    # Check application cookies, not unrelated edge cookies. CSRF stays Origin-enforced.
    cookies = [h for h in ok.raw.headers.getlist('Set-Cookie') if h.startswith(('admin_access=', 'admin_refresh='))]
    assert len(cookies) == 2
    for cookie in cookies:
        assert 'HttpOnly' in cookie and 'Secure' in cookie and 'Path=/api/admin' in cookie
        assert 'samesite=strict' in cookie.lower() or ('samesite=none' in cookie.lower() and 'Partitioned' in cookie)
    assert "Path=/api/admin" in set_cookie

    me = s.get(_admin_url("/me"), timeout=15)
    assert me.status_code == 200

    refreshed = s.post(_admin_url("/refresh"), headers={"Origin": ORIGIN}, timeout=15)
    assert refreshed.status_code == 200

    logout = s.post(_admin_url("/logout"), headers={"Origin": ORIGIN}, timeout=15)
    assert logout.status_code == 200

    revoked = s.get(_admin_url("/me"), timeout=15)
    assert revoked.status_code == 401


def test_admin_settings_validation_and_origin_csrf_rules_and_restore():
    """Module: settings CRUD/validation/origin checks + restore to baseline."""
    s = requests.Session()
    login = _admin_login(s)
    assert login.status_code == 200

    current = s.get(_admin_url("/settings"), timeout=15)
    assert current.status_code == 200
    original = current.json()

    missing_origin = s.put(_admin_url("/settings"), json=original, timeout=15)
    assert missing_origin.status_code == 403

    wrong_origin = s.put(
        _admin_url("/settings"),
        json=original,
        headers={"Origin": "https://invalid.invalid"},
        timeout=15,
    )
    assert wrong_origin.status_code == 403

    invalid_density = dict(original)
    invalid_density["zombie_density"] = "veryhigh"
    density_res = s.put(_admin_url("/settings"), json=invalid_density, headers={"Origin": ORIGIN}, timeout=15)
    assert density_res.status_code == 422

    bad_extra = dict(original)
    bad_extra["extra_field"] = 1
    extra_res = s.put(_admin_url("/settings"), json=bad_extra, headers={"Origin": ORIGIN}, timeout=15)
    assert extra_res.status_code == 422

    bad_neg = dict(original)
    bad_neg["bot_count"] = -1
    neg_res = s.put(_admin_url("/settings"), json=bad_neg, headers={"Origin": ORIGIN}, timeout=15)
    assert neg_res.status_code == 422

    bad_too_high = dict(original)
    bad_too_high["bot_count"] = 201
    high_res = s.put(_admin_url("/settings"), json=bad_too_high, headers={"Origin": ORIGIN}, timeout=15)
    assert high_res.status_code == 422

    mutate = dict(original)
    mutate["time_of_day"] = "night" if original["time_of_day"] == "day" else "day"
    saved = s.put(_admin_url("/settings"), json=mutate, headers={"Origin": ORIGIN}, timeout=15)
    assert saved.status_code == 200
    assert saved.json()["time_of_day"] == mutate["time_of_day"]

    persisted = s.get(_admin_url("/settings"), timeout=15)
    assert persisted.status_code == 200
    assert persisted.json()["time_of_day"] == mutate["time_of_day"]

    restore = s.put(_admin_url("/settings"), json=original, headers={"Origin": ORIGIN}, timeout=15)
    assert restore.status_code == 200
    assert restore.json()["time_of_day"] == original["time_of_day"]


def test_admin_rate_limit_5_fails_then_429_and_cleanup():
    """Module: brute force lockout and cleanup of test-generated lock docs."""
    s = requests.Session()
    statuses = []
    assert _clear_rate_limit_attempts()
    try:
        for _ in range(6):
            r = _admin_login(s, password="bad")
            statuses.append(r.status_code)
        assert _admin_login(s).status_code == 429
    finally:
        assert _clear_rate_limit_attempts()
    assert statuses[:5] == [401, 401, 401, 401, 401]
    assert statuses[5] == 429
    assert _clear_rate_limit_attempts() in {True, False}


def test_join_defaults_to_glock_and_inventory_has_all_slots():
    """Module: join defaults and inventory contract checks."""

    async def _flow():
        ws, _welcome = await _join_ws(name=f"INV{int(time.time())%100000}", weapon="ak47", skin="soldier")
        try:
            state = json.loads(await asyncio.wait_for(ws.recv(), timeout=8))
            while state.get("type") != "state":
                state = json.loads(await asyncio.wait_for(ws.recv(), timeout=8))
            me = state["me"]
            assert me["weapon"] == "glock18"
            inventory = me.get("inventory", {})
            weapons = requests.get(f"{BASE_URL}/api/weapons", timeout=12).json()
            assert len(inventory.keys()) == len(weapons.keys())
            assert set(inventory.keys()) == set(weapons.keys())
            assert inventory["glock18"]["ammo"] == 17
            assert inventory["glock18"]["reserve"] == 102
        finally:
            with contextlib.suppress(Exception):
                await ws.close()

    asyncio.run(_flow())


def test_equip_flow_switching_preserves_per_slot_ammo_and_invalid_payload_denied():
    """Module: equip switching, cooldown behavior, and invalid equip safety."""

    async def _next_state(ws, timeout=10):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
            if msg.get("type") == "state":
                return msg
        raise AssertionError("state timeout")

    async def _flow():
        ws, _ = await _join_ws(name=f"EQ{int(time.time())%100000}", weapon="ak47")
        try:
            s = await _next_state(ws)
            initial_glock_ammo = s["me"]["ammo"]

            await ws.send(json.dumps({"type": "equip", "weapon": "m4"}))
            changed = False
            for _ in range(20):
                s = await _next_state(ws)
                if s["me"]["weapon"] == "m4":
                    changed = True
                    break
            assert changed is True
            await asyncio.sleep(0.4)

            m4_before = s["me"]["ammo"]
            for i in range(24):
                await ws.send(
                    json.dumps(
                        {
                            "type": "input",
                            "x": 0.15,
                            "z": 0,
                            "sprint": False,
                            "fire": True,
                            "fire_pressed": True,
                            "angle": s["me"]["angle"] + i * 0.03,
                        }
                    )
                )
                await asyncio.sleep(0.07)
                s = await _next_state(ws)
                if s["me"]["ammo"] < m4_before:
                    break
            assert s["me"]["ammo"] < m4_before
            await ws.send(json.dumps({'type': 'input', 'seq': 900, 'x': 0, 'z': 0, 'fire': False, 'fire_pressed': False, 'angle': s['me']['angle']}))
            for _ in range(80):
                s = await _next_state(ws)
                if s['me']['input_seq'] >= 900:
                    break
            assert s['me']['input_seq'] >= 900
            m4_after_fire = s["me"]["ammo"]

            await ws.send(json.dumps({"type": "equip", "weapon": "glock18"}))
            for _ in range(20):
                s = await _next_state(ws)
                if s["me"]["weapon"] == "glock18":
                    break
            assert s["me"]["weapon"] == "glock18"
            assert s["me"]["ammo"] == initial_glock_ammo

            back_to_m4 = False
            for _ in range(8):
                await ws.send(json.dumps({"type": "equip", "weapon": "m4"}))
                for _ in range(10):
                    s = await _next_state(ws)
                    if s["me"]["weapon"] == "m4":
                        back_to_m4 = True
                        break
                if back_to_m4:
                    break
                await asyncio.sleep(0.12)
            assert back_to_m4 is True
            assert s["me"]["ammo"] == m4_after_fire

            await ws.send(json.dumps({"type": "equip", "weapon": ["ak47"]}))
            invalid_denied = False
            for _ in range(16):
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=8))
                if msg.get("type") == "action_error":
                    invalid_denied = True
                if msg.get("type") == "state" and invalid_denied:
                    assert msg["me"]["weapon"] == "m4"
                    break
            assert invalid_denied is True
        finally:
            with contextlib.suppress(Exception):
                await ws.close()

    asyncio.run(_flow())


def test_time_of_day_and_bot_counts_visible_in_admin_status_and_ws():
    """Module: world settings propagation + bot count/admin status integrity + restore."""
    s = requests.Session()
    login = _admin_login(s)
    assert login.status_code == 200
    original = s.get(_admin_url("/settings"), timeout=15).json()

    async def _flow():
        ws1, _ = await _join_ws(name=f"W1{int(time.time())%100000}")
        ws2, _ = await _join_ws(name=f"W2{int(time.time())%100000}")
        try:
            target_time = "night" if original["time_of_day"] == "day" else "day"
            update = dict(original)
            update["time_of_day"] = target_time
            update["bot_count"] = min(3, 200)

            put = s.put(_admin_url("/settings"), json=update, headers={"Origin": ORIGIN}, timeout=15)
            assert put.status_code == 200

            got_time1 = False
            got_time2 = False
            for _ in range(30):
                m1 = json.loads(await asyncio.wait_for(ws1.recv(), timeout=8))
                if m1.get("type") == "state" and m1.get("time_of_day") == target_time:
                    got_time1 = True
                    break
            for _ in range(30):
                m2 = json.loads(await asyncio.wait_for(ws2.recv(), timeout=8))
                if m2.get("type") == "state" and m2.get("time_of_day") == target_time:
                    got_time2 = True
                    break
            assert got_time1 and got_time2

            bots_seen = 0
            for _ in range(20):
                st = s.get(_admin_url("/status"), timeout=15)
                assert st.status_code == 200
                data = st.json()
                assert data["total"] == data["humans"] + data["bots"]
                assert data["total"] <= 200
                bots_seen = data["bots"]
                if bots_seen >= 2:
                    break
                await asyncio.sleep(0.35)
            assert bots_seen >= 1
            participants = st.json().get("participants", [])
            bot_names = [p["name"] for p in participants if p.get("bot")]
            if bot_names:
                assert len(bot_names) == len(set(n.casefold() for n in bot_names))

            reset = dict(original)
            reset["bot_count"] = 0
            restore = s.put(_admin_url("/settings"), json=reset, headers={"Origin": ORIGIN}, timeout=15)
            assert restore.status_code == 200
        finally:
            with contextlib.suppress(Exception):
                await ws1.close()
            with contextlib.suppress(Exception):
                await ws2.close()

    asyncio.run(_flow())

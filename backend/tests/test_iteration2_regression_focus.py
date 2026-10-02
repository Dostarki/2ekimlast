"""Iteration 2 focused regression: admin origin/auth, settings restore, local report idempotency, early isolation.

Uses public REACT_APP_BACKEND_URL endpoints only.
"""

import asyncio
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import pytest
import requests
import websockets
from dotenv import dotenv_values
from pymongo import MongoClient


FRONTEND_ENV = dotenv_values('/app/frontend/.env')
BACKEND_ENV = dotenv_values('/app/backend/.env')
BASE_URL = (FRONTEND_ENV.get('REACT_APP_BACKEND_URL') or '').strip().rstrip('/')
MONGO_URL = (BACKEND_ENV.get('MONGO_URL') or '').strip().strip('"')
DB_NAME = (BACKEND_ENV.get('DB_NAME') or '').strip().strip('"')
ADMIN_PASSWORD = '123123'


if not BASE_URL:
    raise RuntimeError('REACT_APP_BACKEND_URL is required')


def _api(path: str) -> str:
    return f"{BASE_URL}/api{path}"


def _admin(path: str) -> str:
    return f"{BASE_URL}/api/admin{path}"


def _ws(token: str) -> str:
    parsed = urlparse(BASE_URL)
    scheme = 'wss' if parsed.scheme == 'https' else 'ws'
    return f"{scheme}://{parsed.netloc}/api/ws/{token}"


def _origin() -> str:
    return (BACKEND_ENV.get('ADMIN_ORIGIN') or BASE_URL).strip().rstrip('/')


def _mongo_db():
    if not MONGO_URL or not DB_NAME:
        pytest.skip('MONGO_URL / DB_NAME required')
    client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=8000)
    return client, client[DB_NAME]


# Module: test-only paid account fixture for join/ws/report checks
@pytest.fixture(scope='module')
def paid_fixture_account():
    client, db = _mongo_db()
    prefix = f"TEST_T1_{secrets.token_hex(4)}"
    now = datetime.now(timezone.utc)
    expires = (now + timedelta(days=2)).isoformat()
    account_id = f"0x{secrets.token_hex(20)}"
    token = f"{prefix}_TOKEN_{secrets.token_urlsafe(18)}"

    db.player_accounts.insert_one({
        'account_id': account_id,
        'address': account_id,
        'nickname': f'{prefix}_P1',
        'normalized_nickname': f'{prefix.lower()}_p1',
        'skin': 'soldier',
        'schema_version': 1,
        'created_at': now.isoformat(),
        'last_login_at': now.isoformat(),
    })
    db.auth_sessions.insert_one({
        'session_token': token,
        'account_id': account_id,
        'address': account_id,
        'chain_id': 4663,
        'created_at': now.isoformat(),
        'expires_at': expires,
    })
    db.access_entitlements.insert_one({
        'account_id': account_id,
        'paid': True,
        'chain_id': 4663,
        'source_order_id': f'{prefix}_ORDER_P1',
        'tx_hash': '0x' + 'a' * 64,
        'quote': {'test_fixture': True},
        'confirmed_at': now.isoformat(),
    })

    yield {'prefix': prefix, 'account_id': account_id, 'token': token}

    db.local_runs.delete_many({'account_id': account_id})
    db.scores.delete_many({'name': {'$regex': f'^{prefix}'}})
    db.auth_sessions.delete_many({'session_token': token})
    db.access_entitlements.delete_many({'account_id': account_id})
    db.player_accounts.delete_many({'account_id': account_id})
    db.player_progress.delete_many({'account_id': account_id})
    client.close()


def _admin_login(session: requests.Session, origin: str):
    return session.post(_admin('/login'), json={'password': ADMIN_PASSWORD}, headers={'Origin': origin}, timeout=20)


# Module: auth config quality gate
def test_admin_password_hash_uses_bcrypt_2b_prefix():
    hashed = (BACKEND_ENV.get('ADMIN_PASSWORD_HASH') or '').strip("'\"")
    assert hashed.startswith('$2b$')


# Module: admin login/session/cookie + required origin behavior
def test_admin_login_cookie_flags_and_origin_enforcement():
    origin = _origin()

    missing = requests.post(_admin('/login'), json={'password': ADMIN_PASSWORD}, timeout=20)
    assert missing.status_code == 403

    foreign = requests.post(
        _admin('/login'),
        json={'password': ADMIN_PASSWORD},
        headers={'Origin': 'https://evil.example.com'},
        timeout=20,
    )
    assert foreign.status_code == 403

    s = requests.Session()
    try:
        ok = _admin_login(s, origin)
        assert ok.status_code == 200
        set_cookie = ', '.join(ok.headers.get_all('set-cookie')) if hasattr(ok.headers, 'get_all') else ok.headers.get('set-cookie', '')
        assert 'HttpOnly' in set_cookie
        assert 'Secure' in set_cookie
        assert 'admin_access=' in set_cookie and 'admin_refresh=' in set_cookie
        assert s.get(_admin('/me'), timeout=20).status_code == 200
    finally:
        try:
            s.post(_admin('/logout'), headers={'Origin': origin}, timeout=20)
        except Exception:
            pass


# Module: admin world settings mutation + restore (zombie 100, bots 3, max bot guard)
def test_admin_settings_update_100z_3b_then_restore_and_bot_cap_guard():
    origin = _origin()
    s = requests.Session()
    original = None
    try:
        login = _admin_login(s, origin)
        assert login.status_code == 200

        get1 = s.get(_admin('/settings'), timeout=20)
        assert get1.status_code == 200
        original = get1.json()

        changed = dict(original)
        changed['zombie_count'] = 100
        changed['bot_count'] = 3
        put = s.put(_admin('/settings'), json=changed, headers={'Origin': origin}, timeout=20)
        assert put.status_code == 200
        assert put.json()['zombie_count'] == 100
        assert put.json()['bot_count'] == 3

        verify = s.get(_admin('/settings'), timeout=20)
        assert verify.status_code == 200
        assert verify.json()['zombie_count'] == 100
        assert verify.json()['bot_count'] == 3

        bad = dict(changed)
        bad['bot_count'] = 201
        bad_put = s.put(_admin('/settings'), json=bad, headers={'Origin': origin}, timeout=20)
        assert bad_put.status_code in (400, 422)
    finally:
        if original is not None:
            try:
                s.put(_admin('/settings'), json=original, headers={'Origin': origin}, timeout=20)
            except Exception:
                pass
        try:
            s.post(_admin('/logout'), headers={'Origin': origin}, timeout=20)
        except Exception:
            pass


# Module: early route/UI reachability + expected config 503 when DB2 blocked
def test_early_routes_and_expected_early_config_503():
    home = requests.get(f'{BASE_URL}/early', timeout=20)
    assert home.status_code == 200

    console = requests.get(f'{BASE_URL}/early/console', timeout=20)
    assert console.status_code == 200

    agent = requests.get(f'{BASE_URL}/early/agent/TESTCODE', timeout=20)
    assert agent.status_code == 200

    admin = requests.get(f'{BASE_URL}/early/admin', timeout=20)
    assert admin.status_code == 200

    config = requests.get(_api('/early/config'), timeout=20)
    assert config.status_code == 503


# Module: local report idempotency across disconnect/reconnect and progress carry-over
def test_disconnect_and_recover_report_once_then_rejoin_progress(paid_fixture_account):
    client, db = _mongo_db()
    token = paid_fixture_account['token']
    prefix = paid_fixture_account['prefix']
    account_id = paid_fixture_account['account_id']

    join = requests.post(
        _api('/join'),
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
        json={'name': f'{prefix}_P1', 'weapon': 'glock18', 'skin': 'soldier'},
        timeout=20,
    )
    assert join.status_code == 200
    payload = join.json()
    run_id = payload['run_id']
    ws_token = payload['token']

    baseline = db.player_progress.find_one({'account_id': account_id}, {'_id': 0})
    base_gold = int((baseline or {}).get('gold', 150))

    report1 = {
        'type': 'report',
        'sequence': 1,
        'revision': 1,
        'score': 100,
        'kills': 1,
        'pvp': 0,
        'hp': 90,
        'weapon': 'glock18',
        'progress': {'gold': base_gold + 10},
    }

    async def _send_ws_report_and_close():
        async with websockets.connect(_ws(ws_token), open_timeout=12) as ws:
            await ws.send('{"type":"ping","time":1}')
            await ws.send(__import__('json').dumps(report1))
            deadline = asyncio.get_event_loop().time() + 8
            saved = None
            while asyncio.get_event_loop().time() < deadline:
                msg = __import__('json').loads(await asyncio.wait_for(ws.recv(), timeout=8))
                if msg.get('type') == 'saved' and msg.get('sequence') == 1:
                    saved = msg
                    break
            assert saved is not None

    asyncio.run(_send_ws_report_and_close())
    time.sleep(0.7)

    after_ws = db.player_progress.find_one({'account_id': account_id}, {'_id': 0}) or {}
    gold_after_ws = int(after_ws.get('gold', base_gold))
    assert gold_after_ws >= base_gold + 10

    dup = requests.post(_api('/local/report'), json={'token': ws_token, 'report': report1}, timeout=20)
    assert dup.status_code == 200

    after_dup = db.player_progress.find_one({'account_id': account_id}, {'_id': 0}) or {}
    gold_after_dup = int(after_dup.get('gold', base_gold))
    assert gold_after_dup == gold_after_ws

    report2 = dict(report1)
    report2['sequence'] = 2
    report2['progress'] = {'gold': base_gold + 20}
    seq2 = requests.post(_api('/local/report'), json={'token': ws_token, 'report': report2}, timeout=20)
    assert seq2.status_code == 200

    after_seq2 = db.player_progress.find_one({'account_id': account_id}, {'_id': 0}) or {}
    gold_after_seq2 = int(after_seq2.get('gold', base_gold))
    assert gold_after_seq2 >= base_gold + 20

    rejoin = requests.post(
        _api('/join'),
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
        json={'name': f'{prefix}_P1', 'weapon': 'glock18', 'skin': 'soldier'},
        timeout=20,
    )
    assert rejoin.status_code == 200
    assert int(rejoin.json()['progress']['gold']) >= base_gold + 20

    # Keep DB clean from this test run's score row.
    db.scores.delete_one({'id': run_id})
    client.close()

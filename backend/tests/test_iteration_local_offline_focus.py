"""Iteration focus: local-simulation session/report APIs + early isolation behavior."""

import asyncio
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import pytest
import requests
import websockets
from dotenv import load_dotenv
from pymongo import MongoClient


load_dotenv(Path('/app/frontend/.env'))
load_dotenv(Path('/app/backend/.env'))

BASE_URL = (os.environ.get('REACT_APP_BACKEND_URL') or '').rstrip('/')
MONGO_URL = (os.environ.get('MONGO_URL') or '').strip().strip('"')
DB_NAME = (os.environ.get('DB_NAME') or '').strip().strip('"')


if not BASE_URL:
    raise RuntimeError('REACT_APP_BACKEND_URL is required')


def _api(path: str) -> str:
    return f"{BASE_URL}/api{path}"


def _ws(token: str) -> str:
    parsed = urlparse(BASE_URL)
    scheme = 'wss' if parsed.scheme == 'https' else 'ws'
    return f"{scheme}://{parsed.netloc}/api/ws/{token}"


def _mongo_db():
    if not MONGO_URL or not DB_NAME:
        pytest.skip('MONGO_URL / DB_NAME required for local fixture setup')
    client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=8000)
    return client, client[DB_NAME]


def _session_headers(token: str):
    return {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}


# Module: test-only wallet identities and paid/unpaid access fixtures for public endpoint testing
@pytest.fixture(scope='module')
def auth_fixtures():
    client, db = _mongo_db()
    prefix = f"TEST_T1_{secrets.token_hex(4)}"
    now = datetime.now(timezone.utc)
    expires = (now + timedelta(days=2)).isoformat()

    paid_1 = f"0x{secrets.token_hex(20)}"
    paid_2 = f"0x{secrets.token_hex(20)}"
    unpaid = f"0x{secrets.token_hex(20)}"

    paid_token_1 = f"{prefix}_PAID1_{secrets.token_urlsafe(18)}"
    paid_token_2 = f"{prefix}_PAID2_{secrets.token_urlsafe(18)}"
    unpaid_token = f"{prefix}_UNPAID_{secrets.token_urlsafe(18)}"

    accounts = [
        {'account_id': paid_1, 'address': paid_1, 'nickname': f'{prefix}_P1', 'normalized_nickname': f'{prefix.lower()}_p1', 'skin': 'soldier', 'schema_version': 1, 'created_at': now.isoformat(), 'last_login_at': now.isoformat()},
        {'account_id': paid_2, 'address': paid_2, 'nickname': f'{prefix}_P2', 'normalized_nickname': f'{prefix.lower()}_p2', 'skin': 'soldier', 'schema_version': 1, 'created_at': now.isoformat(), 'last_login_at': now.isoformat()},
        {'account_id': unpaid, 'address': unpaid, 'nickname': f'{prefix}_U1', 'normalized_nickname': f'{prefix.lower()}_u1', 'skin': 'soldier', 'schema_version': 1, 'created_at': now.isoformat(), 'last_login_at': now.isoformat()},
    ]

    sessions = [
        {'session_token': paid_token_1, 'account_id': paid_1, 'address': paid_1, 'chain_id': 4663, 'created_at': now.isoformat(), 'expires_at': expires},
        {'session_token': paid_token_2, 'account_id': paid_2, 'address': paid_2, 'chain_id': 4663, 'created_at': now.isoformat(), 'expires_at': expires},
        {'session_token': unpaid_token, 'account_id': unpaid, 'address': unpaid, 'chain_id': 4663, 'created_at': now.isoformat(), 'expires_at': expires},
    ]

    entitlements = [
        {'account_id': paid_1, 'paid': True, 'chain_id': 4663, 'source_order_id': f'{prefix}_ORDER_P1', 'tx_hash': '0x' + '1' * 64, 'quote': {'test_fixture': True}, 'confirmed_at': now.isoformat()},
        {'account_id': paid_2, 'paid': True, 'chain_id': 4663, 'source_order_id': f'{prefix}_ORDER_P2', 'tx_hash': '0x' + '2' * 64, 'quote': {'test_fixture': True}, 'confirmed_at': now.isoformat()},
    ]

    db.player_accounts.insert_many(accounts)
    db.auth_sessions.insert_many(sessions)
    db.access_entitlements.insert_many(entitlements)

    yield {
        'prefix': prefix,
        'paid_token_1': paid_token_1,
        'paid_token_2': paid_token_2,
        'unpaid_token': unpaid_token,
        'paid_1': paid_1,
        'paid_2': paid_2,
        'unpaid': unpaid,
    }

    db.local_runs.delete_many({'account_id': {'$in': [paid_1, paid_2, unpaid]}})
    db.scores.delete_many({'name': {'$regex': f'^{prefix}'}})
    db.auth_sessions.delete_many({'session_token': {'$in': [paid_token_1, paid_token_2, unpaid_token]}})
    db.access_entitlements.delete_many({'account_id': {'$in': [paid_1, paid_2]}})
    db.player_accounts.delete_many({'account_id': {'$in': [paid_1, paid_2, unpaid]}})
    db.player_progress.delete_many({'account_id': {'$in': [paid_1, paid_2, unpaid]}})
    client.close()


# Module: status and join gate behavior (401/402/200)
def test_api_status_reports_local_simulation():
    res = requests.get(_api('/status'), timeout=20)
    assert res.status_code == 200
    data = res.json()
    assert data['simulation'] == 'local'
    assert data['capacity'] == 200
    assert isinstance(data['online'], int)


def test_join_without_auth_returns_401():
    res = requests.post(_api('/join'), json={'name': 'TEST_NOAUTH', 'weapon': 'glock18', 'skin': 'soldier'}, timeout=20)
    assert res.status_code == 401
    assert 'WALLET_SIGNATURE_REQUIRED' in res.text


def test_join_unpaid_returns_402(auth_fixtures):
    res = requests.post(
        _api('/join'),
        headers=_session_headers(auth_fixtures['unpaid_token']),
        json={'name': f"{auth_fixtures['prefix']}_UNPAID", 'weapon': 'glock18', 'skin': 'soldier'},
        timeout=20,
    )
    assert res.status_code == 402
    assert 'ONE_TIME_ACCESS_PAYMENT_REQUIRED' in res.text


def test_join_paid_returns_local_bootstrap(auth_fixtures):
    res = requests.post(
        _api('/join'),
        headers=_session_headers(auth_fixtures['paid_token_1']),
        json={'name': f"{auth_fixtures['prefix']}_P1", 'weapon': 'glock18', 'skin': 'soldier'},
        timeout=20,
    )
    assert res.status_code == 200
    body = res.json()
    assert isinstance(body.get('token'), str) and len(body['token']) > 20
    assert body.get('simulation') == 'local'
    assert body.get('settings', {}).get('bot_count') is not None
    assert isinstance(body.get('run_id'), str)


# Module: websocket contract (social/settings/save only, no world snapshots)
def test_ws_does_not_send_state_snapshots(auth_fixtures):
    join = requests.post(
        _api('/join'),
        headers=_session_headers(auth_fixtures['paid_token_1']),
        json={'name': f"{auth_fixtures['prefix']}_P1", 'weapon': 'glock18', 'skin': 'soldier'},
        timeout=20,
    )
    assert join.status_code == 200
    token = join.json()['token']

    async def _run():
        received = set()
        async with websockets.connect(_ws(token), open_timeout=12) as ws:
            await ws.send('{"type":"ping","time":1}')
            await ws.send('{"type":"report","sequence":1,"revision":1,"score":0,"kills":0,"pvp":0,"hp":100,"weapon":"glock18","progress":{}}')
            deadline = asyncio.get_event_loop().time() + 6
            while asyncio.get_event_loop().time() < deadline:
                raw = await asyncio.wait_for(ws.recv(), timeout=6)
                msg = __import__('json').loads(raw)
                received.add(msg.get('type'))
                if {'social', 'pong', 'saved'}.issubset(received):
                    break
            await ws.send('{"type":"leave"}')
        return received

    received_types = asyncio.run(_run())

    assert 'state' not in received_types
    assert 'social' in received_types
    assert 'pong' in received_types


# Module: score/report validation and leaderboard persistence
def test_recover_rejects_foreign_progress_fields(auth_fixtures):
    join = requests.post(
        _api('/join'),
        headers=_session_headers(auth_fixtures['paid_token_1']),
        json={'name': f"{auth_fixtures['prefix']}_P1", 'weapon': 'glock18', 'skin': 'soldier'},
        timeout=20,
    )
    assert join.status_code == 200
    payload = join.json()

    bad_report = {
        'token': payload['token'],
        'report': {
            'type': 'report', 'sequence': 1, 'revision': 1,
            'score': 10, 'kills': 1, 'pvp': 0, 'hp': 100, 'weapon': 'glock18',
            'progress': {'hacker_field': 999}
        }
    }
    res = requests.post(_api('/local/report'), json=bad_report, timeout=20)
    assert res.status_code == 422


def test_recover_valid_report_persists_to_leaderboard(auth_fixtures):
    join = requests.post(
        _api('/join'),
        headers=_session_headers(auth_fixtures['paid_token_2']),
        json={'name': f"{auth_fixtures['prefix']}_P2", 'weapon': 'glock18', 'skin': 'soldier'},
        timeout=20,
    )
    assert join.status_code == 200
    payload = join.json()

    good_report = {
        'token': payload['token'],
        'report': {
            'type': 'report', 'sequence': 1, 'revision': 1,
            'score': 150, 'kills': 1, 'pvp': 0, 'hp': 90, 'weapon': 'glock18',
            'progress': {}
        }
    }
    save = requests.post(_api('/local/report'), json=good_report, timeout=20)
    assert save.status_code == 200
    assert save.json().get('saved') is True

    leaders = requests.get(_api('/leaderboard'), timeout=20)
    assert leaders.status_code == 200
    rows = leaders.json()
    assert any(r.get('id') == payload['run_id'] and int(r.get('score', 0)) >= 150 for r in rows)


# Module: independent player sessions and online human count transitions (bots excluded)
def test_online_count_transitions_0_1_2_1(auth_fixtures):
    def online_count():
        return requests.get(_api('/status'), timeout=20).json()['online']

    baseline = online_count()

    join1 = requests.post(_api('/join'), headers=_session_headers(auth_fixtures['paid_token_1']), json={'name': f"{auth_fixtures['prefix']}_P1", 'weapon': 'glock18', 'skin': 'soldier'}, timeout=20)
    join2 = requests.post(_api('/join'), headers=_session_headers(auth_fixtures['paid_token_2']), json={'name': f"{auth_fixtures['prefix']}_P2", 'weapon': 'glock18', 'skin': 'soldier'}, timeout=20)
    assert join1.status_code == 200 and join2.status_code == 200

    async def _run_flow():
        ws1 = await websockets.connect(_ws(join1.json()['token']), open_timeout=12)
        try:
            for _ in range(10):
                if online_count() >= baseline + 1:
                    break
                await asyncio.sleep(0.4)
            assert online_count() >= baseline + 1

            ws2 = await websockets.connect(_ws(join2.json()['token']), open_timeout=12)
            try:
                for _ in range(10):
                    if online_count() >= baseline + 2:
                        break
                    await asyncio.sleep(0.4)
                assert online_count() >= baseline + 2
            finally:
                await ws2.close()

            for _ in range(20):
                if online_count() <= baseline + 1:
                    break
                await asyncio.sleep(0.7)
            assert online_count() <= baseline + 1
        finally:
            await ws1.close()

    asyncio.run(_run_flow())


# Module: local worker/runtime static availability and early-service graceful failure
def test_local_worker_and_runtime_assets_served():
    worker = requests.get(f"{BASE_URL}/local-game.worker.js", timeout=20)
    assert worker.status_code == 200
    assert 'loadPyodide' in worker.text
    assert '/local-runtime/' in worker.text

    manifest = requests.get(f"{BASE_URL}/local-runtime/manifest.json", timeout=20)
    assert manifest.status_code == 200
    m = manifest.json()
    assert isinstance(m.get('version'), str) and len(m['version']) > 4

    pyodide_js = requests.get(f"{BASE_URL}/local-runtime/pyodide.js", timeout=20)
    assert pyodide_js.status_code == 200


def test_early_config_returns_503_when_secondary_db_unreachable():
    res = requests.get(_api('/early/config'), timeout=20)
    assert res.status_code == 503
    assert 'retry' in res.text.lower() or 'unavailable' in res.text.lower()

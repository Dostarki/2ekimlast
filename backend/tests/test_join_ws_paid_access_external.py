"""External /api/join + websocket integration with disposable SIWE wallet and test-only entitlement."""

import asyncio
import json
import os
import time
from pathlib import Path
from urllib.parse import urlparse

import pytest
import requests
import websockets
from dotenv import load_dotenv
from eth_account import Account
from eth_account.messages import encode_defunct
from motor.motor_asyncio import AsyncIOMotorClient

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from player_accounts import sync_db_to_file


load_dotenv(Path(__file__).resolve().parents[2] / 'frontend' / '.env')
load_dotenv(Path(__file__).resolve().parents[1] / '.env')


# Modules/features covered: real SIWE auth, paid access gate, /api/join -> first websocket state, rejoin persistence.
BASE_URL = (os.environ.get('REACT_APP_BACKEND_URL') or '').rstrip('/')
MONGO_URL = (os.environ.get('MONGO_URL') or '').strip().strip('"')
DB_NAME = (os.environ.get('DB_NAME') or '').strip().strip('"')
if not BASE_URL:
    raise RuntimeError('REACT_APP_BACKEND_URL is required')


def _origin_parts():
    parsed = urlparse(BASE_URL)
    return parsed.netloc, f'{parsed.scheme}://{parsed.netloc}'


def _api(path: str) -> str:
    return f'{BASE_URL}/api{path}'


def _ws_url(token: str) -> str:
    parsed = urlparse(BASE_URL)
    scheme = 'wss' if parsed.scheme == 'https' else 'ws'
    return f'{scheme}://{parsed.netloc}/api/ws/{token}'


async def _cleanup_wallet_records(addresses: set[str]):
    if not (MONGO_URL and DB_NAME and addresses):
        return
    client = AsyncIOMotorClient(MONGO_URL)
    try:
        db = client[DB_NAME]
        # Wait for disconnect flush tail to settle before deleting live-fixture docs.
        stable = 0
        last_online = None
        for _ in range(16):
            try:
                status = requests.get(_api('/status'), timeout=8)
                online = status.json().get('online') if status.ok else None
            except Exception:
                online = None
            if online is not None and online == last_online:
                stable += 1
            else:
                stable = 0
            last_online = online
            if stable >= 2:
                break
            await asyncio.sleep(0.5)

        addr_list = list(addresses)
        await db.auth_challenges.delete_many({'account_id': {'$in': addr_list}})
        await db.auth_sessions.delete_many({'account_id': {'$in': addr_list}})
        await db.purchase_orders.delete_many({'account_id': {'$in': addr_list}})
        await db.access_entitlements.delete_many({'account_id': {'$in': addr_list}})
        await db.player_progress.delete_many({'account_id': {'$in': addr_list}})
        await db.player_accounts.delete_many({'account_id': {'$in': addr_list}})
        await sync_db_to_file(db)
    finally:
        client.close()


@pytest.fixture(scope='class')
def tracked_addresses():
    addresses: set[str] = set()
    yield addresses
    asyncio.run(_cleanup_wallet_records(addresses))


def _create_wallet_auth_session(tracked_addresses: set[str]):
    account = Account.create()
    tracked_addresses.add(account.address.lower())
    domain, uri = _origin_parts()

    challenge = requests.post(_api('/auth/challenge'), json={
        'address': account.address,
        'chain_id': 4663,
        'domain': domain,
        'uri': uri,
    }, timeout=20)
    assert challenge.status_code == 200
    challenge_data = challenge.json()

    signature = Account.sign_message(
        encode_defunct(text=challenge_data['message']),
        private_key=account.key,
    ).signature.hex()

    session = requests.Session()
    verify = session.post(_api('/auth/verify'), json={
        'message': challenge_data['message'],
        'signature': signature,
    }, timeout=20)
    assert verify.status_code == 200
    token = verify.json().get('token')
    assert isinstance(token, str) and len(token) > 10
    return account.address.lower(), token, session


async def _grant_test_paid_access(account_id: str):
    if not (MONGO_URL and DB_NAME):
        pytest.skip('MONGO_URL/DB_NAME required for test-only entitlement setup')
    client = AsyncIOMotorClient(MONGO_URL)
    try:
        db = client[DB_NAME]
        await db.access_entitlements.update_one(
            {'account_id': account_id},
            {'$set': {
                'account_id': account_id,
                'paid': True,
                'chain_id': 4663,
                'source_order_id': 'TEST_ONLY_ENTITLEMENT',
                'tx_hash': '0x' + '1' * 64,
                'quote': {'test_only': True},
                'confirmed_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            }},
            upsert=True,
        )
        await sync_db_to_file(db)
    finally:
        client.close()


async def _seed_join_progress_with_legacy_parts(account_id: str):
    """Test-only seed: mimic legacy non-empty parts + AK47 unlock for join/rejoin checks."""
    if not (MONGO_URL and DB_NAME):
        pytest.skip('MONGO_URL/DB_NAME required for test-only profile seed')
    client = AsyncIOMotorClient(MONGO_URL)
    try:
        db = client[DB_NAME]
        legacy_parts = [
            {'id': 'barrel_common'},
            {'id': 'receiver_uncommon'},
            {'id': 'optic_rare'},
        ]
        await db.player_progress.update_one(
            {'account_id': account_id},
            {
                '$set': {
                    'unlocked_weapons': ['glock18', 'ak47'],
                    'equipped_weapon': 'glock18',
                    'inventory': {
                        'glock18': {'ammo': 17, 'reserve': 0, 'infinite_reserve': True},
                        'ak47': {'ammo': 30, 'reserve': 90, 'infinite_reserve': False},
                    },
                    'weapon_parts': legacy_parts,
                }
            },
            upsert=True,
        )
        await sync_db_to_file(db)
    finally:
        client.close()


async def _recv_first_state(ws, timeout=12):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
        payload = json.loads(raw)
        if payload.get('type') == 'state':
            return payload
    raise AssertionError('No state payload received before timeout')


class TestJoinWebsocketPaidAccessExternal:
    def test_join_and_rejoin_with_test_entitlement_and_authoritative_movement(self, tracked_addresses):
        account_id, token, _session = _create_wallet_auth_session(tracked_addresses)
        asyncio.run(_grant_test_paid_access(account_id))
        asyncio.run(_seed_join_progress_with_legacy_parts(account_id))

        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        join = requests.post(_api('/join'), headers=headers, json={
            'name': 'TEST_JOINER', 'weapon': 'glock18', 'skin': 'soldier'
        }, timeout=20)
        assert join.status_code == 200
        first_token = join.json().get('token')
        assert isinstance(first_token, str) and len(first_token) > 10

        async def session_flow(join_token):
            ws = await websockets.connect(_ws_url(join_token), open_timeout=12)
            try:
                welcome = json.loads(await asyncio.wait_for(ws.recv(), timeout=8))
                assert welcome.get('type') == 'welcome'
                first_state = await _recv_first_state(ws)
                assert first_state.get('type') == 'state'
                assert first_state.get('me', {}).get('id')
                assert 'weapon_parts' in first_state.get('me', {})
                assert first_state['me']['weapon_parts'], 'weapon_parts must be non-empty to guard legacy regression'
                assert {part.get('id') for part in first_state['me']['weapon_parts']} >= {
                    'barrel_common', 'receiver_uncommon', 'optic_rare'
                }
                assert {part.get('tier') for part in first_state['me']['weapon_parts']} >= {1, 2, 3}

                x0 = float(first_state['me']['x'])
                z0 = float(first_state['me']['z'])
                for _ in range(10):
                    await ws.send(json.dumps({'type': 'input', 'x': 1.0, 'z': 0.0, 'fire': False, 'angle': 0.0}))
                    await asyncio.sleep(0.05)
                moved_state = await _recv_first_state(ws)
                moved = abs(float(moved_state['me']['x']) - x0) > 0.2 or abs(float(moved_state['me']['z']) - z0) > 0.2
                assert moved is True
                return moved_state['me']['weapon_parts']
            finally:
                await ws.close()
                # Let disconnect flush complete before next join.
                await asyncio.sleep(0.6)

        first_parts = asyncio.run(session_flow(first_token))

        rejoin = requests.post(_api('/join'), headers=headers, json={
            'name': 'TEST_JOINER', 'weapon': 'glock18', 'skin': 'soldier'
        }, timeout=20)
        assert rejoin.status_code == 200
        second_parts = asyncio.run(session_flow(rejoin.json()['token']))

        assert [p.get('id') for p in first_parts] == [p.get('id') for p in second_parts]

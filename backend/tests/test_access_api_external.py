"""External access-payment API guards using disposable unfunded wallets (no real transfer)."""

import asyncio
import os
from pathlib import Path
from urllib.parse import urlparse

import pytest
import requests
from dotenv import load_dotenv
from eth_account import Account
from eth_account.messages import encode_defunct
from motor.motor_asyncio import AsyncIOMotorClient


load_dotenv(Path(__file__).resolve().parents[2] / 'frontend' / '.env')
load_dotenv(Path(__file__).resolve().parents[1] / '.env')


# Modules/features covered: /api/access auth gating + unpaid account behavior + quote reuse.
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL')
if not BASE_URL:
    raise RuntimeError('REACT_APP_BACKEND_URL is required for external access tests')
BASE_URL = BASE_URL.rstrip('/')
API_BASE = f'{BASE_URL}/api'
MONGO_URL = (os.environ.get('MONGO_URL') or '').strip().strip('"')
DB_NAME = (os.environ.get('DB_NAME') or '').strip().strip('"')


def _origin_parts():
    parsed = urlparse(BASE_URL)
    return parsed.netloc, f'{parsed.scheme}://{parsed.netloc}'


def _challenge_payload(address: str):
    domain, uri = _origin_parts()
    return {'address': address, 'chain_id': 4663, 'domain': domain, 'uri': uri}


def _auth_session(addresses: set[str]):
    account = Account.create()
    addresses.add(account.address.lower())
    challenge = requests.post(f'{API_BASE}/auth/challenge', json=_challenge_payload(account.address), timeout=20)
    assert challenge.status_code == 200
    message = challenge.json()['message']
    signature = Account.sign_message(encode_defunct(text=message), private_key=account.key).signature.hex()
    session = requests.Session()
    verify = session.post(f'{API_BASE}/auth/verify', json={'message': message, 'signature': signature}, timeout=20)
    assert verify.status_code == 200
    return session, account.address


async def _cleanup_wallets(addresses: set[str]):
    if not (MONGO_URL and DB_NAME and addresses):
        return
    client = AsyncIOMotorClient(MONGO_URL)
    try:
        db = client[DB_NAME]
        addr_list = list(addresses)
        await db.auth_challenges.delete_many({'account_id': {'$in': addr_list}})
        await db.auth_sessions.delete_many({'account_id': {'$in': addr_list}})
        await db.player_progress.delete_many({'account_id': {'$in': addr_list}})
        await db.player_accounts.delete_many({'account_id': {'$in': addr_list}})
        await db.purchase_orders.delete_many({'account_id': {'$in': addr_list}})
        await db.access_entitlements.delete_many({'account_id': {'$in': addr_list}})
    finally:
        client.close()


@pytest.fixture(scope='class')
def tracked_addresses():
    addresses: set[str] = set()
    yield addresses
    asyncio.run(_cleanup_wallets(addresses))


class TestAccessApiExternal:
    def test_join_requires_auth_for_guest(self):
        response = requests.post(
            f'{API_BASE}/join',
            json={'name': 'Guest', 'weapon': 'glock18', 'skin': 'soldier'},
            timeout=20,
        )
        assert response.status_code == 401
        assert response.json().get('detail') == 'WALLET_SIGNATURE_REQUIRED'

    def test_unpaid_wallet_auth_has_no_access_and_join_returns_402(self, tracked_addresses):
        session, _ = _auth_session(tracked_addresses)

        me = session.get(f'{API_BASE}/auth/me', timeout=20)
        assert me.status_code == 200
        me_data = me.json()
        assert me_data.get('authenticated') is True
        assert me_data.get('paid_access') is False

        denied = session.post(
            f'{API_BASE}/join',
            json={'name': me_data['account']['nickname'], 'weapon': 'glock18', 'skin': 'soldier'},
            timeout=20,
        )
        assert denied.status_code == 402
        assert denied.json().get('detail') == 'ONE_TIME_ACCESS_PAYMENT_REQUIRED'

    def test_access_status_and_quote_require_auth(self):
        status = requests.get(f'{API_BASE}/access', timeout=20)
        quote = requests.post(f'{API_BASE}/access/quote', json={}, timeout=20)
        assert status.status_code == 401
        assert quote.status_code == 401

    def test_access_quote_reuses_active_order_and_fixed_terms(self, tracked_addresses):
        session, _ = _auth_session(tracked_addresses)

        status = session.get(f'{API_BASE}/access', timeout=20)
        assert status.status_code == 200
        status_data = status.json()
        assert status_data['paid'] is False
        assert status_data['price_usd'] == '1.00'
        assert status_data['chain_id'] == 4663
        assert status_data['treasury'].lower() == '0x45d9aa6ef98407dda4911c6f4a9af59f3de4e334'

        quote1 = session.post(f'{API_BASE}/access/quote', json={'paid': True, 'amount_wei': '1'}, timeout=20)
        quote2 = session.post(f'{API_BASE}/access/quote', json={}, timeout=20)
        assert quote1.status_code == 200 and quote2.status_code == 200
        q1 = quote1.json()
        q2 = quote2.json()
        assert q1['price_usd'] == '1.00' and q2['price_usd'] == '1.00'
        assert q1['order']['order_id'] == q2['order']['order_id']
        assert q1['order']['cents'] == 100
        assert q1['order']['quote']['chain_id'] == 4663
        assert q1['order']['quote']['recipient'].lower() == '0x45d9aa6ef98407dda4911c6f4a9af59f3de4e334'

    def test_access_submit_rejects_other_wallet_cross_order_use(self, tracked_addresses):
        session_a, _ = _auth_session(tracked_addresses)
        session_b, _ = _auth_session(tracked_addresses)

        quote = session_a.post(f'{API_BASE}/access/quote', json={}, timeout=20)
        assert quote.status_code == 200
        order_id = quote.json()['order']['order_id']

        stolen_submit = session_b.post(
            f'{API_BASE}/access/submit',
            json={'order_id': order_id, 'tx_hash': '0x' + 'f' * 64},
            timeout=20,
        )
        assert stolen_submit.status_code == 400
        assert stolen_submit.json().get('detail') == 'access_order_not_found'

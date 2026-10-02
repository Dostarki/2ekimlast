"""Isolated tests for admin wallet exports, gold grants and fee exemptions.

Does not touch user Atlas or production DB. Uses mongomock_motor + ASGI TestClient.
Credentials: NONE. Admin dependency is overridden with a stub for authorised cases,
and the real admin router is used only for 401 denial assertions.
"""
import os
import sys
import uuid
import asyncio
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Env must be set before importing admin_auth (reads at module import indirectly).
os.environ.setdefault('ADMIN_ORIGIN', 'https://admin.example.test')
os.environ.setdefault('ADMIN_PROXY_ORIGIN', 'https://proxy.example.test')
os.environ.setdefault('CORS_ORIGINS', 'https://admin.example.test')
os.environ.setdefault('JWT_SECRET', 'test-secret-not-production')
os.environ.setdefault('ADMIN_PASSWORD_HASH', '$2b$12$' + 'a' * 53)
os.environ.setdefault('MONGO_URL', 'mongodb://localhost:27017')
os.environ.setdefault('DB_NAME', 'test_admin_isolated')

from fastapi import FastAPI
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient

from admin_wallets import wallet_admin_router  # noqa: E402
from admin_routes import create_admin_router  # noqa: E402
import access_payments  # noqa: E402
import player_accounts  # noqa: E402


# --------------------------- Fixtures ---------------------------

@pytest.fixture(autouse=True)
def isolate_file_backup(tmp_path, monkeypatch):
    monkeypatch.setattr(player_accounts, 'LOCAL_STORAGE_FILE', tmp_path / 'test-storage.json')


@pytest.fixture
def db():
    return AsyncMongoMockClient()['game_test']


@pytest.fixture
def early_db():
    return AsyncMongoMockClient()['early_test']


class DummyGame:
    settings = {'bot_count': 0}
    class _LocalSessions:
        async def active(self):
            return []
    local_sessions = _LocalSessions()


@pytest.fixture
def authed_app(db, early_db):
    """App that mounts wallet_admin_router directly (auth bypassed)."""
    app = FastAPI()
    app.include_router(wallet_admin_router(db, early_db), prefix='/api/admin')
    return app


@pytest.fixture
def guarded_app(db, early_db):
    """App that mounts full admin router WITH require_admin gate."""
    app = FastAPI()
    app.include_router(create_admin_router(db, DummyGame(), early_db=early_db))
    return app


@pytest.fixture
def client(authed_app):
    return TestClient(authed_app)


@pytest.fixture
def guarded_client(guarded_app):
    return TestClient(guarded_app)


async def _seed_account(db, wallet, nickname='TestPlayer'):
    """Register a player account + progress using real helper."""
    # bypass checksum validation: eth_utils may reject invalid hex -> use plausible wallet
    from player_accounts import create_or_update_profile
    try:
        return await create_or_update_profile(db, wallet, nickname)
    except Exception:
        # Fallback minimal doc
        await db.player_accounts.insert_one({'account_id': wallet.lower(), 'nickname': nickname})
        await db.player_progress.insert_one(player_accounts.create_initial_progress(wallet))
        return {'account_id': wallet.lower()}


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# --------------------------- Export tests ---------------------------

class TestGameWalletExport:
    def test_empty_returns_empty_body(self, client):
        r = client.get('/api/admin/wallets/game.txt')
        assert r.status_code == 200
        assert r.headers['content-type'].startswith('text/plain')
        assert 'attachment' in r.headers['content-disposition']
        assert 'lastzhood-game-wallets.txt' in r.headers['content-disposition']
        assert r.text == ''

    def test_normalized_unique_sorted(self, db, client):
        valid = [
            '0x' + 'a' * 40,
            '0x' + 'A' * 40,  # dup after lower
            '0x' + 'b' * 40,
            '0x' + '0' * 40,  # zero -> excluded
            'not-a-wallet',   # excluded by regex
        ]
        for i, w in enumerate(valid):
            run(db.player_accounts.insert_one({'account_id': w, 'nickname': f'n{i}'}))
        r = client.get('/api/admin/wallets/game.txt')
        assert r.status_code == 200
        lines = [l for l in r.text.split('\n') if l]
        assert lines == sorted(set(['0x' + 'a' * 40, '0x' + 'b' * 40]))

    def test_early_export_requires_early_db(self, db):
        app = FastAPI()
        app.include_router(wallet_admin_router(db, None), prefix='/api/admin')
        c = TestClient(app)
        r = c.get('/api/admin/wallets/early.txt')
        assert r.status_code == 503

    def test_early_export_dedup(self, early_db, client):
        for w in ['0x' + 'c' * 40, '0x' + 'C' * 40, '0x' + 'd' * 40]:
            run(early_db.agents.insert_one({'wallet': w}))
        r = client.get('/api/admin/wallets/early.txt')
        assert r.status_code == 200
        lines = sorted(l for l in r.text.split('\n') if l)
        assert lines == ['0x' + 'c' * 40, '0x' + 'd' * 40]


# --------------------------- Auth denial ---------------------------

class TestAdminAuthDenial:
    def test_game_export_unauth_401(self, guarded_client):
        r = guarded_client.get('/api/admin/wallets/game.txt')
        assert r.status_code == 401

    def test_gold_unauth_denied(self, guarded_client):
        # POST without session + no Origin header -> origin check 403 (defense in depth)
        r = guarded_client.post('/api/admin/wallets/gold', json={
            'wallet': '0x' + 'a' * 40, 'amount': 10, 'request_id': str(uuid.uuid4())})
        assert r.status_code in (401, 403)

    def test_exemption_unauth_denied(self, guarded_client):
        r = guarded_client.put('/api/admin/wallets/fee-exemption', json={
            'wallet': '0x' + 'a' * 40, 'enabled': True})
        assert r.status_code in (401, 403)


# --------------------------- Gold grant ---------------------------

class TestGoldGrant:
    def test_rejects_unregistered(self, client):
        r = client.post('/api/admin/wallets/gold', json={
            'wallet': '0x' + 'e' * 40, 'amount': 100, 'request_id': str(uuid.uuid4())})
        assert r.status_code == 404

    def test_rejects_invalid_amount(self, client):
        for bad in [0, -5, '10', 1_000_000_001]:
            r = client.post('/api/admin/wallets/gold', json={
                'wallet': '0x' + 'f' * 40, 'amount': bad, 'request_id': str(uuid.uuid4())})
            assert r.status_code in (400, 422), f'amount={bad!r} -> {r.status_code}'

    def test_rejects_bad_wallet(self, client):
        r = client.post('/api/admin/wallets/gold', json={
            'wallet': 'nope', 'amount': 10, 'request_id': str(uuid.uuid4())})
        assert r.status_code == 422

    def test_grants_and_adds_to_balance(self, db, client):
        wallet = '0x' + '1' * 40
        run(_seed_account(db, wallet, 'Alice'))
        req = str(uuid.uuid4())
        r = client.post('/api/admin/wallets/gold', json={
            'wallet': wallet, 'amount': 500, 'request_id': req})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data['wallet'] == wallet
        assert data['amount'] == 500
        # initial 150 + 500 = 650
        assert data['gold'] == 650
        assert data['request_id'] == req

        # Verify persisted via lookup
        r2 = client.get(f'/api/admin/wallets/{wallet}')
        assert r2.status_code == 200
        state = r2.json()
        assert state['registered'] is True
        assert state['gold'] == 650
        assert state['paid_access'] is False
        assert state['fee_exempt'] is False

    def test_idempotent_same_request_id(self, db, client):
        wallet = '0x' + '2' * 40
        run(_seed_account(db, wallet, 'Bob'))
        req = str(uuid.uuid4())
        payload = {'wallet': wallet, 'amount': 300, 'request_id': req}
        r1 = client.post('/api/admin/wallets/gold', json=payload)
        r2 = client.post('/api/admin/wallets/gold', json=payload)
        assert r1.status_code == 200 and r2.status_code == 200
        assert r1.json()['gold'] == r2.json()['gold']
        # Verify no double-add
        r3 = client.get(f'/api/admin/wallets/{wallet}')
        assert r3.json()['gold'] == 150 + 300

    def test_same_request_id_different_amount_conflict(self, db, client):
        wallet = '0x' + '3' * 40
        run(_seed_account(db, wallet, 'Carol'))
        req = str(uuid.uuid4())
        r1 = client.post('/api/admin/wallets/gold', json={
            'wallet': wallet, 'amount': 100, 'request_id': req})
        assert r1.status_code == 200
        r2 = client.post('/api/admin/wallets/gold', json={
            'wallet': wallet, 'amount': 999, 'request_id': req})
        assert r2.status_code == 409


# --------------------------- Fee exemption ---------------------------

class TestFeeExemption:
    def test_grant_before_registration(self, db, client):
        wallet = '0x' + '4' * 40
        r = client.put('/api/admin/wallets/fee-exemption', json={
            'wallet': wallet, 'enabled': True})
        assert r.status_code == 200
        state = r.json()
        assert state['registered'] is False
        assert state['fee_exempt'] is True
        assert state['paid_access'] is False  # never fabricated
        assert state['gold'] is None
        # Document stored under lowercased key
        doc = run(db.game_fee_exemptions.find_one({'_id': wallet.lower()}))
        assert doc is not None

    def test_case_insensitive_and_idempotent(self, db, client):
        wallet_mixed = '0x' + 'A5' * 20
        r1 = client.put('/api/admin/wallets/fee-exemption', json={
            'wallet': wallet_mixed, 'enabled': True})
        assert r1.status_code == 200
        r2 = client.put('/api/admin/wallets/fee-exemption', json={
            'wallet': wallet_mixed.lower(), 'enabled': True})
        assert r2.status_code == 200
        count = run(db.game_fee_exemptions.count_documents({'_id': wallet_mixed.lower()}))
        assert count == 1

    def test_revoke(self, db, client):
        wallet = '0x' + '6' * 40
        client.put('/api/admin/wallets/fee-exemption', json={'wallet': wallet, 'enabled': True})
        r = client.put('/api/admin/wallets/fee-exemption', json={'wallet': wallet, 'enabled': False})
        assert r.status_code == 200
        assert r.json()['fee_exempt'] is False
        assert run(db.game_fee_exemptions.count_documents({'_id': wallet.lower()})) == 0

    def test_exempt_quote_creates_no_order(self, db, client):
        wallet = '0x' + '7' * 40
        client.put('/api/admin/wallets/fee-exemption', json={'wallet': wallet, 'enabled': True})
        # Call quote_access directly; must not call chain or create order
        state = run(access_payments.quote_access(db, wallet))
        assert state['fee_exempt'] is True
        assert state['paid'] is False
        assert state['order'] is None
        assert run(db.purchase_orders.count_documents({})) == 0

    def test_other_wallets_still_need_payment(self, db, client):
        exempt = '0x' + '8' * 40
        other = '0x' + '9' * 40
        client.put('/api/admin/wallets/fee-exemption', json={'wallet': exempt, 'enabled': True})
        other_state = run(access_payments.access_status(db, other))
        assert other_state['fee_exempt'] is False
        assert other_state['paid'] is False


# --------------------------- Wallet lookup ---------------------------

class TestWalletLookup:
    def test_unknown_wallet(self, client):
        wallet = '0x' + 'b' * 40
        r = client.get(f'/api/admin/wallets/{wallet}')
        assert r.status_code == 200
        d = r.json()
        assert d['registered'] is False
        assert d['nickname'] is None
        assert d['gold'] is None
        assert d['fee_exempt'] is False
        assert d['paid_access'] is False

    def test_bad_wallet_422(self, client):
        r = client.get('/api/admin/wallets/not-a-wallet')
        assert r.status_code == 422

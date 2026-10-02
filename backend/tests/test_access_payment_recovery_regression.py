"""Access payment recovery regressions for durable verified orders and backup restore."""

import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest
from dotenv import load_dotenv
from mongomock_motor import AsyncMongoMockClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from chain_config import CHAIN_ID
import access_payments
import player_accounts


def _run(coro):
    return asyncio.run(coro)


def _expired_quote(quote_id: str = 'q-old'):
    now = datetime.now(timezone.utc)
    return {
        'quote_id': quote_id,
        'chain_id': CHAIN_ID,
        'recipient': '0x1111111111111111111111111111111111111111',
        'usd_per_eth': '2000',
        'amount_wei': '500000000000000',
        'issued_at': (now - timedelta(minutes=20)).isoformat(),
        'expires_at': (now - timedelta(minutes=10)).isoformat(),
        'payment_mode': 'native_transfer',
    }


def test_recover_paid_access_from_verified_fulfilled_order_and_submit_short_circuits(tmp_path, monkeypatch):
    """Modules/features: restore paid=true from durable verified order and no re-verify on fulfilled submit."""

    monkeypatch.setattr(player_accounts, 'LOCAL_STORAGE_FILE', tmp_path / 'local.json')

    async def scenario():
        db = AsyncMongoMockClient().test
        owner = '0x2000000000000000000000000000000000000001'
        tx_hash = '0x' + '1' * 64
        order_id = 'ord-recover-fulfilled'
        verified_at = '2026-02-01T12:00:00+00:00'
        fulfilled_at = '2026-02-01T12:01:00+00:00'
        quote = _expired_quote('q-recover')

        await db.purchase_orders.insert_one({
            'order_id': order_id,
            'account_id': owner,
            'access_wallet': owner,
            'authenticated_wallet': owner,
            'kind': 'access',
            'sku': 'game_access',
            'status': 'fulfilled',
            'chain_id': CHAIN_ID,
            'tx_hash': tx_hash,
            'quote': quote,
            'payment_verified': True,
            'payment_confirmations': 13,
            'payment_verified_at': verified_at,
            'fulfilled_at': fulfilled_at,
            'created_at': '2026-02-01T11:59:00+00:00',
        })

        paid = await access_payments.has_paid_access(db, owner)
        assert paid is True

        async def should_not_verify(*_args, **_kwargs):
            raise AssertionError('verify_transaction must not run for already fulfilled order')

        monkeypatch.setattr(access_payments, 'verify_transaction', should_not_verify)
        submit_result = await access_payments.submit_access(db, owner, order_id, tx_hash)
        assert submit_result['paid'] is True

        status = await access_payments.access_status(db, owner)
        assert status['paid'] is True
        assert status['order']['order_id'] == order_id
        assert status['order']['tx_hash'] == tx_hash
        assert status['order']['quote']['quote_id'] == 'q-recover'

    _run(scenario())


def test_recovery_idempotent_and_preserves_verified_and_fulfilled_timestamps(tmp_path, monkeypatch):
    """Modules/features: repeated recovery is idempotent and keeps original order timestamps."""

    monkeypatch.setattr(player_accounts, 'LOCAL_STORAGE_FILE', tmp_path / 'local.json')

    async def scenario():
        db = AsyncMongoMockClient().test
        owner = '0x2000000000000000000000000000000000000002'
        tx_hash = '0x' + '2' * 64
        verified_at = '2026-02-02T10:00:00+00:00'
        fulfilled_at = '2026-02-02T10:01:00+00:00'
        await db.purchase_orders.insert_one({
            'order_id': 'ord-ts-preserve',
            'account_id': owner,
            'access_wallet': owner,
            'kind': 'access',
            'status': 'fulfilled',
            'chain_id': CHAIN_ID,
            'tx_hash': tx_hash,
            'quote': _expired_quote('q-ts'),
            'payment_verified': True,
            'payment_verified_at': verified_at,
            'fulfilled_at': fulfilled_at,
        })

        assert await access_payments.has_paid_access(db, owner) is True
        assert await access_payments.has_paid_access(db, owner) is True

        order = await db.purchase_orders.find_one({'order_id': 'ord-ts-preserve'}, {'_id': 0})
        entitlement = await db.access_entitlements.find_one({'account_id': owner}, {'_id': 0})
        assert order['payment_verified_at'] == verified_at
        assert order['fulfilled_at'] == fulfilled_at
        assert entitlement['confirmed_at'] == verified_at
        assert await db.access_entitlements.count_documents({'account_id': owner}) == 1

    _run(scenario())


def test_recovery_never_grants_for_non_eligible_orders():
    """Modules/features: pending/unverified/failed/wrong-wallet/wrong-chain/market orders never unlock access."""

    async def scenario():
        db = AsyncMongoMockClient().test
        await db.purchase_orders.insert_many([
            {
                'order_id': 'ord-pending',
                'account_id': '0x2000000000000000000000000000000000000011',
                'kind': 'access',
                'status': 'confirming',
                'chain_id': CHAIN_ID,
                'tx_hash': '0x' + 'a' * 64,
                'quote': _expired_quote('q-pending'),
                'payment_verified': False,
            },
            {
                'order_id': 'ord-unverified-fulfilled',
                'account_id': '0x2000000000000000000000000000000000000012',
                'kind': 'access',
                'status': 'fulfilled',
                'chain_id': CHAIN_ID,
                'tx_hash': '0x' + 'b' * 64,
                'quote': _expired_quote('q-unverified'),
                'payment_verified': False,
            },
            {
                'order_id': 'ord-failed',
                'account_id': '0x2000000000000000000000000000000000000013',
                'kind': 'access',
                'status': 'payment_failed',
                'chain_id': CHAIN_ID,
                'tx_hash': '0x' + 'c' * 64,
                'quote': _expired_quote('q-failed'),
                'payment_verified': False,
            },
            {
                'order_id': 'ord-wrong-chain',
                'account_id': '0x2000000000000000000000000000000000000014',
                'kind': 'access',
                'status': 'fulfilled',
                'chain_id': CHAIN_ID + 1,
                'tx_hash': '0x' + 'd' * 64,
                'quote': _expired_quote('q-wrong-chain'),
                'payment_verified': True,
            },
            {
                'order_id': 'ord-market-kind',
                'account_id': '0x2000000000000000000000000000000000000015',
                'kind': 'market',
                'status': 'fulfilled',
                'chain_id': CHAIN_ID,
                'tx_hash': '0x' + 'e' * 64,
                'quote': _expired_quote('q-market'),
                'payment_verified': True,
            },
            {
                'order_id': 'ord-other-wallet',
                'account_id': '0x2000000000000000000000000000000000000016',
                'kind': 'access',
                'status': 'fulfilled',
                'chain_id': CHAIN_ID,
                'tx_hash': '0x' + 'f' * 64,
                'quote': _expired_quote('q-other-wallet'),
                'payment_verified': True,
            },
        ])

        blocked_accounts = [
            '0x2000000000000000000000000000000000000011',
            '0x2000000000000000000000000000000000000012',
            '0x2000000000000000000000000000000000000013',
            '0x2000000000000000000000000000000000000014',
            '0x2000000000000000000000000000000000000015',
            '0x2000000000000000000000000000000000000099',
        ]
        for account in blocked_accounts:
            assert await access_payments.has_paid_access(db, account) is False

        assert await db.access_entitlements.count_documents({}) == 0

    _run(scenario())


def test_sync_roundtrip_preserves_access_entitlements(tmp_path, monkeypatch):
    """Modules/features: sync_db_to_file/sync_db_from_file keep access_entitlements data."""

    storage_path = tmp_path / 'roundtrip_storage.json'
    monkeypatch.setattr(player_accounts, 'LOCAL_STORAGE_FILE', storage_path)

    async def scenario():
        source_db = AsyncMongoMockClient().source
        owner = '0x2000000000000000000000000000000000000007'
        await source_db.purchase_orders.insert_one({
            'order_id': 'ord-roundtrip',
            'account_id': owner,
            'kind': 'access',
            'status': 'fulfilled',
            'chain_id': CHAIN_ID,
            'tx_hash': '0x' + '7' * 64,
            'quote': _expired_quote('q-roundtrip'),
            'payment_verified': True,
        })
        await source_db.access_entitlements.insert_one({
            'account_id': owner,
            'paid': True,
            'chain_id': CHAIN_ID,
            'source_order_id': 'ord-roundtrip',
            'tx_hash': '0x' + '7' * 64,
            'quote': _expired_quote('q-roundtrip'),
            'confirmed_at': '2026-02-07T07:00:00+00:00',
        })

        await player_accounts.sync_db_to_file(source_db)
        target_db = AsyncMongoMockClient().target
        await player_accounts.sync_db_from_file(target_db)

        restored_entitlement = await target_db.access_entitlements.find_one({'account_id': owner}, {'_id': 0})
        restored_order = await target_db.purchase_orders.find_one({'order_id': 'ord-roundtrip'}, {'_id': 0})
        assert restored_entitlement['paid'] is True
        assert restored_entitlement['source_order_id'] == 'ord-roundtrip'
        assert restored_order['payment_verified'] is True

    _run(scenario())


def test_legacy_backup_with_verified_fulfilled_access_order_self_heals(tmp_path, monkeypatch):
    """Modules/features: legacy backup missing entitlements self-heals from verified fulfilled access order."""

    storage_path = tmp_path / 'legacy_storage.json'
    monkeypatch.setattr(player_accounts, 'LOCAL_STORAGE_FILE', storage_path)

    owner = '0x2000000000000000000000000000000000000008'
    legacy_payload = {
        'purchase_orders': [{
            'order_id': 'ord-legacy-heal',
            'account_id': owner,
            'access_wallet': owner,
            'kind': 'access',
            'status': 'fulfilled',
            'chain_id': CHAIN_ID,
            'tx_hash': '0x' + '8' * 64,
            'quote': _expired_quote('q-legacy'),
            'payment_verified': True,
            'payment_verified_at': '2026-02-08T08:00:00+00:00',
        }],
        'saved_at': '2026-02-08T08:05:00+00:00',
    }
    storage_path.write_text(json.dumps(legacy_payload), encoding='utf-8')

    async def scenario():
        db = AsyncMongoMockClient().test
        await player_accounts.sync_db_from_file(db)

        assert await access_payments.has_paid_access(db, owner) is True
        entitlement = await db.access_entitlements.find_one({'account_id': owner}, {'_id': 0})
        assert entitlement['paid'] is True
        assert entitlement['source_order_id'] == 'ord-legacy-heal'

    _run(scenario())

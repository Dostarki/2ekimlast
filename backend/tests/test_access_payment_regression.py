"""Access payment regressions with isolated Mongo + mocked chain verification."""

import asyncio
import os
import sys
from decimal import Decimal

import pytest
from mongomock_motor import AsyncMongoMockClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import access_payments
import market_payments
import player_accounts


def _run(coro):
    return asyncio.run(coro)


async def _seed_account(db, account_id: str):
    await db.player_accounts.insert_one({'account_id': account_id, 'nickname': 'Survivor'})
    await db.player_progress.insert_one(player_accounts.create_initial_progress(account_id))


def test_access_quote_reuses_one_active_order_and_keeps_price_fixed(tmp_path, monkeypatch):
    """Modules/features: access quote creation and idempotent active-order reuse."""

    monkeypatch.setattr(player_accounts, 'LOCAL_STORAGE_FILE', tmp_path / 'local.json')

    async def scenario():
        db = AsyncMongoMockClient().test
        account = '0x1000000000000000000000000000000000000001'
        await _seed_account(db, account)
        await player_accounts.setup_account_indexes(db)
        await access_payments.ensure_access_indexes(db)
        loop = asyncio.get_running_loop()
        market_payments._PRICE_CACHE.update(value=Decimal('2000'), expires=loop.time() + 60)

        first = await access_payments.quote_access(db, account)
        second = await access_payments.quote_access(db, account)

        assert first['paid'] is False
        assert first['price_usd'] == '1.00'
        assert second['order']['order_id'] == first['order']['order_id']
        assert await db.purchase_orders.count_documents({'kind': 'access', 'account_id': account}) == 1

    _run(scenario())


def test_access_submit_pending_confirmation_never_grants_entitlement(tmp_path, monkeypatch):
    """Modules/features: access submit waits for 1 confirmation before entitlement."""

    monkeypatch.setattr(player_accounts, 'LOCAL_STORAGE_FILE', tmp_path / 'local.json')

    async def scenario():
        db = AsyncMongoMockClient().test
        account = '0x1000000000000000000000000000000000000002'
        tx_hash = '0x' + 'a' * 64
        await _seed_account(db, account)
        await player_accounts.setup_account_indexes(db)
        await access_payments.ensure_access_indexes(db)
        loop = asyncio.get_running_loop()
        market_payments._PRICE_CACHE.update(value=Decimal('2000'), expires=loop.time() + 60)

        state = await access_payments.quote_access(db, account)
        order_id = state['order']['order_id']

        async def fake_verify(_db, _order, _hash, _owner, *, required_confirmations):
            assert required_confirmations == 1
            return {'status': 'confirming', 'verified': False, 'confirmations': 1}

        monkeypatch.setattr(access_payments, 'verify_transaction', fake_verify)
        result = await access_payments.submit_access(db, account, order_id, tx_hash)

        assert result['paid'] is False
        assert result['order']['status'] == 'confirming'
        assert await access_payments.has_paid_access(db, account) is False

    _run(scenario())


def test_access_verified_payment_grants_once_and_repeat_submit_is_idempotent(tmp_path, monkeypatch):
    """Modules/features: verified access payment -> permanent entitlement -> no double grant."""

    monkeypatch.setattr(player_accounts, 'LOCAL_STORAGE_FILE', tmp_path / 'local.json')

    async def scenario():
        db = AsyncMongoMockClient().test
        account = '0x1000000000000000000000000000000000000003'
        tx_hash = '0x' + 'b' * 64
        await _seed_account(db, account)
        await player_accounts.setup_account_indexes(db)
        await access_payments.ensure_access_indexes(db)
        loop = asyncio.get_running_loop()
        market_payments._PRICE_CACHE.update(value=Decimal('2000'), expires=loop.time() + 60)

        state = await access_payments.quote_access(db, account)
        order = state['order']

        async def fake_verify(_db, _order, _hash, _owner, *, required_confirmations):
            assert required_confirmations == 1
            return {
                'status': 'paid',
                'verified': True,
                'tx_hash': tx_hash,
                'confirmations': 2,
                'account_id': account,
                'chain_id': 4663,
                'quote_id': order['quote']['quote_id'],
            }

        monkeypatch.setattr(access_payments, 'verify_transaction', fake_verify)
        first = await access_payments.submit_access(db, account, order['order_id'], tx_hash)
        second = await access_payments.submit_access(db, account, order['order_id'], tx_hash)

        assert first['paid'] is True and second['paid'] is True
        assert await db.access_entitlements.count_documents({'account_id': account}) == 1
        assert await db.purchase_orders.count_documents({'order_id': order['order_id'], 'status': 'fulfilled'}) == 1

    _run(scenario())


def test_access_failed_receipt_keeps_audit_and_allows_new_attempt(tmp_path, monkeypatch):
    """Modules/features: reverted tx does not unlock and can request fresh access quote."""

    monkeypatch.setattr(player_accounts, 'LOCAL_STORAGE_FILE', tmp_path / 'local.json')

    async def scenario():
        db = AsyncMongoMockClient().test
        account = '0x1000000000000000000000000000000000000004'
        tx_hash = '0x' + 'c' * 64
        await _seed_account(db, account)
        await player_accounts.setup_account_indexes(db)
        await access_payments.ensure_access_indexes(db)
        loop = asyncio.get_running_loop()
        market_payments._PRICE_CACHE.update(value=Decimal('2000'), expires=loop.time() + 60)

        initial = await access_payments.quote_access(db, account)
        first_order_id = initial['order']['order_id']

        async def fake_failed(_db, _order, _hash, _owner, *, required_confirmations):
            assert required_confirmations == 1
            raise ValueError('payment_failed')

        monkeypatch.setattr(access_payments, 'verify_transaction', fake_failed)
        with pytest.raises(ValueError, match='payment_failed'):
            await access_payments.submit_access(db, account, first_order_id, tx_hash)

        failed_order = await db.purchase_orders.find_one({'order_id': first_order_id}, {'_id': 0})
        assert failed_order['status'] == 'payment_failed'
        assert 'access_wallet' not in failed_order

        retry = await access_payments.quote_access(db, account)
        assert retry['paid'] is False
        assert retry['order']['order_id'] != first_order_id

    _run(scenario())


def test_access_accepts_verified_old_quote_from_quote_history(tmp_path, monkeypatch):
    """Modules/features: old quote history remains valid when verification returns older quote_id."""

    monkeypatch.setattr(player_accounts, 'LOCAL_STORAGE_FILE', tmp_path / 'local.json')

    async def scenario():
        db = AsyncMongoMockClient().test
        account = '0x1000000000000000000000000000000000000005'
        tx_hash = '0x' + 'd' * 64
        await _seed_account(db, account)
        await player_accounts.setup_account_indexes(db)
        await access_payments.ensure_access_indexes(db)
        loop = asyncio.get_running_loop()
        market_payments._PRICE_CACHE.update(value=Decimal('2000'), expires=loop.time() + 60)

        state = await access_payments.quote_access(db, account)
        order = state['order']
        old_quote = dict(order['quote'])
        new_quote = dict(order['quote'])
        new_quote['quote_id'] = 'q-new'
        new_quote['calldata'] = market_payments.marker_for(order['order_id'], 'q-new')
        await db.purchase_orders.update_one(
            {'order_id': order['order_id']},
            {'$set': {'quote': new_quote, 'quote_history': [old_quote], 'status': 'awaiting_payment'}},
        )

        async def fake_verify(_db, _order, _hash, _owner, *, required_confirmations):
            assert required_confirmations == 1
            return {
                'status': 'paid',
                'verified': True,
                'tx_hash': tx_hash,
                'confirmations': 2,
                'account_id': account,
                'chain_id': 4663,
                'quote_id': old_quote['quote_id'],
            }

        monkeypatch.setattr(access_payments, 'verify_transaction', fake_verify)
        result = await access_payments.submit_access(db, account, order['order_id'], tx_hash)
        entitlement = await db.access_entitlements.find_one({'account_id': account}, {'_id': 0})

        assert result['paid'] is True
        assert entitlement['quote']['quote_id'] == old_quote['quote_id']

    _run(scenario())


def test_access_concurrent_duplicate_submits_do_not_double_grant(tmp_path, monkeypatch):
    """Modules/features: concurrent duplicate submit races stay idempotent."""

    monkeypatch.setattr(player_accounts, 'LOCAL_STORAGE_FILE', tmp_path / 'local.json')

    async def scenario():
        db = AsyncMongoMockClient().test
        account = '0x1000000000000000000000000000000000000006'
        tx_hash = '0x' + 'e' * 64
        await _seed_account(db, account)
        await player_accounts.setup_account_indexes(db)
        await access_payments.ensure_access_indexes(db)
        loop = asyncio.get_running_loop()
        market_payments._PRICE_CACHE.update(value=Decimal('2000'), expires=loop.time() + 60)

        state = await access_payments.quote_access(db, account)
        order = state['order']

        async def slow_verified(_db, _order, _hash, _owner, *, required_confirmations):
            assert required_confirmations == 1
            await asyncio.sleep(0.03)
            return {
                'status': 'paid',
                'verified': True,
                'tx_hash': tx_hash,
                'confirmations': 2,
                'account_id': account,
                'chain_id': 4663,
                'quote_id': order['quote']['quote_id'],
            }

        monkeypatch.setattr(access_payments, 'verify_transaction', slow_verified)
        results = await asyncio.gather(
            access_payments.submit_access(db, account, order['order_id'], tx_hash),
            access_payments.submit_access(db, account, order['order_id'], tx_hash),
            return_exceptions=True,
        )

        assert any(not isinstance(r, Exception) and r.get('paid') is True for r in results)
        assert await db.access_entitlements.count_documents({'account_id': account}) == 1

    _run(scenario())

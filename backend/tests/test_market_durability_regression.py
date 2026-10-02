import asyncio
from pathlib import Path
import sys
import os
from decimal import Decimal
import time
from datetime import datetime, timezone

import pytest
from mongomock_motor import AsyncMongoMockClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import player_accounts
from offgame_market import create_purchase_order, finalize_order_fulfillment
from offgame_market import claim_delivery_item
from missions import start_soldier_mission, claim_soldier_mission
import market_payments
from economy import record_economy_ledger


def _run(coro):
    return asyncio.run(coro)


def test_progress_cas_migrates_revisionless_save_and_rejects_stale_writer(tmp_path, monkeypatch):
    monkeypatch.setattr(player_accounts, 'LOCAL_STORAGE_FILE', tmp_path / 'local.json')
    async def scenario():
        db = AsyncMongoMockClient().test
        await db.player_progress.insert_one({'account_id': 'acct', 'gold': 50})
        first = await player_accounts.get_player_progress(db, 'acct')
        assert first.get('revision') is None  # legacy document remains readable
        first['gold'] = 60
        saved = await player_accounts.save_player_progress(db, 'acct', first)
        assert saved['revision'] == 2
        stale = dict(first)
        stale['revision'] = 1
        stale['gold'] = 999
        with pytest.raises(RuntimeError, match='progress_revision_conflict'):
            await player_accounts.save_player_progress(db, 'acct', stale)
        persisted = await db.player_progress.find_one({'account_id': 'acct'})
        assert persisted['gold'] == 60 and persisted['revision'] == 2
    _run(scenario())


def test_paid_order_retry_recovers_persisted_rng_and_delivery_after_progress_commit(tmp_path, monkeypatch):
    monkeypatch.setattr(player_accounts, 'LOCAL_STORAGE_FILE', tmp_path / 'local.json')
    async def scenario():
        db = AsyncMongoMockClient().test
        account = '0x1111111111111111111111111111111111111111'
        await db.player_accounts.insert_one({'account_id': account, 'nickname': 'Survivor'})
        progress = player_accounts.create_initial_progress(account)
        progress.update(gold=9, heal_items={'medkit': 3, 'faid': 5}, consumables={'energy_drink': 10})
        await db.player_progress.insert_one(progress)
        order = await create_purchase_order(db, account, 'pack_field')
        tx_hash = '0x' + 'a' * 64
        await db.purchase_orders.update_one({'order_id': order['order_id']},
            {'$set': {'status': 'awaiting_payment', 'tx_hash': tx_hash, 'chain_id': 4663}})

        original_save = player_accounts.save_player_progress
        failed = {'once': False}
        async def save_then_crash(*args, **kwargs):
            result = await original_save(*args, **kwargs)
            if not failed['once']:
                failed['once'] = True
                raise RuntimeError('simulated crash after progress commit')
            return result
        monkeypatch.setattr(player_accounts, 'save_player_progress', save_then_crash)
        verified = {'verified': True, 'status': 'paid', 'account_id': account, 'chain_id': 4663}
        with pytest.raises(RuntimeError, match='simulated crash'):
            await finalize_order_fulfillment(db, order['order_id'], tx_hash, verified_payment=verified)
        after_crash = await player_accounts.get_player_progress(db, account)
        assert after_crash['gold'] == 1009
        assert after_crash['applied_market_order_ids'] == [order['order_id']]
        assert (await db.purchase_orders.find_one({'order_id': order['order_id']}))['grant_plan']['inbox_items']

        monkeypatch.setattr(player_accounts, 'save_player_progress', original_save)
        delivered = await finalize_order_fulfillment(db, order['order_id'], tx_hash, verified_payment=verified)
        assert delivered['status'] == 'fulfilled'
        final = await player_accounts.get_player_progress(db, account)
        assert final['gold'] == 1009
        entitlements = await db.delivery_inbox.find({'account_id': account, 'status': 'pending'}).to_list(10)
        assert len(entitlements) == 1
        # Retrying terminal delivery is a read-only idempotent result.
        await finalize_order_fulfillment(db, order['order_id'], tx_hash, verified_payment=verified)
        final_again = await player_accounts.get_player_progress(db, account)
        assert final_again['gold'] == 1009
    _run(scenario())


def test_mission_uses_canonical_roster_and_claim_is_restart_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(player_accounts, 'LOCAL_STORAGE_FILE', tmp_path / 'local.json')
    async def scenario():
        db = AsyncMongoMockClient().test
        account = '0x2222222222222222222222222222222222222222'
        await db.player_accounts.insert_one({'account_id': account, 'nickname': 'Survivor'})
        progress = player_accounts.create_initial_progress(account)
        progress['owned_soldiers'] = [{
            'instance_id': 'soldier-one', 'tier_id': 'soldier_s2', 'nickname': 'Scout',
            'runtime': {'hp': 51, 'ammo': 7, 'recovery_until_utc': 0},
        }]
        progress['active_soldier_ids'] = ['soldier-one']
        await db.player_progress.insert_one(progress)
        refused = await start_soldier_mission(db, account, 'soldier-one', 'start-refused')
        assert refused == {'success': False, 'code': 'soldier_in_combat'}

        started = await start_soldier_mission(db, account, 'soldier-one', 'start-1', recall_active=True)
        assert started['success'] is True
        mission = started['mission']
        assert mission['tier_at_start'] == 'soldier_s2' and mission['reward_gold'] == 160
        saved = await player_accounts.get_player_progress(db, account)
        assert saved['active_soldier_ids'] == []
        soldier = saved['owned_soldiers'][0]
        assert soldier['current_mission_id'] == mission['mission_id']
        assert soldier['runtime']['hp'] == 51 and soldier['runtime']['ammo'] == 7

        too_early = await claim_soldier_mission(db, account, mission['mission_id'])
        assert too_early['success'] is False and too_early['code'] == 'mission_not_ready'
        await db.soldier_missions.update_one({'mission_id': mission['mission_id']},
            {'$set': {'end_utc': '2000-01-01T00:00:00+00:00'}})
        first = await claim_soldier_mission(db, account, mission['mission_id'], 'claim-1')
        second = await claim_soldier_mission(db, account, mission['mission_id'], 'claim-1')
        assert first['success'] and first['newly_applied']
        assert second['success'] and not second['newly_applied']
        final = await player_accounts.get_player_progress(db, account)
        assert final['gold'] == 310
        assert final['owned_soldiers'][0].get('current_mission_id') is None
    _run(scenario())


def test_quote_creation_and_renewal_never_replace_a_live_winner(tmp_path, monkeypatch):
    monkeypatch.setattr(player_accounts, 'LOCAL_STORAGE_FILE', tmp_path / 'local.json')
    async def scenario():
        db = AsyncMongoMockClient().test
        order = {'order_id': 'order-quote', 'account_id': '0x3333333333333333333333333333333333333333',
                 'cents': 200, 'status': 'created'}
        await db.purchase_orders.insert_one(dict(order))
        loop = asyncio.get_running_loop()
        market_payments._PRICE_CACHE.update(value=Decimal('2000'), expires=loop.time() + 60)
        first, second = await asyncio.gather(market_payments.create_quote(db, order),
                                             market_payments.create_quote(db, order))
        stored = await db.purchase_orders.find_one({'order_id': order['order_id']})
        assert first['quote_id'] == second['quote_id'] == stored['quote']['quote_id']

        old = stored['quote']
        await db.purchase_orders.update_one({'order_id': order['order_id']},
            {'$set': {'quote.expires_at': '2000-01-01T00:00:00+00:00'}})
        stale = await db.purchase_orders.find_one({'order_id': order['order_id']}, {'_id': 0})
        stale['quote']['expires_at'] = '2000-01-01T00:00:00+00:00'
        renewed_a, renewed_b = await asyncio.gather(market_payments.create_quote(db, stale),
                                                   market_payments.create_quote(db, stale))
        fresh = await db.purchase_orders.find_one({'order_id': order['order_id']})
        assert renewed_a['quote_id'] == renewed_b['quote_id'] == fresh['quote']['quote_id']
        assert fresh['quote']['quote_id'] != old['quote_id']

        await db.purchase_orders.update_one({'order_id': order['order_id']}, {'$set': {'tx_hash': '0x' + 'a' * 64}})
        with pytest.raises(RuntimeError, match='order_payment_already_submitted'):
            await market_payments.create_quote(db, fresh)
    _run(scenario())


def test_payment_verifier_checks_receipt_binding_and_confirmation(tmp_path, monkeypatch):
    async def scenario():
        db = AsyncMongoMockClient().test
        account = '0x4444444444444444444444444444444444444444'
        tx_hash = '0x' + 'b' * 64
        now = int(time.time())
        issued = datetime.fromtimestamp(now - 60, timezone.utc)
        expires = datetime.fromtimestamp(now + 120, timezone.utc)
        order = {'order_id': 'order-verify', 'account_id': account, 'status': 'submitted', 'cents': 200,
                 'quote': {'quote_id': 'q1', 'chain_id': market_payments.CHAIN_ID,
                           'recipient': market_payments.TREASURY, 'amount_wei': '12345',
                           'calldata': market_payments.marker_for('order-verify', 'q1'),
                           'issued_at': issued.isoformat(), 'expires_at': expires.isoformat()}}
        await db.purchase_orders.insert_one(dict(order))
        tx = {'hash': tx_hash, 'from': account, 'to': market_payments.TREASURY,
              'value': hex(12345), 'input': '0x' + order['quote']['calldata'],
              'blockHash': '0xblock', 'blockNumber': '0xa'}
        receipt = {'transactionHash': tx_hash, 'status': '0x1', 'blockHash': '0xblock', 'blockNumber': '0xa'}
        blocks = {'0xa': {'hash': '0xblock', 'timestamp': hex(now - 30)}, 'head': '0xb'}
        async def fake_rpc(_client, method, params):
            if method == 'eth_chainId': return hex(market_payments.CHAIN_ID)
            if method == 'eth_getTransactionByHash': return tx
            if method == 'eth_getTransactionReceipt': return receipt
            if method == 'eth_getBlockByNumber': return blocks[params[0]]
            if method == 'eth_blockNumber': return blocks['head']
            raise AssertionError(method)
        monkeypatch.setattr(market_payments, 'rpc', fake_rpc)
        result = await market_payments.verify_transaction(db, order, tx_hash, account)
        assert result['verified'] and result['confirmations'] == 2

        for field, value, error in [
            ('from', '0x5555555555555555555555555555555555555555', 'payment_sender_mismatch'),
            ('to', '0x5555555555555555555555555555555555555555', 'payment_recipient_mismatch'),
            ('value', '0x1', 'payment_amount_mismatch'),
            ('input', '0x00', 'payment_order_marker_mismatch'),
        ]:
            tx[field] = value
            with pytest.raises(ValueError, match=error):
                await market_payments.verify_transaction(db, order, tx_hash, account)
            tx[field] = {'from': account, 'to': market_payments.TREASURY, 'value': hex(12345),
                         'input': '0x' + order['quote']['calldata']}[field]

        receipt['status'] = '0x0'
        with pytest.raises(ValueError, match='payment_failed'):
            await market_payments.verify_transaction(db, order, tx_hash, account)
        receipt['status'] = '0x1'
        blocks['head'] = '0xa'
        pending = await market_payments.verify_transaction(db, order, tx_hash, account)
        assert pending['status'] == 'confirming' and pending['confirmations'] == 1
        blocks['head'] = '0xb'

        # A transaction mined before expiry remains valid even if submitted later.
        order['quote']['expires_at'] = datetime.fromtimestamp(now - 10, timezone.utc).isoformat()
        accepted_after_expiry = await market_payments.verify_transaction(db, order, tx_hash, account)
        assert accepted_after_expiry['verified']
        # A block mined after the quote deadline must be rejected.
        blocks['0xa']['timestamp'] = hex(now - 5)
        order['quote']['expires_at'] = datetime.fromtimestamp(now - 20, timezone.utc).isoformat()
        with pytest.raises(ValueError, match='quote_expired'):
            await market_payments.verify_transaction(db, order, tx_hash, account)
    _run(scenario())


def test_payment_hash_reservation_and_economy_ledger_are_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(player_accounts, 'LOCAL_STORAGE_FILE', tmp_path / 'local.json')
    async def scenario():
        db = AsyncMongoMockClient().test
        account = '0x6666666666666666666666666666666666666666'
        tx_hash = '0x' + 'c' * 64
        order = {'order_id': 'order-reserve', 'account_id': account, 'status': 'awaiting_payment',
                 'quote': {'quote_id': 'q-reserve', 'chain_id': market_payments.CHAIN_ID}}
        await db.purchase_orders.insert_one(dict(order))
        reserved = await market_payments.reserve_transaction_hash(db, order, tx_hash, account)
        assert reserved['status'] == 'submitted' and reserved['tx_hash'] == tx_hash
        assert (await market_payments.reserve_transaction_hash(db, reserved, tx_hash, account))['tx_hash'] == tx_hash
        with pytest.raises(ValueError, match='order_transaction_hash_conflict'):
            await market_payments.reserve_transaction_hash(db, reserved, '0x' + 'd' * 64, account)
        with pytest.raises(ValueError, match='transaction_hash_invalid'):
            await market_payments.reserve_transaction_hash(db, order, 'fake', account)

        from economy import EconomyTransaction
        transaction = EconomyTransaction(account_id=account, gold_delta=12, action='test',
                                         source_type='test', source_id='source', request_id='ledger-1')
        first = await record_economy_ledger(db, transaction)
        second = await record_economy_ledger(db, transaction)
        assert first['transaction_id'] == second['transaction_id']
        assert await db.economy_ledger.count_documents({'request_id': 'ledger-1'}) == 1
    _run(scenario())


def test_concurrent_luck_delivery_reuses_one_persisted_draw_set(tmp_path, monkeypatch):
    monkeypatch.setattr(player_accounts, 'LOCAL_STORAGE_FILE', tmp_path / 'local.json')
    async def scenario():
        db = AsyncMongoMockClient().test
        account = '0x7777777777777777777777777777777777777777'
        await db.player_accounts.insert_one({'account_id': account})
        await db.player_progress.insert_one(player_accounts.create_initial_progress(account))
        order = await create_purchase_order(db, account, 'equipment_luck_2')
        tx_hash = '0x' + 'e' * 64
        await db.purchase_orders.update_one({'order_id': order['order_id']},
            {'$set': {'status': 'awaiting_payment', 'tx_hash': tx_hash, 'chain_id': 4663}})
        draws_one = [{'draw_index': i, 'item_id': 'fabric_t1', 'is_calibration': False, 'quantity': 1} for i in range(1, 6)]
        draws_two = [{'draw_index': i, 'item_id': 'fabric_t2', 'is_calibration': False, 'quantity': 1} for i in range(1, 6)]
        candidates = iter([draws_one, draws_two])
        monkeypatch.setattr('offgame_market.roll_luck_box_draws', lambda _count: next(candidates))
        verified = {'verified': True, 'status': 'paid', 'account_id': account, 'chain_id': 4663}
        results = await asyncio.gather(
            finalize_order_fulfillment(db, order['order_id'], tx_hash, verified_payment=verified),
            finalize_order_fulfillment(db, order['order_id'], tx_hash, verified_payment=verified),
            return_exceptions=True)
        # A CAS loser may require the documented idempotent retry; it cannot
        # persist a second set of draws or award from it.
        if any(isinstance(result, Exception) for result in results):
            await finalize_order_fulfillment(db, order['order_id'], tx_hash, verified_payment=verified)
        stored = await db.purchase_orders.find_one({'order_id': order['order_id']}, {'_id': 0})
        progress = await player_accounts.get_player_progress(db, account)
        assert stored['status'] == 'fulfilled' and len(stored['box_results']) == 5
        assert progress['gold'] == 1150
        awarded_t1 = progress['equipment_parts'].get('fabric_t1', 0)
        awarded_t2 = progress['equipment_parts'].get('fabric_t2', 0)
        assert (awarded_t1, awarded_t2) in ((5, 0), (0, 5))
        assert stored['box_results'][0]['item_id'] in ('fabric_t1', 'fabric_t2')
    _run(scenario())


def test_delivery_claim_partial_and_bag_full_keep_pending_remainder_durable(tmp_path, monkeypatch):
    monkeypatch.setattr(player_accounts, 'LOCAL_STORAGE_FILE', tmp_path / 'local.json')
    async def scenario():
        db = AsyncMongoMockClient().test
        account = '0x8888888888888888888888888888888888888888'
        await db.player_accounts.insert_one({'account_id': account})
        progress = player_accounts.create_initial_progress(account)
        progress['heal_items'] = {'medkit': 1, 'faid': 2}
        await db.player_progress.insert_one(progress)
        await db.delivery_inbox.insert_one({'entitlement_id': 'delivery-1', 'account_id': account,
                                            'items': {'medkit': 2}, 'status': 'pending', 'claim_version': 0})
        partial = await claim_delivery_item(db, account, 'delivery-1', 'claim-1')
        assert partial['success'] and partial['claimed_items'] == {'medkit': 2}
        assert partial['remaining_items'] == {} and partial['entitlement_status'] == 'claimed'
        replay = await claim_delivery_item(db, account, 'delivery-1', 'claim-1')
        assert replay['success'] is False
        final = await player_accounts.get_player_progress(db, account)
        assert final['heal_items']['medkit'] == 3

        # A completely full bag returns explicit BAG_FULL without changing or
        # hiding the durable entitlement.
        await db.delivery_inbox.insert_one({'entitlement_id': 'delivery-2', 'account_id': account,
                                            'items': {'medkit': 1}, 'status': 'pending', 'claim_version': 0})
        full = await claim_delivery_item(db, account, 'delivery-2', 'claim-2')
        assert full['success'] is False and full['error_code'] == 'BAG_FULL'
        assert full['remaining_items'] == {'medkit': 1}
        still_pending = await db.delivery_inbox.find_one({'entitlement_id': 'delivery-2'})
        assert still_pending['status'] == 'pending' and still_pending['items'] == {'medkit': 1}
    _run(scenario())

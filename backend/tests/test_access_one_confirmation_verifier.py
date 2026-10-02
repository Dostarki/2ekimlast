"""Modules/features: verifier confirmation thresholds (access=1 vs shared default=2)."""

import asyncio
import os
import sys
import time
from datetime import datetime, timezone

from mongomock_motor import AsyncMongoMockClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import market_payments


def _run(coro):
    return asyncio.run(coro)


def _order_fixture(account: str, now: int):
    issued = datetime.fromtimestamp(now - 60, timezone.utc)
    expires = datetime.fromtimestamp(now + 120, timezone.utc)
    return {
        'order_id': 'order-access-threshold',
        'account_id': account,
        'status': 'submitted',
        'kind': 'access',
        'quote': {
            'quote_id': 'q-access-threshold',
            'chain_id': market_payments.CHAIN_ID,
            'recipient': market_payments.TREASURY,
            'amount_wei': '12345',
            'issued_at': issued.isoformat(),
            'expires_at': expires.isoformat(),
            'payment_mode': 'native_transfer',
        },
        'submitted_at': datetime.fromtimestamp(now - 20, timezone.utc).isoformat(),
        'submitted_quote_id': 'q-access-threshold',
    }


def test_shared_verifier_default_two_confirmations_returns_confirming(monkeypatch):
    async def scenario():
        db = AsyncMongoMockClient().test
        account = '0x9444444444444444444444444444444444444444'
        tx_hash = '0x' + '9' * 64
        now = int(time.time())
        order = _order_fixture(account, now)
        await db.purchase_orders.insert_one(dict(order))

        tx = {
            'hash': tx_hash,
            'from': account,
            'to': market_payments.TREASURY,
            'value': hex(12345),
            'input': '0x',
            'blockHash': '0xblock',
            'blockNumber': '0xa',
        }
        receipt = {
            'transactionHash': tx_hash,
            'status': '0x1',
            'blockHash': '0xblock',
            'blockNumber': '0xa',
        }
        blocks = {'0xa': {'hash': '0xblock', 'timestamp': hex(now - 10)}, 'head': '0xa'}

        async def fake_rpc(_client, method, params):
            if method == 'eth_chainId':
                return hex(market_payments.CHAIN_ID)
            if method == 'eth_getTransactionByHash':
                return tx
            if method == 'eth_getTransactionReceipt':
                return receipt
            if method == 'eth_getBlockByNumber':
                return blocks[params[0]]
            if method == 'eth_blockNumber':
                return blocks['head']
            raise AssertionError(method)

        monkeypatch.setattr(market_payments, 'rpc', fake_rpc)
        result = await market_payments.verify_transaction(db, order, tx_hash, account)
        assert result['verified'] is False
        assert result['status'] == 'confirming'
        assert result['confirmations'] == 1

    _run(scenario())


def test_shared_verifier_accepts_one_confirmation_when_requested(monkeypatch):
    async def scenario():
        db = AsyncMongoMockClient().test
        account = '0x9555555555555555555555555555555555555555'
        tx_hash = '0x' + '8' * 64
        now = int(time.time())
        order = _order_fixture(account, now)
        await db.purchase_orders.insert_one(dict(order))

        tx = {
            'hash': tx_hash,
            'from': account,
            'to': market_payments.TREASURY,
            'value': hex(12345),
            'input': '0x',
            'blockHash': '0xblock',
            'blockNumber': '0xa',
        }
        receipt = {
            'transactionHash': tx_hash,
            'status': '0x1',
            'blockHash': '0xblock',
            'blockNumber': '0xa',
        }
        blocks = {'0xa': {'hash': '0xblock', 'timestamp': hex(now - 10)}, 'head': '0xa'}

        async def fake_rpc(_client, method, params):
            if method == 'eth_chainId':
                return hex(market_payments.CHAIN_ID)
            if method == 'eth_getTransactionByHash':
                return tx
            if method == 'eth_getTransactionReceipt':
                return receipt
            if method == 'eth_getBlockByNumber':
                return blocks[params[0]]
            if method == 'eth_blockNumber':
                return blocks['head']
            raise AssertionError(method)

        monkeypatch.setattr(market_payments, 'rpc', fake_rpc)
        result = await market_payments.verify_transaction(
            db,
            order,
            tx_hash,
            account,
            required_confirmations=1,
        )
        assert result['verified'] is True
        assert result['status'] == 'paid'
        assert result['confirmations'] == 1

    _run(scenario())

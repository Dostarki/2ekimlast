"""Network guard regression tests for market payment verification."""

import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import market_payments


# Modules/features covered: market_payments.verify_transaction Robinhood-mainnet-only guard.
def _run(coro):
    return asyncio.run(coro)


def test_verify_transaction_rejects_wrong_quote_chain_before_rpc():
    async def scenario():
        account = '0x1111111111111111111111111111111111111111'
        order = {
            'order_id': 'order-wrong-chain',
            'account_id': account,
            'status': 'awaiting_payment',
            'quote': {
                'quote_id': 'q1',
                'chain_id': 1,
                'recipient': market_payments.TREASURY,
                'amount_wei': '1',
                'calldata': '00',
                'issued_at': '2099-01-01T00:00:00+00:00',
                'expires_at': '2099-01-01T00:05:00+00:00',
            },
        }
        tx_hash = '0x' + 'a' * 64
        with pytest.raises(ValueError, match='payment_quote_wrong_chain'):
            await market_payments.verify_transaction(None, order, tx_hash, account)

    _run(scenario())

"""Server owned Robinhood Chain native ETH checkout quotes and verification."""
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_CEILING
import uuid
import httpx
import re
import asyncio
import os
from eth_utils import to_checksum_address
from chain_config import CHAIN_ID, RPC_URL

PRICE_URL = os.environ['COINBASE_SPOT_URL']
TREASURY = to_checksum_address(os.environ['TREASURY_ADDRESS'])
CONFIRMATIONS = 2
QUOTE_TTL_SECONDS = 180
_PRICE_CACHE = {'value': None, 'expires': 0.0}
_PRICE_LOCK = asyncio.Lock()
_QUOTE_LOCKS = {}


def marker_for(order_id: str, quote_id: str) -> str:
    return f'LastZHood:{order_id}:{quote_id}'.encode().hex()


async def create_quote(db, order: dict) -> dict:
    lock = _QUOTE_LOCKS.setdefault(order['order_id'], asyncio.Lock())
    async with lock:
        fresh = await db.purchase_orders.find_one(
            {'order_id': order['order_id'], 'account_id': order['account_id']}, {'_id': 0})
        if not fresh:
            raise RuntimeError('order_not_found')
        return await _create_quote_unlocked(db, fresh)


async def _create_quote_unlocked(db, order: dict) -> dict:
    if order.get('tx_hash'):
        raise RuntimeError('order_payment_already_submitted')
    if order.get('quote') and order.get('status') in ('submitted', 'confirming'):
        return order['quote']
    prior_quote = order.get('quote')
    if prior_quote and order.get('status') == 'awaiting_payment':
        expires = datetime.fromisoformat(order['quote']['expires_at'])
        if (expires > datetime.now(timezone.utc) and prior_quote.get('payment_mode') == 'native_transfer'
                and prior_quote.get('recipient', '').lower() == TREASURY.lower()):
            return order['quote']
        expired = await db.purchase_orders.update_one(
            {'order_id': order['order_id'], 'account_id': order['account_id'], 'status': 'awaiting_payment',
             'quote.quote_id': prior_quote.get('quote_id'), 'tx_hash': {'$exists': False}},
            {'$set': {'status': 'created'}},
        )
        if expired.matched_count != 1:
            latest = await db.purchase_orders.find_one(
                {'order_id': order['order_id'], 'account_id': order['account_id']}, {'_id': 0})
            latest_quote = (latest or {}).get('quote') or {}
            if (latest and not latest.get('tx_hash') and latest.get('status') == 'awaiting_payment'
                    and latest_quote.get('payment_mode') == 'native_transfer' and latest_quote.get('expires_at')
                    and datetime.fromisoformat(latest_quote['expires_at']) > datetime.now(timezone.utc)):
                return latest_quote
            if latest and not latest.get('tx_hash') and latest.get('status') == 'created':
                return await _create_quote_unlocked(db, latest)
            raise RuntimeError('order_state_conflict')
        order = {**order, 'status': 'created'}
    if order.get('status') != 'created':
        raise RuntimeError('order_not_payable')
    async with _PRICE_LOCK:
        now_mono = asyncio.get_running_loop().time()
        if _PRICE_CACHE['value'] is not None and now_mono < _PRICE_CACHE['expires']:
            usd_per_eth = _PRICE_CACHE['value']
        else:
            async with httpx.AsyncClient(timeout=8) as client:
                response = await client.get(PRICE_URL)
                response.raise_for_status()
                price_data = response.json()['data']
                if price_data.get('currency') != 'USD' or price_data.get('base') != 'ETH':
                    raise RuntimeError('price_currency_invalid')
                usd_per_eth = Decimal(price_data['amount'])
            if not usd_per_eth.is_finite() or not Decimal(100) <= usd_per_eth <= Decimal(1_000_000):
                raise RuntimeError('price_unavailable')
            _PRICE_CACHE.update(value=usd_per_eth, expires=now_mono + 30)
    if not usd_per_eth.is_finite() or not Decimal(100) <= usd_per_eth <= Decimal(1_000_000):
        raise RuntimeError('price_unavailable')
    amount_eth = (Decimal(order['cents']) / Decimal(100)) / usd_per_eth
    wei = int((amount_eth * Decimal(10**18)).to_integral_value(rounding=ROUND_CEILING))
    now = datetime.now(timezone.utc)
    quote = {
        'quote_id': str(uuid.uuid4()), 'chain_id': CHAIN_ID,
        'recipient': TREASURY, 'usd_per_eth': str(usd_per_eth),
        'amount_wei': str(wei), 'issued_at': now.isoformat(),
        'expires_at': (now + timedelta(seconds=QUOTE_TTL_SECONDS)).isoformat(),
        'payment_mode': 'native_transfer',
    }
    old_quote_id = (prior_quote or {}).get('quote_id')
    cas_filter = {
        'order_id': order['order_id'], 'account_id': order['account_id'],
        'status': 'created', 'tx_hash': {'$exists': False},
    }
    cas_filter['quote.quote_id'] = old_quote_id if old_quote_id else {'$exists': False}
    updates = {'$set': {'quote': quote, 'status': 'awaiting_payment'}}
    if prior_quote:
        updates['$push'] = {'quote_history': prior_quote}
    result = await db.purchase_orders.update_one(cas_filter, updates)
    if result.matched_count != 1:
        winner = await db.purchase_orders.find_one(
            {'order_id': order['order_id'], 'account_id': order['account_id']}, {'_id': 0})
        winner_quote = (winner or {}).get('quote') or {}
        if (winner and not winner.get('tx_hash') and winner.get('status') == 'awaiting_payment'
                and winner_quote.get('payment_mode') == 'native_transfer' and winner_quote.get('expires_at')
                and datetime.fromisoformat(winner_quote['expires_at']) > datetime.now(timezone.utc)):
            return winner_quote
        if winner and not winner.get('tx_hash') and winner.get('status') == 'created':
            return await _create_quote_unlocked(db, winner)
        raise RuntimeError('order_state_conflict')
    return quote


async def rpc(client, method, params):
    response = await client.post(RPC_URL, json={'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params})
    response.raise_for_status()
    body = response.json()
    if body.get('error') or 'result' not in body:
        raise RuntimeError('chain_rpc_unavailable')
    return body['result']


async def reserve_transaction_hash(db, order: dict, tx_hash: str, authenticated_account: str) -> dict:
    """Bind one well-formed hash to its authenticated owner/order before RPC IO."""
    if not re.fullmatch(r'0x[0-9a-fA-F]{64}', tx_hash or ''):
        raise ValueError('transaction_hash_invalid')
    owner = authenticated_account.lower()
    if order.get('account_id', '').lower() != owner:
        raise PermissionError('order_owner_mismatch')
    tx_hash = tx_hash.lower()
    bound = order.get('tx_hash')
    if bound:
        if bound.lower() != tx_hash:
            raise ValueError('order_transaction_hash_conflict')
        return order
    if order.get('status') not in ('awaiting_payment', 'submitted', 'confirming') or not order.get('quote', {}).get('quote_id'):
        raise ValueError('order_not_payable')
    duplicate = await db.purchase_orders.find_one({'chain_id': CHAIN_ID, 'tx_hash': tx_hash,
                                                    'order_id': {'$ne': order['order_id']}}, {'_id': 0})
    if duplicate:
        raise ValueError('transaction_already_used')
    result = await db.purchase_orders.update_one(
        {'order_id': order['order_id'], 'account_id': owner,
         'status': {'$in': ['awaiting_payment', 'submitted', 'confirming']},
         'quote.quote_id': order['quote']['quote_id'], 'tx_hash': {'$exists': False}},
        {'$set': {'status': 'submitted', 'tx_hash': tx_hash, 'chain_id': CHAIN_ID,
                  'submitted_at': datetime.now(timezone.utc).isoformat(), 'submitted_quote_id': order['quote']['quote_id']}},
    )
    if result.matched_count != 1:
        latest = await db.purchase_orders.find_one(
            {'order_id': order['order_id'], 'account_id': owner}, {'_id': 0})
        if latest and latest.get('tx_hash', '').lower() == tx_hash:
            return latest
        if latest and latest.get('tx_hash'):
            raise ValueError('order_transaction_hash_conflict')
        raise RuntimeError('order_state_conflict')
    latest = await db.purchase_orders.find_one({'order_id': order['order_id'], 'account_id': owner}, {'_id': 0})
    if not latest:
        raise RuntimeError('order_storage_unavailable')
    return latest


async def verify_transaction(db, order: dict, tx_hash: str, authenticated_account: str, *, required_confirmations: int = CONFIRMATIONS):
    if type(required_confirmations) is not int or required_confirmations < 1:
        raise ValueError('invalid_confirmation_requirement')
    quote = order.get('quote') or {}
    if quote.get('chain_id') != CHAIN_ID:
        raise ValueError('payment_quote_wrong_chain')
    if not re.fullmatch(r'0x[0-9a-fA-F]{64}', tx_hash or ''):
        raise ValueError('transaction_hash_invalid')
    if not quote or order.get('status') not in ('awaiting_payment', 'submitted', 'confirming'):
        raise ValueError('order_not_payable')
    if order['account_id'].lower() != authenticated_account.lower():
        raise PermissionError('order_owner_mismatch')
    if order.get('tx_hash') and order['tx_hash'].lower() != tx_hash.lower():
        raise ValueError('order_transaction_hash_conflict')
    async with httpx.AsyncClient(timeout=8) as client:
        if int(await rpc(client, 'eth_chainId', []), 16) != CHAIN_ID:
            raise RuntimeError('wrong_chain')
        tx = await rpc(client, 'eth_getTransactionByHash', [tx_hash])
        receipt = await rpc(client, 'eth_getTransactionReceipt', [tx_hash])
        if tx is None or receipt is None:
            return {'status': 'submitted', 'verified': False}
        if tx.get('hash', '').lower() != tx_hash.lower() or receipt.get('transactionHash', '').lower() != tx_hash.lower():
            raise ValueError('transaction_hash_mismatch')
        if tx.get('from', '').lower() != authenticated_account.lower():
            raise ValueError('payment_sender_mismatch')
        if int(receipt.get('status', '0x0'), 16) != 1:
            raise ValueError('payment_failed')
        block = await rpc(client, 'eth_getBlockByNumber', [receipt['blockNumber'], False])
        head = await rpc(client, 'eth_blockNumber', [])
        if not block or block.get('hash') != receipt.get('blockHash') or tx.get('blockHash') != receipt.get('blockHash') or tx.get('blockNumber') != receipt.get('blockNumber'):
            raise ValueError('payment_block_mismatch')
        tx_time = datetime.fromtimestamp(int(block['timestamp'], 16), timezone.utc)
        payload = (tx.get('input') or tx.get('data') or '0x').lower()
        def input_matches(q):
            if q.get('payment_mode') == 'native_transfer':
                return payload in ('', '0x')
            return bool(q.get('calldata')) and payload == ('0x' + q['calldata']).lower()
        def time_matches(q):
            issued_at, expires_at = datetime.fromisoformat(q['issued_at']), datetime.fromisoformat(q['expires_at'])
            submitted_at = datetime.fromisoformat(order['submitted_at']) if order.get('submitted_at') else None
            timely_submission = (submitted_at is not None and issued_at <= submitted_at <= expires_at
                                 and order.get('submitted_quote_id') == q.get('quote_id'))
            return tx_time.timestamp() >= int(issued_at.timestamp()) - 15 and (tx_time <= expires_at or timely_submission)
        # A refresh must not discard a valid earlier quote that was already paid.
        quotes = [quote, *(order.get('quote_history') or [])]
        matching = next((q for q in quotes if q.get('chain_id') == CHAIN_ID and input_matches(q)
                         and tx.get('to', '').lower() == q['recipient'].lower()
                         and int(tx.get('value', '0x0'), 16) == int(q['amount_wei']) and time_matches(q)), None)
        if matching:
            quote = matching
        if quote.get('chain_id') != CHAIN_ID:
            raise ValueError('payment_quote_wrong_chain')
        if tx.get('to', '').lower() != quote['recipient'].lower():
            raise ValueError('payment_recipient_mismatch')
        if int(tx.get('value', '0x0'), 16) != int(quote['amount_wei']):
            raise ValueError('payment_amount_mismatch')
        if not input_matches(quote):
            raise ValueError('payment_order_marker_mismatch')
        if not time_matches(quote):
            raise ValueError('quote_expired')
        confirmations = int(head, 16) - int(receipt['blockNumber'], 16) + 1
        if confirmations < required_confirmations:
            return {'status': 'confirming', 'verified': False, 'confirmations': confirmations}
    duplicate = await db.purchase_orders.find_one({'chain_id': CHAIN_ID, 'tx_hash': tx_hash.lower(), 'order_id': {'$ne': order['order_id']}}, {'_id': 0})
    if duplicate:
        raise ValueError('transaction_already_used')
    return {'status': 'paid', 'verified': True, 'tx_hash': tx_hash.lower(), 'confirmations': confirmations,
            'account_id': authenticated_account.lower(), 'chain_id': CHAIN_ID, 'quote_id': quote['quote_id']}

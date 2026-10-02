"""DEADZONE - Robinhood Chain EVM Authentication & SIWE (EIP-4361)

Handles nonce generation, EIP-191 signature recovery, SIWE verification,
and secure HTTP session management for EVM wallets.
"""

from datetime import datetime, timezone, timedelta
import logging
import os
import re
import secrets
from typing import Dict, Any, Optional
from urllib.parse import urlsplit
from eth_account import Account
from eth_account.messages import encode_defunct
from chain_config import CHAIN_ID
from access_payments import has_paid_access, has_fee_exemption

from player_accounts import to_checksum_address, get_account_by_address, get_player_progress, create_or_update_profile, sync_db_to_file

log = logging.getLogger('deadzone.auth')

STATEMENT = "Sign in to DEADZONE Westfall with your Robinhood Chain wallet."
SUPPORTED_CHAINS = {CHAIN_ID}


async def create_challenge(db, address: str, chain_id: int = CHAIN_ID, domain: Optional[str] = None, uri: Optional[str] = None) -> Dict[str, Any]:
    """Generates an atomic, single-use SIWE challenge nonce."""
    if chain_id not in SUPPORTED_CHAINS:
        raise ValueError('Only Robinhood Chain Mainnet (4663) is supported.')
    allowed_origins = {origin.strip().rstrip('/') for origin in os.environ['CORS_ORIGINS'].split(',')}
    if not uri or uri.rstrip('/') not in allowed_origins or not domain or urlsplit(uri).netloc != domain:
        raise ValueError('Sign-in domain and URI must match an allowed application origin.')
    acc_id = address.lower()
    checksum_addr = to_checksum_address(acc_id)
    nonce = secrets.token_hex(16)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=5)

    challenge_doc = {
        'nonce': nonce,
        'account_id': acc_id,
        'address': checksum_addr,
        'chain_id': chain_id,
        'domain': domain,
        'uri': uri,
        'issued_at': now.isoformat(),
        'expires_at': expires.isoformat(),
        'consumed': False,
    }

    eff_domain = domain
    eff_uri = uri

    siwe_text = (
        f"{eff_domain} wants you to sign in with your Ethereum account:\n"
        f"{checksum_addr}\n\n"
        f"{STATEMENT}\n\n"
        f"URI: {eff_uri}\n"
        f"Version: 1\n"
        f"Chain ID: {chain_id}\n"
        f"Nonce: {nonce}\n"
        f"Issued At: {now.isoformat()}"
    )


    challenge_doc['message'] = siwe_text
    await db.auth_challenges.insert_one(challenge_doc)

    return {

        'nonce': nonce,
        'issuedAt': now.isoformat(),
        'address': checksum_addr,
        'statement': STATEMENT,
        'message': siwe_text,
    }



def parse_siwe_message(message: str) -> Dict[str, Any]:
    """Extracts essential EIP-4361 fields from the signed SIWE message text."""
    addr_match = re.search(r'(0x[a-fA-F0-9]{40})', message)
    nonce_match = re.search(r'Nonce:\s*([a-zA-Z0-9]+)', message)
    chain_match = re.search(r'Chain ID:\s*([0-9]+)', message)
    uri_match = re.search(r'URI:\s*([^\n\r]+)', message)

    if not addr_match or not nonce_match or not chain_match:
        raise ValueError('Invalid SIWE message structure: missing address, nonce, or chain ID.')

    return {
        'address': addr_match.group(1),
        'nonce': nonce_match.group(1),
        'chainId': int(chain_match.group(1)),
        'uri': uri_match.group(1) if uri_match else ''
    }


async def verify_signature(db, message: str, signature: str) -> Dict[str, Any]:
    """Verifies SIWE EIP-191 personal sign recovery and challenge validity."""
    parsed = parse_siwe_message(message)
    claimed_address = parsed['address'].lower()
    nonce = parsed['nonce']
    chain_id = parsed['chainId']
    if chain_id not in SUPPORTED_CHAINS:
        raise ValueError('Only Robinhood Chain Mainnet (4663) is supported.')

    # 1. Cryptographic address recovery
    try:
        encoded = encode_defunct(text=message)
        recovered_addr = Account.recover_message(encoded, signature=signature).lower()
    except Exception as e:
        log.warning(f'Signature recovery failed: {e}')
        raise ValueError('Invalid cryptographic signature.')

    if recovered_addr != claimed_address:
        log.warning(f'Address mismatch: claimed {claimed_address} vs recovered {recovered_addr}')
        raise ValueError('Recovered address does not match claimed address.')

    # 2. Challenge validation and atomic consumption
    challenge = await db.auth_challenges.find_one({'nonce': nonce}, {'_id': 0})
    if not challenge:
        raise ValueError('Challenge nonce not found.')
    if challenge.get('chain_id') != CHAIN_ID or challenge.get('message') != message:
        raise ValueError('Signed message does not match the mainnet challenge. Request a new challenge.')

    if challenge.get('account_id') and challenge['account_id'] != claimed_address:
        log.warning(f"Nonce account mismatch: expected {challenge.get('account_id')} vs {claimed_address}")
        raise ValueError('Challenge nonce invalid for this address.')


    if challenge.get('consumed', False):
        raise ValueError('Challenge nonce has already been consumed.')

    # Check expiration
    expires_at = datetime.fromisoformat(challenge['expires_at'].replace('Z', '+00:00'))
    if datetime.now(timezone.utc) > expires_at:
        raise ValueError('Challenge nonce has expired. Please sign in again.')

    # Atomically consume nonce to prevent replay
    consumed = await db.auth_challenges.update_one(
        {'nonce': nonce, 'consumed': False, 'chain_id': CHAIN_ID}, {'$set': {'consumed': True}})
    if consumed.modified_count != 1:
        raise ValueError('Challenge nonce has already been consumed.')

    # 3. Create persistent authenticated session
    session_token = secrets.token_urlsafe(36)
    now = datetime.now(timezone.utc)
    session_expires = now + timedelta(days=7)
    checksum_addr = to_checksum_address(claimed_address)

    session_doc = {
        'session_token': session_token,
        'account_id': claimed_address,
        'address': checksum_addr,
        'chain_id': chain_id,
        'created_at': now.isoformat(),
        'expires_at': session_expires.isoformat(),
    }
    await db.auth_sessions.insert_one(session_doc)
    await sync_db_to_file(db)

    # 4. Check if profile exists; if not, create initial survivor profile
    account = await get_account_by_address(db, claimed_address)
    new_account = account is None
    if not account:
        default_nick = f"Survivor_{claimed_address[-4:].upper()}"
        account = await create_or_update_profile(db, claimed_address, default_nick, 'soldier')
    progress = await get_player_progress(db, claimed_address)

    return {
        'authenticated': True,
        'token': session_token,
        'sessionToken': session_token,
        'address': checksum_addr,
        'hasProfile': True,
        'new_account': new_account,
        'paid_access': await has_paid_access(db, claimed_address),
        'fee_exempt': await has_fee_exemption(db, claimed_address),
        'account': account,
        'progress': progress,
    }



async def get_session_account(db, session_token: str) -> Optional[Dict[str, Any]]:
    """Validates session token and returns authenticated player account."""
    if not session_token:
        return None
    session = await db.auth_sessions.find_one({'session_token': session_token, 'chain_id': CHAIN_ID}, {'_id': 0})
    if not session:
        return None

    # Check expiry
    expires_at = datetime.fromisoformat(session['expires_at'].replace('Z', '+00:00'))
    if datetime.now(timezone.utc) > expires_at:
        await db.auth_sessions.delete_one({'session_token': session_token})
        await sync_db_to_file(db)
        return None

    account = await get_account_by_address(db, session['account_id'])
    progress = await get_player_progress(db, session['account_id'])
    return {
        'session': session,
        'account': account,
        'progress': progress,
        'address': session['address'],
        'account_id': session['account_id'],
        'paid_access': await has_paid_access(db, session['account_id']),
        'fee_exempt': await has_fee_exemption(db, session['account_id']),
    }


async def logout(db, session_token: str):
    if session_token:
        await db.auth_sessions.delete_one({'session_token': session_token})
        await sync_db_to_file(db)

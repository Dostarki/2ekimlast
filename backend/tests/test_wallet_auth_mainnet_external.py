"""Wallet auth + mainnet gate regression tests against external preview backend."""

import os
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

import pytest
import requests
from dotenv import load_dotenv
from eth_account import Account
from eth_account.messages import encode_defunct
from motor.motor_asyncio import AsyncIOMotorClient


load_dotenv(Path(__file__).resolve().parents[1] / '.env')


# Modules/features covered: /api/auth/challenge, /api/auth/verify, /api/auth/me mainnet + origin validation.
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    raise RuntimeError("REACT_APP_BACKEND_URL is required for external auth tests")
BASE_URL = BASE_URL.rstrip("/")
API_BASE = f"{BASE_URL}/api"
MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")


def _origin_parts():
    parsed = urlparse(BASE_URL)
    return parsed.netloc, f"{parsed.scheme}://{parsed.netloc}"


def _new_wallet(tracked_addresses: set[str]):
    acct = Account.create()
    tracked_addresses.add(acct.address.lower())
    return acct, acct.address


def _challenge_payload(address: str):
    domain, uri = _origin_parts()
    return {"address": address, "chain_id": 4663, "domain": domain, "uri": uri}


async def _cleanup_test_wallet_records(addresses: set[str]):
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
    finally:
        client.close()


async def _force_expire_nonce(nonce: str):
    if not (MONGO_URL and DB_NAME):
        pytest.skip('MONGO_URL/DB_NAME missing; cannot run nonce-expiry mutation test.')
    client = AsyncIOMotorClient(MONGO_URL)
    try:
        db = client[DB_NAME]
        expired = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        result = await db.auth_challenges.update_one({'nonce': nonce}, {'$set': {'expires_at': expired}})
        if result.matched_count != 1:
            pytest.skip('Nonce document not accessible for expiry mutation check.')
    finally:
        client.close()


@pytest.fixture(scope='class')
def tracked_addresses():
    addresses: set[str] = set()
    yield addresses
    import asyncio
    asyncio.run(_cleanup_test_wallet_records(addresses))


class TestWalletAuthMainnetExternal:
    def test_challenge_accepts_valid_mainnet_request(self, tracked_addresses):
        _, address = _new_wallet(tracked_addresses)
        response = requests.post(f"{API_BASE}/auth/challenge", json=_challenge_payload(address), timeout=20)
        assert response.status_code == 200
        data = response.json()
        assert data["address"].lower() == address.lower()
        assert "Nonce:" in data["message"]
        assert "Chain ID: 4663" in data["message"]

    @pytest.mark.parametrize("bad_chain", [1, 46630, 0])
    def test_challenge_rejects_non_mainnet_chain_ids(self, bad_chain, tracked_addresses):
        _, address = _new_wallet(tracked_addresses)
        payload = _challenge_payload(address)
        payload["chain_id"] = bad_chain
        response = requests.post(f"{API_BASE}/auth/challenge", json=payload, timeout=20)
        assert response.status_code == 400
        detail = response.json().get("detail", "")
        assert "4663" in detail

    def test_challenge_rejects_null_chain_id(self, tracked_addresses):
        _, address = _new_wallet(tracked_addresses)
        payload = _challenge_payload(address)
        payload["chain_id"] = None
        response = requests.post(f"{API_BASE}/auth/challenge", json=payload, timeout=20)
        assert response.status_code == 422

    def test_challenge_rejects_wrong_origin(self, tracked_addresses):
        _, address = _new_wallet(tracked_addresses)
        payload = _challenge_payload(address)
        payload["domain"] = "evil.example"
        payload["uri"] = "https://evil.example"
        response = requests.post(f"{API_BASE}/auth/challenge", json=payload, timeout=20)
        assert response.status_code == 400
        assert "allowed application origin" in response.json().get("detail", "")

    def test_verify_and_me_work_with_real_signature(self, tracked_addresses):
        account, address = _new_wallet(tracked_addresses)
        challenge = requests.post(f"{API_BASE}/auth/challenge", json=_challenge_payload(address), timeout=20)
        assert challenge.status_code == 200
        message = challenge.json()["message"]

        signature = Account.sign_message(encode_defunct(text=message), private_key=account.key).signature.hex()
        session = requests.Session()
        verify = session.post(
            f"{API_BASE}/auth/verify", json={"message": message, "signature": signature}, timeout=20
        )
        assert verify.status_code == 200
        verify_data = verify.json()
        assert verify_data["authenticated"] is True
        assert verify_data["account"]["address"].lower() == address.lower()
        assert isinstance(verify_data.get("token"), str) and len(verify_data["token"]) > 10

        me = session.get(f"{API_BASE}/auth/me", timeout=20)
        assert me.status_code == 200
        me_data = me.json()
        assert me_data["authenticated"] is True
        assert me_data["account"]["address"].lower() == address.lower()

    def test_verify_rejects_tampered_message(self, tracked_addresses):
        account, address = _new_wallet(tracked_addresses)
        challenge = requests.post(f"{API_BASE}/auth/challenge", json=_challenge_payload(address), timeout=20)
        assert challenge.status_code == 200
        message = challenge.json()["message"]
        signature = Account.sign_message(encode_defunct(text=message), private_key=account.key).signature.hex()

        tampered = message.replace("Chain ID: 4663", "Chain ID: 1")
        verify = requests.post(
            f"{API_BASE}/auth/verify", json={"message": tampered, "signature": signature}, timeout=20
        )
        assert verify.status_code == 400

    def test_verify_replay_same_nonce_fails(self, tracked_addresses):
        account, address = _new_wallet(tracked_addresses)
        challenge = requests.post(f"{API_BASE}/auth/challenge", json=_challenge_payload(address), timeout=20)
        assert challenge.status_code == 200
        message = challenge.json()["message"]
        signature = Account.sign_message(encode_defunct(text=message), private_key=account.key).signature.hex()

        first = requests.post(f"{API_BASE}/auth/verify", json={"message": message, "signature": signature}, timeout=20)
        second = requests.post(f"{API_BASE}/auth/verify", json={"message": message, "signature": signature}, timeout=20)
        assert first.status_code == 200
        assert second.status_code == 400
        assert "consumed" in second.json().get("detail", "").lower()

    def test_verify_concurrent_reuse_only_one_succeeds(self, tracked_addresses):
        account, address = _new_wallet(tracked_addresses)
        challenge = requests.post(f"{API_BASE}/auth/challenge", json=_challenge_payload(address), timeout=20)
        assert challenge.status_code == 200
        message = challenge.json()["message"]
        signature = Account.sign_message(encode_defunct(text=message), private_key=account.key).signature.hex()

        def _verify_once():
            response = requests.post(
                f"{API_BASE}/auth/verify", json={"message": message, "signature": signature}, timeout=20
            )
            return response.status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(lambda _: _verify_once(), [0, 1]))
        assert statuses.count(200) == 1
        assert statuses.count(400) == 1

    def test_verify_rejects_message_with_modified_domain_uri(self, tracked_addresses):
        account, address = _new_wallet(tracked_addresses)
        challenge = requests.post(f"{API_BASE}/auth/challenge", json=_challenge_payload(address), timeout=20)
        assert challenge.status_code == 200
        message = challenge.json()["message"]
        tampered = message.replace(BASE_URL, "https://evil.example")
        signature = Account.sign_message(encode_defunct(text=tampered), private_key=account.key).signature.hex()
        verify = requests.post(
            f"{API_BASE}/auth/verify", json={"message": tampered, "signature": signature}, timeout=20
        )
        assert verify.status_code == 400
        assert "mainnet challenge" in verify.json().get("detail", "").lower()

    def test_verify_rejects_expired_nonce(self, tracked_addresses):
        import asyncio
        account, address = _new_wallet(tracked_addresses)
        challenge = requests.post(f"{API_BASE}/auth/challenge", json=_challenge_payload(address), timeout=20)
        assert challenge.status_code == 200
        data = challenge.json()
        message = data["message"]
        nonce = data["nonce"]
        asyncio.run(_force_expire_nonce(nonce))
        signature = Account.sign_message(encode_defunct(text=message), private_key=account.key).signature.hex()
        verify = requests.post(
            f"{API_BASE}/auth/verify", json={"message": message, "signature": signature}, timeout=20
        )
        assert verify.status_code == 400
        assert "expired" in verify.json().get("detail", "").lower()

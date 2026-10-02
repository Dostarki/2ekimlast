"""Iteration 11 - installation/environment smoke tests after repo migration.

Validates that migrated DEADZONE backend wires correctly behind the external
preview URL: public endpoints, SIWE challenge, join auth guard, and admin
password login (Origin via Cloudflare proxy)."""
import os
import requests
import pytest

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://emergent-build-131.preview.emergentagent.com').rstrip('/')
# The real external Origin header that reaches the backend after the Cloudflare
# proxy rewrite - matches ADMIN_PROXY_ORIGIN and the second CORS_ORIGINS entry.
PROXY_ORIGIN = 'https://emergent-build-131.cluster-12.preview.emergentcf.cloud'
PUBLIC_ORIGIN = BASE_URL


@pytest.fixture(scope='module')
def client():
    s = requests.Session()
    s.headers.update({'Content-Type': 'application/json'})
    return s


# --- Public health endpoints ---------------------------------------------------

@pytest.mark.parametrize('path', [
    '/api/',
    '/api/status',
    '/api/weapons',
    '/api/world',
    '/api/leaderboard',
    '/api/bosses',
])
def test_public_endpoint_returns_200(client, path):
    r = client.get(f'{BASE_URL}{path}', timeout=20)
    assert r.status_code == 200, r.text


def test_offgame_catalog_has_payment_mode(client):
    r = client.get(f'{BASE_URL}/api/offgame-market/catalog', timeout=20)
    assert r.status_code == 200
    data = r.json()
    caps = data.get('capabilities') or {}
    assert caps.get('payment_mode') == 'native_eth_quote'
    assert caps.get('chain_id') == 4663
    assert caps.get('treasury', '').startswith('0x')


# --- SIWE challenge ------------------------------------------------------------

def test_siwe_challenge_returns_nonce(client):
    payload = {
        'address': '0x1234567890123456789012345678901234567890',
        'domain': 'emergent-build-131.preview.emergentagent.com',
        'uri': PUBLIC_ORIGIN,
    }
    r = client.post(f'{BASE_URL}/api/auth/challenge', json=payload,
                    headers={'Origin': PUBLIC_ORIGIN}, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data.get('nonce'), str) and len(data['nonce']) >= 16
    assert 'Chain ID: 4663' in data['message']
    assert 'emergent-build-131.preview.emergentagent.com' in data['message']


def test_siwe_challenge_rejects_untrusted_uri(client):
    payload = {
        'address': '0x1234567890123456789012345678901234567890',
        'domain': 'evil.example.com',
        'uri': 'https://evil.example.com',
    }
    r = client.post(f'{BASE_URL}/api/auth/challenge', json=payload, timeout=20)
    assert r.status_code == 400


# --- Join guard ----------------------------------------------------------------

def test_join_requires_wallet_signature(client):
    r = client.post(f'{BASE_URL}/api/join', json={'nickname': 'test', 'skin': 'soldier'}, timeout=20)
    assert r.status_code == 401
    assert r.json().get('detail') == 'WALLET_SIGNATURE_REQUIRED'


# --- Admin password-only login (Origin-protected) -----------------------------

def test_admin_login_success_with_proxy_origin(client):
    r = client.post(f'{BASE_URL}/api/admin/login', json={'password': '123123'},
                    headers={'Origin': PUBLIC_ORIGIN}, timeout=20)
    assert r.status_code == 200, r.text
    assert r.json() == {'role': 'admin'}
    # Session cookies issued.
    assert any(c.name == 'admin_access' for c in r.cookies)


def test_admin_login_rejects_wrong_password(client):
    s = requests.Session()
    s.headers.update({'Content-Type': 'application/json', 'Origin': PUBLIC_ORIGIN})
    r = s.post(f'{BASE_URL}/api/admin/login', json={'password': 'wrongwrong'}, timeout=20)
    assert r.status_code in (401, 429)


def test_admin_me_after_login(client):
    s = requests.Session()
    s.headers.update({'Content-Type': 'application/json', 'Origin': PUBLIC_ORIGIN})
    login = s.post(f'{BASE_URL}/api/admin/login', json={'password': '123123'}, timeout=20)
    assert login.status_code == 200, login.text
    me = s.get(f'{BASE_URL}/api/admin/me', timeout=20)
    assert me.status_code == 200
    assert me.json() == {'role': 'admin'}

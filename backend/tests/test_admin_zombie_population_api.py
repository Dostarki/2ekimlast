"""Live admin API coverage for admin zombie_count validation/persistence."""
import os
import requests
from dotenv import load_dotenv
from pathlib import Path

load_dotenv('/app/frontend/.env')
load_dotenv('/app/backend/.env')

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')
API_BASE = f'{BASE_URL}/api'
ORIGIN = os.environ.get('ADMIN_ORIGIN')
ADMIN_PASSWORD = '123123'


def _login():
    s = requests.Session()
    s.headers.update({'Origin': ORIGIN, 'Content-Type': 'application/json'})
    r = s.post(f'{API_BASE}/admin/login', json={'password': ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, f'login failed: {r.status_code} {r.text}'
    return s


def test_admin_status_includes_zombies_field():
    s = _login()
    r = s.get(f'{API_BASE}/admin/status', timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    for k in ('humans', 'bots', 'total', 'zombies', 'tick_ms', 'participants'):
        assert k in data, f'missing {k}'
    assert isinstance(data['zombies'], int)
    assert isinstance(data['tick_ms'], (int, float))


def test_admin_settings_put_zombie_count():
    s = _login()
    # Read and restore exact current settings in finally.
    r = s.get(f'{API_BASE}/admin/settings', timeout=15)
    assert r.status_code == 200, r.text
    original = r.json()
    assert 'zombie_count' in original and 'zombie_density' in original
    try:
        for count in (0, 601, 1500, 10000):
            payload = dict(original)
            payload['zombie_count'] = count
            payload['zombie_density'] = 'off' if count == 0 else 'normal'
            update = s.put(f'{API_BASE}/admin/settings', json=payload, timeout=20)
            assert update.status_code == 200, update.text
            assert update.json()['zombie_count'] == count
            verify = s.get(f'{API_BASE}/admin/settings', timeout=20)
            assert verify.status_code == 200
            assert verify.json()['zombie_count'] == count

        for bad in (-1, 1.25, True):
            payload = dict(original)
            payload['zombie_count'] = bad
            bad_res = s.put(f'{API_BASE}/admin/settings', json=payload, timeout=15)
            assert bad_res.status_code in (400, 422), f'expected validation error, got {bad_res.status_code}'
    finally:
        restore = s.put(f'{API_BASE}/admin/settings', json=original, timeout=20)
        assert restore.status_code == 200, restore.text
        restored = s.get(f'{API_BASE}/admin/settings', timeout=20)
        assert restored.status_code == 200
        assert restored.json().get('zombie_count') == original.get('zombie_count')
        assert restored.json().get('bot_count') == original.get('bot_count')


def test_admin_login_requires_origin():
    s = requests.Session()
    s.headers.update({'Content-Type': 'application/json'})  # no Origin
    r = s.post(f'{API_BASE}/admin/login', json={'password': ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 403, f'expected 403 w/o origin, got {r.status_code}'

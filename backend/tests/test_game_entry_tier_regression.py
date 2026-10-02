"""Regression tests for tier normalization, snapshot safety, market grants and run-loop isolation."""

import asyncio
import copy
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine import Game
from equipment import execute_sell
from offgame_market import create_purchase_order, finalize_order_fulfillment, resolve_order_manifest
import player_accounts
import server
from weapon_parts import PART_TIERS, normalize_weapon_parts, weapon_parts_snapshot


def _run(coro):
    return asyncio.run(coro)


# Modules/features: weapon_parts catalogue derivation + snapshot compatibility for legacy/malformed records.
def test_weapon_parts_normalization_and_snapshot_preserve_shape_without_downgrade():
    legacy_parts = [
        {'id': 'barrel_common'},
        {'id': 'receiver_uncommon', 'tier': 1},
        {'id': 'optic_rare', 'tier': 1},
        {'id': 'mystery_part'},
        {'foo': 'bar'},
        'bad-record',
    ]

    normalized = normalize_weapon_parts(legacy_parts)
    assert len(normalized) == len(legacy_parts)
    assert normalized[0]['tier'] == 1
    assert normalized[1]['tier'] == 2
    assert normalized[2]['tier'] == 3
    assert normalized[3] == {'id': 'mystery_part'}

    snap = weapon_parts_snapshot(legacy_parts)
    by_id = {row['id']: row['tier'] for row in snap}
    assert by_id['barrel_common'] == 1
    assert by_id['receiver_uncommon'] == 2
    assert by_id['optic_rare'] == 3
    assert by_id['mystery_part'] == 0


# Modules/features: legacy sale path without explicit tier should use authoritative catalogue tier pricing.
def test_sell_legacy_weapon_parts_without_tier_uses_catalog_tier_price():
    player = {
        'gold': 10,
        'weapon_parts': [
            {'id': 'barrel_common'},
            {'id': 'barrel_uncommon', 'tier': 1},
            {'id': 'barrel_uncommon'},
        ],
    }
    ok, _msg, earned = execute_sell(player, 'weapon_parts', 'barrel_uncommon', 2)
    assert ok is True
    assert earned == 18  # tier-2 part = 9 each
    assert player['gold'] == 28
    assert [p['id'] for p in player['weapon_parts']] == ['barrel_common']


# Modules/features: game snapshot should not crash on missing tier/malformed records.
def test_game_snapshot_handles_missing_tier_and_malformed_records():
    game = Game(save_score=None)
    saved_progress = {
        'weapon_parts': [
            {'id': 'barrel_common'},
            {'id': 'receiver_uncommon', 'tier': 0},
            {'id': 'unknown_part'},
            {'foo': 'bar'},
            123,
        ]
    }
    session = {'account_id': 'acct-x', 'name': 'Tester', 'weapon': 'glock18', 'progress': saved_progress}
    player = game.add_player(session, ws=None, bot=True)
    state = game.snapshot(player, time.monotonic())
    assert state['type'] == 'state'
    parts = state['me']['weapon_parts']
    ids = [p['id'] for p in parts]
    assert 'barrel_common' in ids
    assert 'receiver_uncommon' in ids
    assert 'unknown_part' in ids
    assert all('tier' in p for p in parts)


class _DummyChannel:
    def __init__(self, fail=False):
        self.fail = fail
        self.offers = 0

    def offer(self, payload):
        if self.fail:
            raise RuntimeError('synthetic snapshot failure')
        self.offers += 1


# Modules/features: Game.run per-player snapshot failure isolation and non-spammy logging.
def test_run_loop_isolates_failing_snapshot_and_continues_stream_for_healthy_player(monkeypatch):
    game = Game(save_score=None)

    bad_channel = _DummyChannel(fail=True)
    good_channel = _DummyChannel(fail=False)
    game.players = {
        'bad': {'id': 'bad', 'bot': False, 'channel': bad_channel},
        'good': {'id': 'good', 'bot': False, 'channel': good_channel},
    }

    def fake_snapshot(player, _now, _shared=None):
        if player['id'] == 'bad':
            raise KeyError('tier')
        return {'type': 'state', 'me': {'id': 'good'}, 'events': []}

    monkeypatch.setattr(game, 'update', lambda _dt, _now: None)
    monkeypatch.setattr(game, 'shared_snapshot', lambda _now: {'bosses': [], 'leaders': []})
    monkeypatch.setattr(game, 'snapshot', fake_snapshot)

    logs = []
    monkeypatch.setattr('engine.logging.exception', lambda *args, **kwargs: logs.append(args[0]))

    async def scenario():
        task = asyncio.create_task(game.run())
        await asyncio.sleep(0.18)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    _run(scenario())
    assert good_channel.offers > 0
    assert game.players['bad'].get('_snapshot_failed') is True
    assert sum(1 for row in logs if 'Player snapshot failed' in row) == 1


# Modules/features: market pack fulfillment (offline persisted path) and idempotency for all four packs.
@pytest.mark.parametrize('sku', ['pack_field', 'pack_supply', 'pack_operator', 'pack_outpost'])
def test_market_pack_fulfillment_offline_all_four_and_idempotent(sku, tmp_path, monkeypatch):
    mongomock_motor = pytest.importorskip('mongomock_motor')
    monkeypatch.setattr(player_accounts, 'LOCAL_STORAGE_FILE', tmp_path / 'local_storage.json')

    async def scenario():
        db = mongomock_motor.AsyncMongoMockClient().test
        account = f'0x{sku[-6:]:0>40}'
        await db.player_accounts.insert_one({'account_id': account, 'nickname': f'TEST_{sku}'})
        await db.player_progress.insert_one(player_accounts.create_initial_progress(account))

        order = await create_purchase_order(db, account, sku)
        tx_hash = '0x' + ('a' * 60) + sku[-4:]
        await db.purchase_orders.update_one({'order_id': order['order_id']}, {
            '$set': {'status': 'awaiting_payment', 'tx_hash': tx_hash, 'chain_id': 4663}
        })

        verified = {'verified': True, 'status': 'paid', 'account_id': account, 'chain_id': 4663}
        first = await finalize_order_fulfillment(db, order['order_id'], tx_hash, verified_payment=verified)
        second = await finalize_order_fulfillment(db, order['order_id'], tx_hash, verified_payment=verified)
        assert first['status'] == 'fulfilled'
        assert second['status'] == 'fulfilled'

        progress = await player_accounts.get_player_progress(db, account)
        manifest = resolve_order_manifest(sku, [])
        expected_parts = sum(int(v) for v in manifest.get('weapon_parts', {}).values())
        actual_parts = progress.get('weapon_parts', [])
        assert len(actual_parts) == expected_parts
        assert all(p.get('id') in PART_TIERS and p.get('tier') == PART_TIERS[p.get('id')] for p in actual_parts)
        assert order['order_id'] in (progress.get('applied_market_order_ids') or [])

    _run(scenario())


# Modules/features: live grant path (_apply_market_manifest_to_live) all packs and idempotency.
@pytest.mark.parametrize('sku', ['pack_field', 'pack_supply', 'pack_operator', 'pack_outpost'])
def test_apply_market_manifest_to_live_all_four_and_idempotent(sku):
    order = {
        'order_id': f'order-{sku}',
        'sku': sku,
        'manifest': resolve_order_manifest(sku, []),
        'grant_plan': {'inbox_items': {}},
    }
    player = {
        'gold': 0,
        'weapon_parts': [],
        'equipment_parts': {},
        'owned_equipment': [],
        'equipment_levels': {},
        'heal_items': {},
        'consumables': {},
        'calibration': {},
        'applied_market_order_ids': [],
    }

    changed_first = server._apply_market_manifest_to_live(player, copy.deepcopy(order))
    snapshot_first = copy.deepcopy(player)
    changed_second = server._apply_market_manifest_to_live(player, copy.deepcopy(order))

    assert changed_first is True
    assert changed_second is False
    assert player == snapshot_first
    assert all(p['tier'] == PART_TIERS[p['id']] for p in player.get('weapon_parts', []))


# Modules/features: legacy progress normalization + CAS forward save with unknown record preservation.
def test_legacy_progress_load_save_cas_and_unknown_record_preserved(tmp_path, monkeypatch):
    mongomock_motor = pytest.importorskip('mongomock_motor')
    monkeypatch.setattr(player_accounts, 'LOCAL_STORAGE_FILE', tmp_path / 'local_storage.json')

    async def scenario():
        db = mongomock_motor.AsyncMongoMockClient().test
        account = '0x9999999999999999999999999999999999999999'
        await db.player_accounts.insert_one({'account_id': account, 'nickname': 'TEST_legacy'})
        await db.player_progress.insert_one({
            'account_id': account,
            'gold': 150,
            'weapon_parts': [{'id': 'barrel_common'}, {'id': 'unknown_legacy', 'meta': 1}],
        })

        loaded = await player_accounts.get_player_progress(db, account)
        assert loaded['weapon_parts'][0]['tier'] == 1
        assert loaded['weapon_parts'][1] == {'id': 'unknown_legacy', 'meta': 1}
        assert loaded.get('revision') is None

        loaded['gold'] = 151
        saved = await player_accounts.save_player_progress(db, account, loaded)
        assert saved['revision'] == 2

        stale = dict(loaded)
        stale['revision'] = 1
        with pytest.raises(RuntimeError, match='progress_revision_conflict'):
            await player_accounts.save_player_progress(db, account, stale)

    _run(scenario())

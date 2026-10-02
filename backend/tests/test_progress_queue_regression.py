"""Regression tests for queued immutable progress saves and CAS conflict safety."""

import asyncio
import copy
import os
import sys

import pytest
from mongomock_motor import AsyncMongoMockClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine import Game
import player_accounts


def _run(coro):
    return asyncio.run(coro)


# Modules/features: queued persistence chain revision advancement and immutable snapshots.
def test_persist_progress_queued_writes_advance_revision_and_keep_snapshot_immutable():
    captured_before_save = []

    async def save_progress(snapshot):
        captured_before_save.append(copy.deepcopy(snapshot))
        await asyncio.sleep(0.01)
        snapshot['revision'] = int(snapshot.get('revision', 1)) + 1

    async def scenario():
        game = Game(save_score=None, save_progress=save_progress)
        player = {
            'id': 'p-queue',
            'account_id': 'acct-queue',
            'name': 'TEST_QUEUE',
            'revision': 1,
            'gold': 100,
            'weapon_parts': [{'id': 'barrel_common', 'tier': 1}],
            'bot': False,
        }

        task1 = game.persist_progress(player)
        # Mutate live actor between queued saves: each save must use its own immutable snapshot.
        player['gold'] = 200
        task2 = game.persist_progress(player)
        player['gold'] = 300
        player['weapon_parts'].append({'id': 'optic_rare', 'tier': 3})
        task3 = game.persist_progress(player)

        await asyncio.gather(task1, task2, task3)

        # Expected queued snapshot revisions before each save call.
        assert [doc['revision'] for doc in captured_before_save] == [1, 2, 3]
        # Final live actor revision should advance to newest persisted revision.
        assert player['revision'] == 4
        # First queued snapshot must not be rewritten by later live mutations.
        assert captured_before_save[0]['gold'] == 100
        assert captured_before_save[0]['weapon_parts'] == [{'id': 'barrel_common', 'tier': 1}]

    _run(scenario())


# Modules/features: flush_progress awaits delayed tail completion during disconnect-like path.
def test_flush_progress_waits_for_delayed_save_and_updates_live_revision():
    started = asyncio.Event()
    release = asyncio.Event()

    async def save_progress(snapshot):
        started.set()
        await release.wait()
        snapshot['revision'] = int(snapshot.get('revision', 1)) + 1

    async def scenario():
        game = Game(save_score=None, save_progress=save_progress)
        player = {
            'id': 'p-disconnect',
            'account_id': 'acct-disconnect',
            'name': 'TEST_DISCONNECT',
            'revision': 1,
            'gold': 50,
            'bot': False,
        }

        pending_flush = asyncio.create_task(game.flush_progress(player))
        await started.wait()
        assert pending_flush.done() is False
        release.set()
        await pending_flush
        assert player['revision'] == 2

    _run(scenario())


# Modules/features: external concurrent revision mismatch rejects stale write and keeps rewarded data intact.
def test_external_revision_conflict_does_not_overwrite_market_reward(tmp_path, monkeypatch):
    monkeypatch.setattr(player_accounts, 'LOCAL_STORAGE_FILE', tmp_path / 'local_progress.json')

    async def scenario():
        db = AsyncMongoMockClient().test
        account_id = '0x1234000000000000000000000000000000000000'
        base = player_accounts.create_initial_progress(account_id)
        base['revision'] = 4
        base['gold'] = 1000
        base['applied_market_order_ids'] = ['order-reward-1']
        await db.player_progress.insert_one(base)

        stale_writer = {
            'account_id': account_id,
            'revision': 3,
            'gold': 10,
            'applied_market_order_ids': [],
        }
        with pytest.raises(RuntimeError, match='progress_revision_conflict'):
            await player_accounts.save_player_progress(db, account_id, stale_writer)

        persisted = await db.player_progress.find_one({'account_id': account_id}, {'_id': 0})
        assert persisted['revision'] == 4
        assert persisted['gold'] == 1000
        assert persisted['applied_market_order_ids'] == ['order-reward-1']

    _run(scenario())

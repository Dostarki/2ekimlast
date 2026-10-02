import asyncio
import contextlib
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import player_accounts
import server
from engine import Game
from enemy_damage import damage_player


class _Collection:
    def __init__(self, documents=()):
        self.docs = [dict(doc) for doc in documents]
        self.updates = []

    async def create_index(self, *_args, **_kwargs):
        return 'index'

    async def find_one(self, query, *_args, **_kwargs):
        return next((dict(doc) for doc in self.docs if all(doc.get(k) == v for k, v in query.items())), None)

    async def update_one(self, query, update, upsert=False):
        self.updates.append((query, update, upsert))
        existing = await self.find_one(query)
        if existing is None and upsert:
            existing = dict(query)
            self.docs.append(existing)
        if existing is not None:
            existing.update(update.get('$set', {}))
            for document in self.docs:
                if all(document.get(k) == v for k, v in query.items()):
                    document.update(update.get('$set', {}))
                    break


class _MongoMock:
    def __init__(self, account, progress):
        self.player_accounts = _Collection([account])
        self.player_progress = _Collection([progress] if progress else [])
        self.auth_challenges = _Collection()
        self.auth_sessions = _Collection()


def test_account_startup_seed_preserves_existing_progress(monkeypatch):
    account_id = 'test-special-account'
    existing = {'account_id': account_id, 'gold': 721, 'owned_soldiers': [{'instance_id': 'stable-id', 'tier_id': 'soldier_s3'}]}
    db = _MongoMock({'account_id': account_id, 'normalized_nickname': 'babasiken31'}, existing)

    async def _no_file_io(_db):
        return None

    monkeypatch.setattr(player_accounts, 'sync_db_from_file', _no_file_io)
    monkeypatch.setattr(player_accounts, 'sync_db_to_file', _no_file_io)
    asyncio.run(player_accounts.setup_account_indexes(db))

    assert db.player_progress.docs == [existing]
    assert db.player_progress.updates == []


def test_websocket_recruits_five_individual_soldiers_then_rejects_sixth(monkeypatch):
    # Keep the websocket test fully local: an isolated Game instance, no live
    # account/session data, and no persistent database calls.
    isolated_game = Game(None)
    monkeypatch.setattr(server, 'game', isolated_game)
    server.pending.clear()

    @contextlib.asynccontextmanager
    async def _ephemeral_lifespan(_app):
        task = asyncio.create_task(isolated_game.run())
        try:
            yield
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    monkeypatch.setattr(server.app.router, 'lifespan_context', _ephemeral_lifespan)

    def receive_until(ws, message_type):
        for _ in range(50):
            message = ws.receive_json()
            if message.get('type') == message_type:
                return message
        raise AssertionError(f'{message_type} was not sent')

    with TestClient(server.app) as client:
        joined = client.post('/api/join', json={'name': 'Roster Test', 'weapon': 'glock18', 'skin': 'soldier'})
        assert joined.status_code == 200
        with client.websocket_connect(f"/api/ws/{joined.json()['token']}") as ws:
            receive_until(ws, 'welcome')
            receive_until(ws, 'state')
            player = next(iter(isolated_game.players.values()))
            player.update(gold=12000, level=40)

            records = []
            for _ in range(5):
                ws.send_json({'type': 'soldier_buy', 'tier': 1})
                assert receive_until(ws, 'action_success')['message'] == 'S1 mercenary recruited to squad.'
                records = list(player['owned_soldiers'])
            assert len(records) == 5
            assert len({record['instance_id'] for record in records}) == 5
            assert all(record['tier_id'] == 'soldier_s1' for record in records)

            gold_before_sixth = player['gold']
            ws.send_json({'type': 'soldier_buy', 'tier': 1})
            assert 'maximum of 5' in receive_until(ws, 'action_error')['message'].lower()
            assert player['gold'] == gold_before_sixth

            second_id = records[1]['instance_id']
            runtime_before = {'hp': 33, 'ammo': 2, 'reserve': 4, 'status': 'recovering', 'recovery_until_utc': 9999999999}
            records[1]['runtime'] = dict(runtime_before)
            ws.send_json({'type': 'soldier_rename', 'instance_id': second_id, 'nickname': '  Scout Nova  '})
            assert receive_until(ws, 'action_success')['message'] == 'Mercenary name updated.'
            renamed = next(record for record in player['owned_soldiers'] if record['instance_id'] == second_id)
            assert renamed['nickname'] == 'Scout Nova' and renamed['runtime'] == runtime_before
            ws.send_json({'type': 'soldier_rename', 'instance_id': 'not-owned', 'nickname': 'Nope'})
            assert receive_until(ws, 'action_error')['message'] == 'Mercenary not found.'
            ws.send_json({'type': 'soldier_deactivate', 'instance_id': second_id})
            receive_until(ws, 'action_success')
            ws.send_json({'type': 'soldier_upgrade', 'instance_id': second_id})
            receive_until(ws, 'action_success')

            snapshot = isolated_game.snapshot(player, 1.0)['me']
            upgraded = next(record for record in snapshot['owned_soldiers'] if record['instance_id'] == second_id)
            others = [record for record in snapshot['owned_soldiers'] if record['instance_id'] != second_id]
            assert upgraded['tier_id'] == 'soldier_s2'
            assert second_id not in snapshot['active_soldier_ids']
            assert all(record['tier_id'] == 'soldier_s1' for record in others)


def test_websocket_immediate_disconnect_reconnect_keeps_soldier_recovery(monkeypatch):
    persisted = {}

    async def save(snapshot):
        persisted[snapshot['account_id']] = snapshot

    async def load(_db, account_id):
        return persisted.get(account_id, initial)

    isolated_game = Game(None, save_progress=save)
    monkeypatch.setattr(server, 'game', isolated_game)
    monkeypatch.setattr(server, 'get_player_progress', load)
    server.pending.clear()

    @contextlib.asynccontextmanager
    async def lifespan(_app):
        task = asyncio.create_task(isolated_game.run())
        try:
            yield
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    monkeypatch.setattr(server.app.router, 'lifespan_context', lifespan)
    account_id = 'rejoin-account'
    initial = {'owned_soldier_tiers': ['soldier_s1'], 'active_soldier_tiers': ['soldier_s1'], 'owned_soldiers': [{'instance_id': 'rejoin-s1', 'tier_id': 'soldier_s1', 'active': True, 'runtime': {}}], 'active_soldier_ids': ['rejoin-s1']}
    server.pending['first'] = {'account_id': account_id, 'name': 'Rejoin', 'weapon': 'glock18', 'skin': 'soldier', 'progress': initial, 'expires': 9999999999}
    with TestClient(server.app) as client:
        with client.websocket_connect('/api/ws/first') as ws:
            assert ws.receive_json()['type'] == 'welcome'
            player = next(p for p in isolated_game.players.values() if p['account_id'] == account_id)
            actor = isolated_game.soldiers['rejoin-s1']; player.update(x=100., z=0.); actor.update(x=100., z=0., ammo=3, reserve=5, is_soldier=True)
            ws.send_json({'type': 'soldier_rename', 'instance_id': 'rejoin-s1', 'nickname': '  Last Watch  '})
            assert ws.receive_json()['type'] == 'action_success'
            assert actor['name'] == 'Last Watch' and actor['ammo'] == 3 and actor['reserve'] == 5
            assert client.portal.call(lambda: damage_player(isolated_game, actor, 999, 'Zombie', 0.))
            deadline = actor['recovery_until_utc']
        # The websocket finally block flushes its account save before removal.
        server.pending['second'] = {'account_id': account_id, 'name': 'Rejoin', 'weapon': 'glock18', 'skin': 'soldier', 'progress': {}, 'expires': 9999999999}
        with client.websocket_connect('/api/ws/second') as ws:
            assert ws.receive_json()['type'] == 'welcome'
            restored = next(p for p in isolated_game.players.values() if p['account_id'] == account_id)
            snapshot = isolated_game.snapshot(restored, 0.)['me']
            companion = next(item for item in snapshot['soldiers'] if item['id'] == 'rejoin-s1')
            assert companion['name'] == 'Last Watch' and companion['status'] == 'recovering' and companion['recovery_time'] > 0
            restored_actor = isolated_game.soldiers['rejoin-s1']
            assert restored_actor['ammo'] == 3 and restored_actor['reserve'] == 5 and restored_actor['recovery_until_utc'] == deadline

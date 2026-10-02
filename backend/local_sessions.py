"""Online presence + persistence only. Never simulates or sends world actors."""
import asyncio
import contextlib
import hashlib
import json
import secrets
import time
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import ValidationError
from local_progress import FIELDS, LocalReport, store_report
from player_accounts import get_player_progress


class LocalSessions:
    def __init__(self, db, game):
        self.db, self.game = db, game
        self.connections = {}
        self.report_locks = [asyncio.Lock() for _ in range(64)]
        self.join_lock = asyncio.Lock()
        self.router = APIRouter()
        self.router.add_api_websocket_route('/api/ws/{token}', self.websocket)
        self.router.add_api_route('/api/local/report', self.recover, methods=['POST'])

    async def persist(self, run_id, data):
        lock = self.report_locks[int(hashlib.sha256(run_id.encode()).hexdigest(), 16) % len(self.report_locks)]
        async with lock:
            run = await self.db.local_runs.find_one({'id': run_id}, {'_id': 0})
            report = LocalReport.model_validate(data)
            if report.sequence <= run.get('sequence', 0):
                return run.get('revision', report.revision)
            return await store_report(self.db, run, report)

    async def recover(self, request: Request):
        raw = await request.body()
        if len(raw) > 128_000:
            raise HTTPException(413, 'Report too large.')
        try:
            body = json.loads(raw)
            token = body['token']
            if not isinstance(token, str) or len(token) > 100:
                raise ValueError()
            run = await self.db.local_runs.find_one({'token_hash': hashlib.sha256(token.encode()).hexdigest(),
                'expires_at': {'$gt': datetime.now(timezone.utc)}}, {'_id': 0})
            if not run:
                raise HTTPException(410, 'Recovery session expired.')
            revision = await self.persist(run['id'], body['report'])
            return {'saved': True, 'revision': revision}
        except (ValueError, KeyError, TypeError, ValidationError):
            raise HTTPException(422, 'Invalid report.')

    async def setup(self):
        await self.db.local_runs.create_index('id', unique=True)
        await self.db.local_runs.create_index('token_hash', unique=True)
        await self.db.local_runs.create_index('expires_at', expireAfterSeconds=0)
        await self.db.local_runs.create_index('last_seen')

    async def active(self):
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=12)
        return await self.db.local_runs.find({'connected': True, 'last_seen': {'$gt': cutoff}},
            {'_id': 0, 'id': 1, 'account_id': 1, 'name': 1, 'weapon': 1, 'hp': 1, 'score': 1}).to_list(200)

    async def create(self, user, skin):
        async with self.join_lock:
            active = await self.active()
            if len(active) >= 200:
                raise HTTPException(409, 'The server is full.')
            account_id = user['account_id']
            if any(p['account_id'] == account_id for p in active):
                raise HTTPException(409, 'This wallet already has an active game. Leave that game first.')
            # Invalidate unfinished tickets and disconnected games for this account.
            await self.db.local_runs.update_many({'account_id': account_id}, {'$set': {'closed': True}})
            progress = await get_player_progress(self.db, account_id)
            token, run_id = secrets.token_urlsafe(32), secrets.token_hex(16)
            name = user['account'].get('nickname') or 'Survivor'
            now = datetime.now(timezone.utc)
            run = {'id': run_id, 'token_hash': hashlib.sha256(token.encode()).hexdigest(),
                   'account_id': account_id, 'name': name, 'skin': skin, 'connected': False,
                   'started_at': now.timestamp(), 'last_seen': now, 'expires_at': now + timedelta(hours=24),
                   'sequence': 0, 'score': 0, 'kills': 0, 'pvp': 0, 'weapon': 'glock18', 'hp': 100,
                   'client_progress': {k: progress[k] for k in FIELDS if k in progress}}
            await self.db.local_runs.insert_one(run)
            return {'token': token, 'run_id': run_id, 'name': name, 'skin': skin, 'account_id': account_id,
                    'weapon': 'glock18', 'progress': progress, 'settings': self.game.settings,
                    'simulation': 'local'}

    async def websocket(self, ws: WebSocket, token: str):
        run = await self.db.local_runs.find_one({'token_hash': hashlib.sha256(token.encode()).hexdigest(),
            'closed': {'$ne': True}, 'expires_at': {'$gt': datetime.now(timezone.utc)}}, {'_id': 0})
        if not run:
            await ws.close(code=1008)
            return
        async with self.join_lock:
            active = await self.active()
            if run['id'] in self.connections or any(p['account_id'] == run['account_id'] for p in active):
                await ws.close(code=4009)
                return
            if len(active) >= 200:
                await ws.close(code=1013)
                return
            # Check again after acquiring the lock: another join can revoke a ticket.
            if not await self.db.local_runs.find_one({'id': run['id'], 'closed': {'$ne': True}}, {'_id': 0, 'id': 1}):
                await ws.close(code=1008)
                return
            await ws.accept()
            self.connections[run['id']] = ws
            await self.db.local_runs.update_one({'id': run['id']}, {'$set': {'connected': True, 'last_seen': datetime.now(timezone.utc)}})
        last_report = 0
        async def social():
            while True:
                active = await self.active()
                leaders = await self.db.scores.find({}, {'_id': 0}).sort('score', -1).limit(10).to_list(10)
                await ws.send_json({'type': 'social', 'online': len({p['account_id'] for p in active}),
                                    'leaders': leaders, 'settings': self.game.settings})
                await asyncio.sleep(2)
        task = asyncio.create_task(social())
        try:
            while True:
                raw = await asyncio.wait_for(ws.receive_text(), timeout=15)
                if len(raw) > 128_000:
                    await ws.close(code=1009)
                    break
                data = json.loads(raw)
                if not isinstance(data, dict):
                    continue
                if data.get('type') == 'ping':
                    await self.db.local_runs.update_one({'id': run['id'], 'closed': {'$ne': True}},
                        {'$set': {'last_seen': datetime.now(timezone.utc)}})
                    await ws.send_json({'type': 'pong', 'time': data.get('time')})
                elif data.get('type') == 'report':
                    if time.monotonic() - last_report < .25:
                        continue
                    last_report = time.monotonic()
                    try:
                        report = LocalReport.model_validate(data)
                        revision = await self.persist(run['id'], data)
                        await ws.send_json({'type': 'saved', 'sequence': report.sequence, 'revision': revision})
                    except (ValidationError, ValueError):
                        await ws.send_json({'type': 'sync_error', 'message': 'Progress report rejected; local game continues.'})
                    except Exception:
                        import logging
                        logging.exception('Local progress save failed')
                        await ws.send_json({'type': 'sync_error', 'message': 'Progress could not be saved. Retrying.'})
                elif data.get('type') == 'leave':
                    await self.db.local_runs.update_one({'id': run['id']}, {'$set': {'closed': True}})
                    await ws.send_json({'type': 'left'})
                    break
                # Movement, damage, enemy coordinates are deliberately NOT accepted.
        except (WebSocketDisconnect, TimeoutError, ValueError, RuntimeError):
            pass
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
            self.connections.pop(run['id'], None)
            await self.db.local_runs.update_one({'id': run['id']}, {'$set': {'connected': False}})
            with contextlib.suppress(Exception):
                await ws.close()
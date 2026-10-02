import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from admin_auth import auth_routes
from game_settings import GameSettings, apply_settings
from admin_wallets import wallet_admin_router


class Participant(BaseModel):
    id: str
    name: str
    bot: bool
    weapon: str
    hp: float
    score: int


class AdminStatus(BaseModel):
    humans: int
    bots: int
    total: int
    zombies: int
    capacity: int = 200
    tick_ms: float
    participants: list[Participant]


def create_admin_router(db, game, early_db=None):
    auth, require_admin = auth_routes(db)
    router = APIRouter(prefix='/api/admin', dependencies=[Depends(require_admin)])
    router.include_router(wallet_admin_router(db, early_db))
    lock = asyncio.Lock()

    @router.get('/settings', response_model=GameSettings)
    async def settings(response: Response):
        response.headers['Cache-Control'] = 'no-store'
        return game.settings

    @router.put('/settings', response_model=GameSettings)
    async def update_settings(body: GameSettings):
        settings = body.model_dump()
        async with lock:
            await db.game_settings.update_one({'id': 'world'}, {'$set': {'settings': settings, 'updated_at': datetime.now(timezone.utc).isoformat()}}, upsert=True)
            apply_settings(game, settings)
        return settings

    @router.get('/status', response_model=AdminStatus)
    async def status(response: Response):
        response.headers['Cache-Control'] = 'no-store'
        players = await game.local_sessions.active()
        from game_settings import zombie_target
        return {'humans': len(players), 'bots': game.settings['bot_count'], 'total': len(players), 'zombies': zombie_target(game.settings), 'tick_ms': 0,
                'participants': [{**{k: p[k] for k in ('id', 'name', 'weapon', 'hp', 'score')}, 'bot': bool(p.get('bot'))} for p in players]}

    root = APIRouter()
    root.include_router(auth)
    root.include_router(router)
    return root
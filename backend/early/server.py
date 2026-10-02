import logging
import os
import httpx
import asyncio
import time
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from starlette.responses import JSONResponse

load_dotenv(Path(__file__).parent / '.env')
from .registry import router
from .settings import public_config
from .campaign import seed_campaign, get_campaign
from .admin import router as admin_router
from .admin_security import seed_admin
from .x_avatar import router as x_avatar_router
from .avatar_provider import TIMEOUT, UA

logging.basicConfig(level=logging.INFO)
client = AsyncIOMotorClient(os.environ['MONGO_URL2'], serverSelectionTimeoutMS=15000)
db = client[os.environ['DB_NAME2']]


setup_lock = asyncio.Lock()


async def initialize(app):
    await seed_campaign(db)
    public_config((await get_campaign(db)).settings)
    await seed_admin(db)
    await db.agents.create_index('handle_key', unique=True)
    await db.agents.create_index('ref_code', unique=True)
    await db.agents.create_index('request_id', unique=True)
    await db.agents.create_index('created_at')
    await db.counters.create_index('name', unique=True)
    await db.counters.update_one({'name': 'agent_number'}, {'$setOnInsert': {'value': 0}}, upsert=True)
    await db.x_avatar_metadata.create_index('handle', unique=True)
    await db.x_avatar_metadata.create_index('expires_at', expireAfterSeconds=0)
    app.state.ready = True


async def ensure_ready(app):
    if getattr(app.state, 'ready', False):
        return True
    async with setup_lock:
        if getattr(app.state, 'ready', False):
            return True
        if time.monotonic() < getattr(app.state, 'retry_at', 0):
            return False
        try:
            await initialize(app)
        except Exception as error:
            app.state.retry_at = time.monotonic() + 30
            logging.error('Early database unavailable (%s); game remains available.', type(error).__name__)
    return getattr(app.state, 'ready', False)


@asynccontextmanager
async def lifespan(app):
    app.state.db = db
    app.state.x_http = httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=False, headers={'User-Agent': UA})
    await ensure_ready(app)
    yield
    await app.state.x_http.aclose()
    client.close()


app = FastAPI(title='LastZhood Survivor Registry', lifespan=lifespan)
cors_origins = [origin.strip().rstrip('/') for origin in os.environ['CORS_ORIGINS'].split(',')]
# Reflect concrete HTTP(S) origins when wildcard mode is configured. Sending
# ACAO '*' with credentials would still block cookie login in browsers.
cors_any_origin = '*' in cors_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[] if cors_any_origin else cors_origins,
    allow_origin_regex=r'^https?://[^/\s]+$' if cors_any_origin else None,
    allow_credentials=True,
    allow_methods=['GET', 'POST', 'PUT'],
    allow_headers=['Content-Type', 'X-Admin-Client', 'X-CSRF-Token'],
)
app.include_router(router)
app.include_router(x_avatar_router)
app.include_router(admin_router)


@app.middleware('http')
async def private_settings_cache(request, call_next):
    if not await ensure_ready(request.app):
        return JSONResponse({'detail': 'Early database connection is unavailable. Please retry shortly.'}, status_code=503,
                            headers={'Cache-Control': 'no-store', 'Retry-After': '30'})
    response = await call_next(request)
    if '/admin' in request.url.path or request.url.path.endswith('/config'):
        response.headers['Cache-Control'] = 'no-store'
    return response


@app.get('/')
async def root():
    return {'service': 'LastZhood Survivor Registry', 'status': 'online'}
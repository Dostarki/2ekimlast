import hashlib
import logging
import secrets
import string
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from .models import AgentPublic, ParticipationCreate, PublicConfig, RegistryStats
from .settings import public_config
from .campaign import get_campaign

router = APIRouter()
PUBLIC_FIELDS = {key: 1 for key in AgentPublic.model_fields}
PUBLIC_FIELDS['_id'] = 0


@router.get('/config', response_model=PublicConfig)
async def config(request: Request):
    try:
        return public_config((await get_campaign(request.app.state.db)).settings)
    except (ValueError, KeyError, TypeError):
        logging.exception('Invalid campaign configuration')
        raise HTTPException(503, 'Mission settings are unavailable. Please try again later.')


@router.get('/agents/stats', response_model=RegistryStats)
async def stats(request: Request):
    return RegistryStats(count=await request.app.state.db.agents.count_documents({}))


@router.get('/agents/recent', response_model=list[AgentPublic])
async def recent(request: Request):
    return await request.app.state.db.agents.find({}, PUBLIC_FIELDS).sort('number', -1).limit(16).to_list(16)


@router.get('/agents/{ref_code}', response_model=AgentPublic)
async def public_agent(ref_code: str, request: Request):
    agent = await request.app.state.db.agents.find_one({'ref_code': ref_code.upper()}, PUBLIC_FIELDS)
    if not agent:
        raise HTTPException(404, 'Agent not found.')
    return agent


@router.post('/participations', response_model=AgentPublic, status_code=201)
async def participate(payload: ParticipationCreate, request: Request):
    db = request.app.state.db
    request_id = str(payload.request_id)
    previous = await db.agents.find_one({'request_id': request_id}, PUBLIC_FIELDS)
    if previous:
        if previous['handle'].lower() != payload.handle.lower():
            raise HTTPException(409, 'This submission has already been used. Start a new mission.')
        return previous
    if await db.agents.find_one({'handle_key': payload.handle.lower()}, {'_id': 0, 'number': 1}):
        raise HTTPException(409, 'This X handle is already registered. Use a different handle, or return to the browser where you registered.')
    if payload.referred_by and not await db.agents.find_one({'ref_code': payload.referred_by}, {'_id': 0, 'number': 1}):
        raise HTTPException(422, 'That referral code does not exist.')
    counter = await db.counters.find_one_and_update(
        {'name': 'agent_number'}, {'$inc': {'value': 1}}, upsert=True,
        return_document=ReturnDocument.AFTER, projection={'_id': 0, 'value': 1})
    fingerprint = int(hashlib.sha256(payload.handle.lower().encode()).hexdigest()[:8], 16)
    public = AgentPublic(
        handle=payload.handle, number=counter['value'],
        ref_code=''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8)),
        cell=f'{fingerprint % 64:02d}.{(fingerprint // 64) % 64:02d}',
        agent_class=['SCOUT', 'OPERATOR', 'RANGER', 'SIGNAL'][fingerprint % 4],
        tier='GENESIS', created_at=datetime.now(timezone.utc).isoformat())
    doc = {**public.model_dump(), 'handle_key': payload.handle.lower(),
           'wallet': payload.wallet, 'completed_tasks': payload.completed_tasks,
           'consent': payload.consent, 'referred_by': payload.referred_by,
           'request_id': request_id}
    try:
        await db.agents.insert_one(doc)
    except DuplicateKeyError:
        retry = await db.agents.find_one({'request_id': request_id}, PUBLIC_FIELDS)
        if retry and retry['handle'].lower() == payload.handle.lower():
            return retry
        raise HTTPException(409, 'This X handle is already registered. Please use another handle.')
    # insert_one mutates doc with ObjectId; return the separate validated public model.
    return public
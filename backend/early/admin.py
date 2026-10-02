from datetime import datetime, timezone

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pymongo import ReturnDocument
from starlette.concurrency import run_in_threadpool

from .admin_security import (ACCESS_SECONDS, clear_cookies, issue_session, require_admin,
                            require_admin_client, reserve_login_attempt, session_from_cookie,
                            set_token_cookie, token_for)
from .campaign import CAMPAIGN_ID, CampaignResponse, CampaignUpdate, get_campaign
from admin_wallets import wallet_export

router = APIRouter(prefix='/admin')


class LoginPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    password: str = Field(min_length=1, max_length=72)

    @field_validator('password')
    @classmethod
    def byte_length(cls, value):
        if len(value.encode('utf-8')) > 72:
            raise ValueError('Şifre en fazla 72 bayt olabilir.')
        return value


class AuthResponse(BaseModel):
    authenticated: bool


class LoginResponse(AuthResponse):
    csrf_token: str


@router.post('/login', response_model=LoginResponse, dependencies=[Depends(require_admin_client)])
async def login(payload: LoginPayload, request: Request, response: Response):
    db = request.app.state.db
    identifier = await reserve_login_attempt(request)
    admin = await db.admin_users.find_one({'_id': 'admin'}, {'_id': 0, 'password_hash': 1})
    valid = admin and await run_in_threadpool(bcrypt.checkpw, payload.password.encode(), admin['password_hash'].encode())
    if not valid:
        raise HTTPException(401, 'Şifre yanlış. Lütfen tekrar deneyin.')
    await db.admin_login_attempts.delete_one({'_id': identifier})
    proof = await issue_session(db, response)
    return LoginResponse(authenticated=True, csrf_token=proof)


@router.get('/me', response_model=AuthResponse, dependencies=[Depends(require_admin)])
async def me():
    return AuthResponse(authenticated=True)


@router.post('/refresh', response_model=AuthResponse)
async def refresh(request: Request, response: Response):
    session_id = await session_from_cookie(request, 'refresh')
    set_token_cookie(response, 'access_token', token_for(session_id, 'access', ACCESS_SECONDS), ACCESS_SECONDS)
    return AuthResponse(authenticated=True)


@router.post('/logout', response_model=AuthResponse)
async def logout(request: Request, response: Response):
    # Revoke even when the short-lived access cookie has expired.
    for kind in ('refresh', 'access'):
        try:
            session_id = await session_from_cookie(request, kind)
            await request.app.state.db.admin_sessions.delete_one({'session_id': session_id})
            break
        except HTTPException as error:
            if error.status_code != 401:
                raise
    else:
        raise HTTPException(401, 'Oturum sona erdi. Lütfen tekrar giriş yapın.')
    clear_cookies(response)
    return AuthResponse(authenticated=False)


@router.get('/wallets.txt', dependencies=[Depends(require_admin)])
async def export_wallets(request: Request):
    return await wallet_export(request.app.state.db.agents, 'wallet', 'lastzhood-early-wallets.txt')


@router.get('/settings', response_model=CampaignResponse, dependencies=[Depends(require_admin)])
async def read_settings(request: Request):
    return await get_campaign(request.app.state.db)


@router.put('/settings', response_model=CampaignResponse,
            dependencies=[Depends(require_admin)])
async def save_settings(payload: CampaignUpdate, request: Request):
    document = await request.app.state.db.campaign_settings.find_one_and_update(
        {'_id': CAMPAIGN_ID, 'revision': payload.revision},
        {'$set': {'settings': payload.model_dump(exclude={'revision'}),
                  'updated_at': datetime.now(timezone.utc).isoformat()}, '$inc': {'revision': 1}},
        return_document=ReturnDocument.AFTER, projection={'_id': 0})
    if not document:
        raise HTTPException(409, 'Ayarlar başka bir oturumda değişti. Güncel ayarları yükleyip tekrar düzenleyin.')
    return CampaignResponse.model_validate(document)
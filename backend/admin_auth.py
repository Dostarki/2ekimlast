"""Password-only operator login. No change to guest game tickets."""
import os
import secrets
import logging
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from pymongo import ReturnDocument
from starlette.concurrency import run_in_threadpool


class LoginBody(BaseModel):
    password: str = Field(min_length=1, max_length=72)


class AdminIdentity(BaseModel):
    role: str = 'admin'


def check_origin(request: Request):
    # Origin/domain restriction intentionally disabled: admin access is granted
    # by the operator password alone (brute-force attempt limit still applies).
    return


async def setup_admin(db):
    password_hash = os.environ['ADMIN_PASSWORD_HASH']
    os.environ['JWT_SECRET']  # Fail fast on incomplete configuration.
    account = await db.admin_accounts.find_one({'id': 'operator'}, {'_id': 0})
    if not account or account['password_hash'] != password_hash:
        await db.admin_accounts.update_one({'id': 'operator'}, {'$set': {'id': 'operator', 'password_hash': password_hash}}, upsert=True)
        await db.admin_sessions.delete_many({})
    await db.admin_accounts.create_index('id', unique=True)
    await db.admin_sessions.create_index('expires_at', expireAfterSeconds=0)
    await db.admin_sessions.create_index('sid', unique=True)
    await db.login_attempts.create_index('identifier', unique=True)
    await db.login_attempts.create_index('expires_at', expireAfterSeconds=0)


def auth_routes(db):
    router = APIRouter(prefix='/api/admin', tags=['admin'])

    async def session(request, kind='access'):
        token = request.cookies.get(f'admin_{kind}')
        try:
            payload = jwt.decode(token or '', os.environ['JWT_SECRET'], algorithms=['HS256'], options={'require': ['exp', 'sub', 'type', 'sid']})
            if payload['sub'] != 'operator' or payload['type'] != kind:
                raise ValueError()
            row = await db.admin_sessions.find_one({'sid': payload['sid'], 'expires_at': {'$gt': datetime.now(timezone.utc)}}, {'_id': 0, 'sid': 1})
            if not row:
                raise ValueError()
            return payload['sid']
        except (jwt.InvalidTokenError, ValueError):
            raise HTTPException(401, 'An admin session is required.')

    async def require_admin(request: Request):
        if request.method not in ('GET', 'HEAD'):
            check_origin(request)
        return await session(request)

    def set_tokens(response, sid, refresh=True):
        now = datetime.now(timezone.utc)
        for kind, seconds in [('access', 900), ('refresh', 604800)] if refresh else [('access', 900)]:
            token = jwt.encode({'sub': 'operator', 'sid': sid, 'type': kind, 'exp': now+timedelta(seconds=seconds)}, os.environ['JWT_SECRET'], algorithm='HS256')
            response.set_cookie(f'admin_{kind}', token, max_age=seconds, httponly=True, secure=True, samesite='strict', path='/api/admin')
        response.headers['Cache-Control'] = 'no-store'

    @router.post('/login', response_model=AdminIdentity)
    async def login(body: LoginBody, request: Request, response: Response):
        check_origin(request)
        now = datetime.now(timezone.utc)
        # One operator account: proxy IP rotation must not bypass or split its limit.
        identifier = 'admin:operator'
        await db.login_attempts.delete_one({'identifier': identifier, 'expires_at': {'$lte': now}})
        attempt = await db.login_attempts.find_one_and_update({'identifier': identifier}, {'$inc': {'count': 1}, '$setOnInsert': {'expires_at': now+timedelta(minutes=15)}}, upsert=True, return_document=ReturnDocument.AFTER, projection={'_id': 0})
        if attempt['count'] > 5:
            expires = attempt['expires_at'].replace(tzinfo=timezone.utc)
            retry = max(1, int((expires-now).total_seconds()))
            raise HTTPException(429, 'Too many sign-in attempts. Try again in 15 minutes.', headers={'Retry-After': str(retry)})
        account = await db.admin_accounts.find_one({'id': 'operator'}, {'_id': 0})
        encoded = body.password.encode()
        valid = len(encoded) <= 72 and await run_in_threadpool(bcrypt.checkpw, encoded, account['password_hash'].encode())
        if not valid:
            raise HTTPException(401, 'Incorrect password.')
        await db.login_attempts.delete_one({'identifier': identifier})
        sid = secrets.token_urlsafe(32)
        await db.admin_sessions.insert_one({'sid': sid, 'expires_at': now+timedelta(days=7)})
        set_tokens(response, sid)
        return AdminIdentity()

    @router.get('/me', response_model=AdminIdentity)
    async def me(response: Response, sid=Depends(require_admin)):
        response.headers['Cache-Control'] = 'no-store'
        return AdminIdentity()

    @router.post('/refresh', response_model=AdminIdentity)
    async def refresh(request: Request, response: Response):
        check_origin(request)
        set_tokens(response, await session(request, 'refresh'), refresh=False)
        return AdminIdentity()

    @router.post('/logout', response_model=AdminIdentity)
    async def logout(request: Request, response: Response):
        check_origin(request)
        for kind in ('access', 'refresh'):
            try:
                await db.admin_sessions.delete_one({'sid': await session(request, kind)})
            except HTTPException:
                pass
            response.delete_cookie(f'admin_{kind}', path='/api/admin', secure=True, httponly=True, samesite='strict')
        return AdminIdentity()

    return router, require_admin

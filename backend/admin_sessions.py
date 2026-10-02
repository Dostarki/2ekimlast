"""Persistent operator sessions and password validation, independent of routes."""
import os
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import HTTPException
from pymongo import ReturnDocument
from starlette.concurrency import run_in_threadpool

COOKIE_PATH = '/api/admin'
TOKEN_TTLS = {'access': 900, 'refresh': 604800}


class AdminSessions:
    def __init__(self, db):
        self.db = db

    async def session(self, request, kind='access'):
        token = request.cookies.get(f'admin_{kind}')
        try:
            payload = jwt.decode(token or '', os.environ['JWT_SECRET'], algorithms=['HS256'],
                                 options={'require': ['exp', 'sub', 'type', 'sid']})
            if payload['sub'] != 'operator' or payload['type'] != kind:
                raise ValueError()
            row = await self.db.admin_sessions.find_one(
                {'sid': payload['sid'], 'expires_at': {'$gt': datetime.now(timezone.utc)}},
                {'_id': 0, 'sid': 1})
            if not row:
                raise ValueError()
            return payload['sid']
        except (jwt.InvalidTokenError, ValueError):
            raise HTTPException(401, 'An admin session is required.')

    async def record_attempt(self, now):
        identifier = 'admin:operator'
        await self.db.login_attempts.delete_one({'identifier': identifier, 'expires_at': {'$lte': now}})
        attempt = await self.db.login_attempts.find_one_and_update(
            {'identifier': identifier}, {'$inc': {'count': 1},
            '$setOnInsert': {'expires_at': now + timedelta(minutes=15)}}, upsert=True,
            return_document=ReturnDocument.AFTER, projection={'_id': 0})
        if attempt['count'] > 5:
            expires = attempt['expires_at'].replace(tzinfo=timezone.utc)
            retry = max(1, int((expires - now).total_seconds()))
            raise HTTPException(429, 'Too many sign-in attempts. Try again in 15 minutes.',
                                headers={'Retry-After': str(retry)})

    async def verify_password(self, password):
        account = await self.db.admin_accounts.find_one({'id': 'operator'}, {'_id': 0})
        encoded = password.encode()
        valid = (account is not None and len(encoded) <= 72
                 and await run_in_threadpool(bcrypt.checkpw, encoded, account['password_hash'].encode()))
        if not valid:
            raise HTTPException(401, 'Incorrect password.')

    async def login(self, password, response):
        now = datetime.now(timezone.utc)
        await self.record_attempt(now)
        await self.verify_password(password)
        await self.db.login_attempts.delete_one({'identifier': 'admin:operator'})
        sid = secrets.token_urlsafe(32)
        await self.db.admin_sessions.insert_one({'sid': sid, 'expires_at': now + timedelta(days=7)})
        self.set_tokens(response, sid)

    @staticmethod
    def set_tokens(response, sid, refresh=True):
        now = datetime.now(timezone.utc)
        for kind in ('access', 'refresh') if refresh else ('access',):
            seconds = TOKEN_TTLS[kind]
            token = jwt.encode({'sub': 'operator', 'sid': sid, 'type': kind,
                                'exp': now + timedelta(seconds=seconds)}, os.environ['JWT_SECRET'], algorithm='HS256')
            response.set_cookie(f'admin_{kind}', token, max_age=seconds, httponly=True,
                                secure=True, samesite='strict', path=COOKIE_PATH)
        response.headers['Cache-Control'] = 'no-store'

    async def logout(self, request, response):
        for kind in ('access', 'refresh'):
            try:
                sid = await self.session(request, kind)
                await self.db.admin_sessions.delete_one({'sid': sid})
            except HTTPException:
                pass
            response.delete_cookie(f'admin_{kind}', path=COOKIE_PATH, secure=True,
                                   httponly=True, samesite='strict')
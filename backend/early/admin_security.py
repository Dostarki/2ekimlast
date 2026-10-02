import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import HTTPException, Request
from starlette.concurrency import run_in_threadpool

ACCESS_SECONDS = 15 * 60
REFRESH_SECONDS = 7 * 24 * 60 * 60
COOKIE_PATH = '/api/early/admin'


async def seed_admin(db):
    password = os.environ['EARLY_ADMIN_PASSWORD'].encode('utf-8')
    if not 10 <= len(password) <= 72 or len(os.environ['EARLY_JWT_SECRET']) < 32:
        raise ValueError('Admin password must be 10–72 bytes; JWT_SECRET must be at least 32 characters.')
    await db.admin_sessions.create_index('session_id', unique=True)
    await db.admin_sessions.create_index('expires_at', expireAfterSeconds=0)
    await db.admin_login_attempts.create_index('expires_at', expireAfterSeconds=0)
    existing = await db.admin_users.find_one({'_id': 'admin'}, {'_id': 0, 'password_hash': 1})
    if existing:
        return
    hashed = await run_in_threadpool(bcrypt.hashpw, password, bcrypt.gensalt())
    await db.admin_users.update_one({'_id': 'admin'}, {'$set': {'password_hash': hashed.decode(),
        'role': 'admin', 'updated_at': datetime.now(timezone.utc).isoformat()}}, upsert=True)
    await db.admin_sessions.delete_many({'admin_id': 'admin'})


def require_admin_client(request: Request):
    # Any web origin may authenticate with the password. A non-simple header
    # and JSON content type prevent plain cross-site form login requests.
    content_type = request.headers.get('content-type', '').split(';')[0].strip().lower()
    if request.headers.get('x-admin-client') != 'lastzhood-admin' or content_type != 'application/json':
        raise HTTPException(400, 'Geçersiz giriş isteği. Lütfen yönetici giriş formunu kullanın.')


def token_for(session_id, kind, duration):
    now = datetime.now(timezone.utc)
    return jwt.encode({'sub': 'admin', 'sid': session_id, 'type': kind, 'iat': now,
                       'exp': now + timedelta(seconds=duration)}, os.environ['EARLY_JWT_SECRET'], algorithm='HS256')


def set_token_cookie(response, name, token, duration):
    response.set_cookie(name, token, max_age=duration, httponly=True, secure=True,
                        samesite='none', path=COOKIE_PATH)


def clear_cookies(response):
    for name in ('access_token', 'refresh_token'):
        response.delete_cookie(name, path=COOKIE_PATH, secure=True, httponly=True, samesite='none')


async def issue_session(db, response):
    session_id = secrets.token_urlsafe(32)
    proof = secrets.token_urlsafe(32)
    await db.admin_sessions.insert_one({'session_id': session_id, 'admin_id': 'admin',
                                       'csrf_hash': hashlib.sha256(proof.encode()).hexdigest(),
                                       'expires_at': datetime.now(timezone.utc) + timedelta(seconds=REFRESH_SECONDS)})
    set_token_cookie(response, 'access_token', token_for(session_id, 'access', ACCESS_SECONDS), ACCESS_SECONDS)
    set_token_cookie(response, 'refresh_token', token_for(session_id, 'refresh', REFRESH_SECONDS), REFRESH_SECONDS)
    # Only password-authenticated login returns the plaintext proof.
    return proof


async def session_from_cookie(request: Request, kind='access'):
    proof = request.headers.get('x-csrf-token')
    if not proof:
        raise HTTPException(401, 'Oturum sona erdi. Lütfen tekrar giriş yapın.')
    if len(proof) > 128:
        raise HTTPException(403, 'Oturum doğrulanamadı. Lütfen tekrar giriş yapın.')
    try:
        payload = jwt.decode(request.cookies.get(f'{kind}_token', ''), os.environ['EARLY_JWT_SECRET'],
                             algorithms=['HS256'], options={'require': ['exp', 'iat', 'sub', 'sid', 'type']})
        if payload['sub'] != 'admin' or payload['type'] != kind:
            raise jwt.InvalidTokenError()
    except jwt.InvalidTokenError:
        raise HTTPException(401, 'Oturum sona erdi. Lütfen tekrar giriş yapın.')
    db = request.app.state.db
    session = await db.admin_sessions.find_one({'session_id': payload['sid'], 'admin_id': 'admin',
        'expires_at': {'$gt': datetime.now(timezone.utc)}}, {'_id': 0, 'session_id': 1, 'csrf_hash': 1})
    admin = await db.admin_users.find_one({'_id': 'admin', 'role': 'admin'}, {'_id': 0, 'role': 1})
    if not session or not admin or not session.get('csrf_hash'):
        raise HTTPException(401, 'Oturum sona erdi. Lütfen tekrar giriş yapın.')
    if not secrets.compare_digest(hashlib.sha256(proof.encode()).hexdigest(), session['csrf_hash']):
        raise HTTPException(403, 'Oturum doğrulanamadı. Lütfen tekrar giriş yapın.')
    return session['session_id']


async def require_admin(request: Request):
    return await session_from_cookie(request)


async def reserve_login_attempt(request: Request):
    from pymongo import ReturnDocument
    now = datetime.now(timezone.utc)
    # This application has exactly one administrator. Bucket attempts by that
    # account, not rotating ingress IPs or spoofable forwarded headers.
    # Mongo's atomic increment also limits concurrent/distributed attempts.
    identifier = 'admin:' + str(int(now.timestamp()) // 900)
    attempt = await request.app.state.db.admin_login_attempts.find_one_and_update({'_id': identifier},
        {'$inc': {'count': 1}, '$setOnInsert': {'expires_at': now + timedelta(minutes=15)}},
        upsert=True, return_document=ReturnDocument.AFTER, projection={'_id': 0, 'count': 1})
    if attempt['count'] > 5:
        raise HTTPException(429, 'Çok fazla giriş denemesi. Lütfen 15 dakika sonra tekrar deneyin.',
                            headers={'Retry-After': '900'})
    return identifier
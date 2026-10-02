"""Password-only operator login. No change to guest game tickets."""
import os
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from admin_sessions import AdminSessions


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


class AdminAuthRoutes:
    def __init__(self, db):
        self.sessions = AdminSessions(db)

    async def require_admin(self, request: Request):
        if request.method not in ('GET', 'HEAD'):
            check_origin(request)
        return await self.sessions.session(request)

    async def login(self, body: LoginBody, request: Request, response: Response):
        check_origin(request)
        await self.sessions.login(body.password, response)
        return AdminIdentity()

    async def me(self, response: Response):
        response.headers['Cache-Control'] = 'no-store'
        return AdminIdentity()

    async def refresh(self, request: Request, response: Response):
        check_origin(request)
        self.sessions.set_tokens(response, await self.sessions.session(request, 'refresh'), refresh=False)
        return AdminIdentity()

    async def logout(self, request: Request, response: Response):
        check_origin(request)
        await self.sessions.logout(request, response)
        return AdminIdentity()


def auth_routes(db):
    router = APIRouter(prefix='/api/admin', tags=['admin'])
    handlers = AdminAuthRoutes(db)
    require_admin = handlers.require_admin
    router.add_api_route('/login', handlers.login, methods=['POST'], response_model=AdminIdentity)
    router.add_api_route('/me', handlers.me, methods=['GET'], response_model=AdminIdentity,
                         dependencies=[Depends(require_admin)])
    router.add_api_route('/refresh', handlers.refresh, methods=['POST'], response_model=AdminIdentity)
    router.add_api_route('/logout', handlers.logout, methods=['POST'], response_model=AdminIdentity)
    return router, require_admin

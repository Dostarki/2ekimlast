"""Authenticated access-checkout routes; never accepts client prices or paid flags."""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError
from access_payments import access_status, quote_access, submit_access
from player_auth import get_session_account

log = logging.getLogger(__name__)


class AccessState(BaseModel):
    paid: bool
    fee_exempt: bool
    price_usd: str
    chain_id: int
    treasury: str
    order: Optional[dict] = None


class AccessSubmit(BaseModel):
    order_id: str = Field(min_length=1, max_length=80)
    tx_hash: str = Field(pattern=r'^0x[0-9a-fA-F]{64}$')


def access_router(db):
    router = APIRouter(prefix='/api/access', tags=['access'])

    async def owner(request: Request):
        token = request.headers.get('Authorization', '').removeprefix('Bearer ') or request.cookies.get('deadzone_session')
        session = await get_session_account(db, token) if token else None
        if not session:
            raise HTTPException(401, 'WALLET_SIGNATURE_REQUIRED')
        return session['account_id']

    @router.get('', response_model=AccessState)
    async def status(account_id=Depends(owner)):
        return await access_status(db, account_id)

    @router.post('/quote', response_model=AccessState)
    async def quote(account_id=Depends(owner)):
        try:
            return await quote_access(db, account_id)
        except Exception:
            log.exception('Access quote unavailable')
            raise HTTPException(503, 'PAYMENT_QUOTE_UNAVAILABLE')

    @router.post('/submit', response_model=AccessState)
    async def submit(body: AccessSubmit, account_id=Depends(owner)):
        try:
            return await submit_access(db, account_id, body.order_id, body.tx_hash)
        except (ValueError, PermissionError) as error:
            raise HTTPException(400, str(error))
        except DuplicateKeyError:
            raise HTTPException(409, 'TRANSACTION_ALREADY_USED')
        except Exception:
            log.exception('Access payment verification unavailable')
            raise HTTPException(503, 'PAYMENT_VERIFICATION_UNAVAILABLE')

    return router
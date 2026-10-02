"""Operator wallet tools. Mounted only inside the authenticated admin router."""
import re
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field
from pymongo.errors import PyMongoError

from access_payments import has_fee_exemption, has_paid_access
from document_models import BaseDocument
from economy import EconomyTransaction, mutate_gold_atomic
from player_accounts import get_account_by_address, get_player_progress


WALLET_PATTERN = r'^0x[0-9a-fA-F]{40}$'


def normalize_wallet(value):
    if not isinstance(value, str) or not re.fullmatch(WALLET_PATTERN, value.strip()) or int(value.strip()[2:], 16) == 0:
        raise ValueError('Geçerli, sıfır olmayan bir EVM cüzdan adresi girin.')
    return value.strip().lower()


WalletAddress = Annotated[str, BeforeValidator(normalize_wallet)]


class GoldGrant(BaseModel):
    model_config = ConfigDict(extra='forbid')
    wallet: WalletAddress
    amount: int = Field(gt=0, le=1_000_000_000, strict=True)
    request_id: UUID


class ExemptionUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    wallet: WalletAddress
    enabled: bool = Field(strict=True)


class FeeExemption(BaseDocument):
    granted_at: str
    granted_by: str


class WalletState(BaseModel):
    wallet: str
    registered: bool
    nickname: str | None
    gold: int | None
    fee_exempt: bool
    paid_access: bool


class GoldResult(BaseModel):
    wallet: str
    amount: int
    gold: int
    request_id: str


async def wallet_export(collection, field, filename):
    # No pagination cap: all registered wallets, once each, in deterministic order.
    pipeline = [
        {'$match': {field: {'$type': 'string', '$regex': WALLET_PATTERN}}},
        {'$group': {'_id': {'$toLower': '$' + field}}},
        {'$match': {'_id': {'$ne': '0x' + '0' * 40}}},
        {'$sort': {'_id': 1}},
    ]
    try:
        rows = await collection.aggregate(pipeline).to_list(length=None)
    except PyMongoError:
        raise HTTPException(503, 'Cüzdan listesi alınamadı. Veritabanı bağlantısını kontrol edip tekrar deneyin.')
    return Response(''.join(row['_id'] + '\n' for row in rows), media_type='text/plain', headers={
        'Content-Disposition': f'attachment; filename="{filename}"',
        'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
    })


async def wallet_state(db, wallet):
    account = await get_account_by_address(db, wallet)
    progress = await get_player_progress(db, wallet) if account else None
    return WalletState(wallet=wallet, registered=bool(account), nickname=account.get('nickname') if account else None,
                       gold=int(progress.get('gold', 0)) if progress else None,
                       fee_exempt=await has_fee_exemption(db, wallet), paid_access=await has_paid_access(db, wallet))


def wallet_admin_router(db, early_db):
    router = APIRouter(prefix='/wallets')

    @router.get('/game.txt')
    async def game_wallets():
        return await wallet_export(db.player_accounts, 'account_id', 'lastzhood-game-wallets.txt')

    @router.get('/early.txt')
    async def early_wallets():
        if early_db is None:
            raise HTTPException(503, 'Early veritabanı kullanılamıyor.')
        return await wallet_export(early_db.agents, 'wallet', 'lastzhood-early-wallets.txt')

    @router.post('/gold', response_model=GoldResult)
    async def grant_gold(body: GoldGrant, response: Response):
        response.headers['Cache-Control'] = 'no-store'
        if not await get_account_by_address(db, body.wallet):
            raise HTTPException(404, 'Bu cüzdan oyunda kayıtlı değil. Önce cüzdanla giriş yapılmalı.')
        key = f'admin-gold:{body.wallet}:{body.request_id}'
        for attempt in range(3):
            progress = await get_player_progress(db, body.wallet)
            previous = progress.get('applied_economy_requests', {}).get(key)
            if previous and previous['gold_delta'] != body.amount:
                raise HTTPException(409, 'Bu işlem numarası farklı bir gold miktarı için kullanılmış.')
            try:
                transaction = EconomyTransaction(account_id=body.wallet, gold_delta=body.amount,
                    action='admin_gold_grant', source_type='admin', source_id='operator',
                    reason='Admin panel gold grant', request_id=key)
                _, gold, _ = await mutate_gold_atomic(db, transaction)
                return GoldResult(wallet=body.wallet, amount=body.amount, gold=gold, request_id=str(body.request_id))
            except RuntimeError as error:
                if str(error) != 'progress_revision_conflict':
                    raise
                if attempt == 2:
                    raise HTTPException(409, 'Oyuncu bakiyesi güncelleniyor. Aynı işlemi tekrar deneyin.')

    @router.put('/fee-exemption', response_model=WalletState)
    async def set_exemption(body: ExemptionUpdate, response: Response):
        response.headers['Cache-Control'] = 'no-store'
        if body.enabled:
            grant = FeeExemption(id=body.wallet, granted_at=datetime.now(timezone.utc).isoformat(), granted_by='operator')
            await db.game_fee_exemptions.update_one({'_id': body.wallet}, {'$setOnInsert': grant.to_mongo()}, upsert=True)
        else:
            await db.game_fee_exemptions.delete_one({'_id': body.wallet})
        return await wallet_state(db, body.wallet)

    @router.get('/{wallet}', response_model=WalletState)
    async def lookup(wallet: WalletAddress, response: Response):
        response.headers['Cache-Control'] = 'no-store'
        return await wallet_state(db, wallet)

    return router

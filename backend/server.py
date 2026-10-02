import asyncio
import copy
import contextlib
import logging
import os
import secrets
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field

from world import WORLD, WEAPONS
from engine import Game
from skins import SkinId
from boss_catalog import boss_snapshot
from admin_auth import setup_admin
from admin_routes import create_admin_router
from game_settings import GameSettings, apply_settings
from inventory import equip_weapon, inventory_snapshot
from weapon_parts import create_weapon_part
from loot import use_heal_item, use_consumable, allocate_stat, craft_upgrade
from player_accounts import setup_account_indexes, get_player_progress, save_player_progress, DEFAULT_STATS, create_or_update_profile, sync_db_to_file
from player_auth import create_challenge, verify_signature, get_session_account, logout
from chain_config import CHAIN_ID
from access_payments import ensure_access_indexes
from access_routes import access_router
from local_sessions import LocalSessions

load_dotenv(Path(__file__).parent / '.env')
from early.server import app as early_app, lifespan as early_lifespan, db as early_db
client = AsyncIOMotorClient(os.environ['MONGO_URL'])
db = client[os.environ['DB_NAME']]
logging.basicConfig(level=logging.INFO)
log = logging.getLogger('deadzone')
pending = {}


async def save_score(player):
    if player['score'] <= 0 or player.get('bot'):
        return
    doc = {k: player[k] for k in ('id', 'name', 'weapon', 'score', 'kills', 'pvp')}
    doc['ended_at'] = datetime.now(timezone.utc).isoformat()
    try:
        await db.scores.update_one({'id': doc['id']}, {'$set': doc}, upsert=True)
    except Exception:
        log.exception('Score persistence failed')


async def save_player_progress_handler(player):
    account_id = player.get('account_id')
    if not account_id or player.get('bot'):
        return
    # Game.persist_progress supplies an immutable snapshot. Do not inspect the
    # live actor map here: it may already have been removed by a disconnect.
    data = {
        'revision': player.get('revision', 1),
        'gold': player.get('gold', 0),
        'xp': player.get('xp', 0),
        'level': player.get('level', 1),
        'stat_points': player.get('stat_points', 0),
        'stats': player.get('stats', DEFAULT_STATS),
        'heal_items': player.get('heal_items', {}),
        'consumables': player.get('consumables', {'energy_drink': 0}),
        'energy_drink_expires_at': player.get('energy_drink_expires_at'),
        'unlocked_weapons': list(player.get('inventory', {}).keys()),
        'equipped_weapon': player.get('weapon', 'glock18'),
        'weapon_parts': player.get('weapon_parts', []),
        'weapon_upgrades': player.get('weapon_upgrades', {}),
        'inventory': inventory_snapshot(player),
        'total_score': player.get('score', 0),
        'kills': player.get('kills', 0),
        'pvp': player.get('pvp', 0),
        'equipped_equipment': player.get('equipped_equipment', {}),
        'owned_equipment': player.get('owned_equipment', []),
        'equipment_levels': player.get('equipment_levels', {}),
        'equipment_parts': player.get('equipment_parts', {}),
        'calibration': player.get('calibration', {}),
        'calibration_progress': player.get('calibration_progress', {'elite_kills': 0, 'boss_kills': 0}),
        'owned_soldier_tiers': player.get('owned_soldier_tiers', []),
        'active_soldier_tier': player.get('active_soldier_tier', None),
        'active_soldier_tiers': player.get('active_soldier_tiers', []),
        'owned_soldiers': player.get('owned_soldiers', []),
        'active_soldier_ids': player.get('active_soldier_ids', []),
        'vip_until_utc': player.get('vip_until_utc'),
        'is_vip': player.get('is_vip', False),
        'bonus_numerator_remainder': player.get('bonus_numerator_remainder', 0),
        'unlocked_badges': player.get('unlocked_badges', []),
        'active_badge': player.get('active_badge'),
        'name_color': player.get('name_color'),
        'current_mission_ids': player.get('current_mission_ids', []),
        'applied_market_order_ids': player.get('applied_market_order_ids', []),
        'applied_mission_claims': player.get('applied_mission_claims', {}),
        'applied_delivery_claims': player.get('applied_delivery_claims', {}),
    }
    await save_player_progress(db, account_id, data)
    player['revision'] = data['revision']


game = Game(save_score, save_progress=save_player_progress_handler)
local_sessions = LocalSessions(db, game)
game.local_sessions = local_sessions


@asynccontextmanager
async def lifespan(app):
    await db.scores.create_index([('score', -1)])
    await setup_admin(db)
    await setup_account_indexes(db)
    await ensure_access_indexes(db)
    saved = await db.game_settings.find_one({'id': 'world'}, {'_id': 0})
    if saved:
        apply_settings(game, GameSettings.model_validate(saved['settings']).model_dump())
    await local_sessions.setup()
    async with early_lifespan(early_app):
        yield
    await asyncio.gather(*(p['channel'].stop() for p in list(game.players.values()) if not p.get('bot')))
    await asyncio.gather(*(save_score(p) for p in list(game.players.values())))
    await asyncio.gather(*(game.flush_progress(p) for p in list(game.players.values())))
    await sync_db_to_file(db)
    client.close()


app = FastAPI(lifespan=lifespan)
app.mount('/api/early', early_app)
app.include_router(local_sessions.router)
app.include_router(access_router(db))
app.add_middleware(CORSMiddleware, allow_origins=os.environ['CORS_ORIGINS'].split(','), allow_credentials=True, allow_methods=['*'], allow_headers=['*'])

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.include_router(create_admin_router(db, game, early_db))


from typing import Optional


class ChallengeRequest(BaseModel):
    address: str
    chain_id: int = CHAIN_ID
    domain: Optional[str] = None
    uri: Optional[str] = None



class VerifyRequest(BaseModel):
    message: str
    signature: str


class ChallengeResponse(BaseModel):
    nonce: str
    issuedAt: str
    address: str
    statement: str
    message: str


class WalletAuthResponse(BaseModel):
    authenticated: bool
    token: str
    sessionToken: str
    address: str
    hasProfile: bool
    new_account: bool = False
    account: dict
    progress: dict
    paid_access: bool
    fee_exempt: bool


class ProfileRequest(BaseModel):
    nickname: str
    skin: str = 'soldier'


class JoinRequest(BaseModel):
    name: Optional[str] = None
    weapon: str = 'glock18'
    skin: SkinId = 'soldier'


class Score(BaseModel):
    id: str
    name: str
    weapon: str
    score: int
    kills: int
    pvp: int
    ended_at: str


@app.get('/api/')
async def root():
    return {'name': 'LastZHood', 'status': 'online'}


@app.get('/api/status')
async def status():
    active = await local_sessions.active()
    return {'online': len({p['account_id'] for p in active}), 'simulation': 'local', 'capacity': 200, 'friendly_fire': True, 'map': 'Westfall', 'size': 1600, 'tick_rate': 20,
            'tick_ms': round(game.tick_ms, 2), 'tick_overruns': game.tick_overruns,
            'coalesced_states': sum(p['channel'].coalesced for p in game.players.values() if not p.get('bot'))}


@app.get('/api/bosses')
async def bosses_status():
    return [boss_snapshot(boss, time.monotonic()) for boss in game.bosses.values()]


@app.get('/api/world')
async def world():
    return WORLD


@app.get('/api/weapons')
async def weapons():
    return WEAPONS


@app.get('/api/leaderboard', response_model=list[Score])
async def leaderboard():
    return await db.scores.find({}, {'_id': 0}).sort('score', -1).limit(20).to_list(20)


@app.post('/api/auth/challenge', response_model=ChallengeResponse)
async def auth_challenge(body: ChallengeRequest):
    try:
        return await create_challenge(
            db, body.address, chain_id=body.chain_id, domain=body.domain, uri=body.uri)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))



@app.post('/api/auth/verify', response_model=WalletAuthResponse)
async def auth_verify(body: VerifyRequest, response: Response):
    try:
        res = await verify_signature(db, body.message, body.signature)
        response.set_cookie(
            key='deadzone_session',
            value=res['sessionToken'],
            httponly=True,
            secure=True,
            samesite='lax',
            max_age=7*86400
        )
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get('/api/auth/me')
async def auth_me(request: Request):
    token = request.cookies.get('deadzone_session') or request.headers.get('Authorization', '').replace('Bearer ', '')
    user = await get_session_account(db, token)
    if not user:
        return {'authenticated': False}
    return {'authenticated': True, 'address': user['address'], 'account': user['account'], 'progress': user['progress'], 'paid_access': user['paid_access'], 'fee_exempt': user['fee_exempt']}


@app.post('/api/auth/profile')
async def auth_profile(body: ProfileRequest, request: Request):
    token = request.cookies.get('deadzone_session') or request.headers.get('Authorization', '').replace('Bearer ', '')
    user = await get_session_account(db, token)
    if not user:
        raise HTTPException(status_code=401, detail='Authentication required')
    try:
        account = await create_or_update_profile(db, user['account_id'], body.nickname, body.skin)
        progress = await get_player_progress(db, user['account_id'])
        return {'success': True, 'account': account, 'progress': progress, 'paid_access': user['paid_access'], 'fee_exempt': user['fee_exempt']}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post('/api/auth/logout')
async def auth_logout(request: Request, response: Response):
    token = request.cookies.get('deadzone_session') or request.headers.get('Authorization', '').replace('Bearer ', '')
    await logout(db, token)
    response.delete_cookie('deadzone_session')
    return {'success': True}


class MarketSellRequest(BaseModel):
    category: str
    item_key: str
    amount: int = 1


class MarketSoldierBuyRequest(BaseModel):
    tier: int = 1


class MarketSoldierActivateRequest(BaseModel):
    tier: Optional[int] = None
    instance_id: Optional[str] = None

class MarketSoldierUpgradeRequest(BaseModel):
    instance_id: str


class MarketSoldierRenameRequest(BaseModel):
    instance_id: str
    nickname: str


class EquipmentCraftRequest(BaseModel):
    item_id: str


class EquipmentUpgradeRequest(BaseModel):
    item_id: str


class EquipmentEquipRequest(BaseModel):
    slot: str
    item_id: Optional[str] = None


class MaterialConvertRequest(BaseModel):
    source_id: str
    target_id: str


@app.get('/api/market/catalog')
async def market_catalog():
    from equipment import EQUIPMENT_CATALOG, EQUIPMENT_MATERIALS, SELL_PRICES
    from soldier import SOLDIER_CATALOG
    return {
        'equipment': EQUIPMENT_CATALOG,
        'materials': EQUIPMENT_MATERIALS,
        'sell_prices': SELL_PRICES,
        'soldiers': SOLDIER_CATALOG,
    }


async def _get_auth_target(request: Request):
    token = request.cookies.get('deadzone_session') or request.headers.get('Authorization', '').replace('Bearer ', '')
    user = await get_session_account(db, token)
    if not user:
        raise HTTPException(status_code=401, detail='Authentication required.')
    account_id = user['account_id']
    # Check if currently active in game
    live_player = next((p for p in game.players.values() if p.get('account_id') == account_id), None)
    if live_player:
        return account_id, live_player, True
    await game.wait_for_progress(account_id)
    prog = await get_player_progress(db, account_id)
    return account_id, prog, False


async def _persist_live_after_account_mutation(account_id, player, merge_fields=()):
    """Rebase the live actor's next CAS after an account-side DB mutation."""
    latest = await get_player_progress(db, account_id)
    for field in merge_fields:
        if field in latest:
            player[field] = copy.deepcopy(latest[field])
    player['revision'] = latest.get('revision', player.get('revision', 1))
    game.persist_progress(player)
    return latest


def _apply_market_manifest_to_live(player, order):
    applied = player.setdefault('applied_market_order_ids', [])
    order_id = order.get('order_id')
    if order_id in applied:
        return False
    manifest = order.get('manifest') or {}
    player['gold'] = int(player.get('gold', 0)) + int(manifest.get('gold', 0))
    eq_parts = player.setdefault('equipment_parts', {})
    for item, count in manifest.get('materials', {}).items():
        eq_parts[item] = int(eq_parts.get(item, 0)) + int(count)
    player.setdefault('weapon_parts', []).extend(
        create_weapon_part(part) for part, count in manifest.get('weapon_parts', {}).items() for _ in range(int(count)))
    for item in manifest.get('equipment_to_grant', []):
        if item not in player.setdefault('owned_equipment', []):
            player['owned_equipment'].append(item)
            player.setdefault('equipment_levels', {})[item] = 0
    badge = manifest.get('badge')
    if badge:
        badges = player.setdefault('unlocked_badges', [])
        if badge not in badges:
            badges.append(badge)
        player['active_badge'] = badge
    if manifest.get('name_color'):
        player['name_color'] = manifest['name_color']
    plan = order.get('grant_plan') or {}
    inbox = plan.get('inbox_items') or {}
    for item, quantity in manifest.get('items', {}).items():
        fit = max(0, int(quantity) - int(inbox.get(item, 0)))
        if item in ('medkit', 'faid'):
            player.setdefault('heal_items', {})[item] = int(player.get('heal_items', {}).get(item, 0)) + fit
        else:
            player.setdefault('consumables', {})[item] = int(player.get('consumables', {}).get(item, 0)) + fit
    if order.get('sku') == 'equipment_luck_2':
        for draw in order.get('box_results') or []:
            if draw.get('is_calibration'):
                cal = player.setdefault('calibration', {})
                cal[draw['item_id']] = int(cal.get(draw['item_id'], 0)) + 1
            else:
                eq_parts[draw['item_id']] = int(eq_parts.get(draw['item_id'], 0)) + 1
    if order_id:
        applied.append(order_id)
    return True


@app.post('/api/market/sell')
async def market_sell(body: MarketSellRequest, request: Request):
    account_id, target, is_live = await _get_auth_target(request)
    from equipment import execute_sell
    ok, msg, gold = execute_sell(target, body.category, body.item_key, body.amount)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    if is_live:
        game.persist_progress(target)
    else:
        await save_player_progress(db, account_id, target)
    return {'success': True, 'message': msg, 'gold_earned': gold, 'progress': target if not is_live else None}


def _check_soldier_owned(owned_list, tier):
    if not owned_list:
        return False
    t_str = str(tier).lower()
    return any(str(t).lower() in (t_str, f"soldier_s{t_str}") or t_str in (str(t).lower(), f"soldier_s{str(t).lower()}") for t in owned_list)

def _active_tier_id(tier):
    return f"soldier_s{int(str(tier).replace('soldier_s', ''))}"

def _sync_active_soldiers(player):
    from soldier import reconcile_soldier_roster
    reconcile_soldier_roster(game, player)


@app.post('/api/market/buy_soldier')
async def market_buy_soldier(body: MarketSoldierBuyRequest, request: Request):
    account_id, target, is_live = await _get_auth_target(request)
    from soldier import recruit_soldier
    ok, msg, _record = recruit_soldier(target)
    if not ok: raise HTTPException(status_code=400, detail=msg)
    if is_live:
        _sync_active_soldiers(target); game.persist_progress(target)
    else: await save_player_progress(db, account_id, target)
    return {'success': True, 'message': msg, 'progress': target if not is_live else None}
@app.post('/api/market/activate_soldier')
async def market_activate_soldier(body: MarketSoldierActivateRequest, request: Request):
    account_id, target, is_live = await _get_auth_target(request)
    from soldier import SOLDIER_CATALOG, create_soldier_instance, set_soldier_active
    if body.instance_id:
        ok, msg = set_soldier_active(target, body.instance_id, True)
        if not ok: raise HTTPException(status_code=400, detail=msg)
        if is_live: _sync_active_soldiers(target); game.persist_progress(target)
        else: await save_player_progress(db, account_id, target)
        return {'success': True, 'message': msg, 'progress': target if not is_live else None}
    if body.tier is None or body.tier == 0:
        target['active_soldier_tier'] = None
        target['active_soldier_tiers'] = []
        if is_live:
            _sync_active_soldiers(target)
            game.persist_progress(target)
        else:
            await save_player_progress(db, account_id, target)
        return {'success': True, 'message': 'Mercenary recalled.', 'progress': target if not is_live else None}

    if not _check_soldier_owned(target.get('owned_soldier_tiers', []), body.tier):
        raise HTTPException(status_code=400, detail='You do not own this mercenary.')
    tier_id = _active_tier_id(body.tier)
    active = target.setdefault('active_soldier_tiers', [])
    if tier_id not in active:
        if len(active) >= 5:
            raise HTTPException(status_code=400, detail='Maximum 5 mercenaries can be deployed.')
        active.append(tier_id)
    target['active_soldier_tier'] = active[0] if active else None
    if is_live:
        _sync_active_soldiers(target)
        game.persist_progress(target)
    else:
        await save_player_progress(db, account_id, target)
    return {'success': True, 'message': f"{SOLDIER_CATALOG[body.tier]['name']} deployed!", 'progress': target if not is_live else None}

@app.post('/api/market/upgrade_soldier')
async def market_upgrade_soldier(body: MarketSoldierUpgradeRequest, request: Request):
    account_id, target, is_live = await _get_auth_target(request)
    from soldier import upgrade_soldier
    ok, msg, _record = upgrade_soldier(target, body.instance_id)
    if not ok: raise HTTPException(status_code=400, detail=msg)
    if is_live: _sync_active_soldiers(target); game.persist_progress(target)
    else: await save_player_progress(db, account_id, target)
    return {'success': True, 'message': msg, 'progress': target if not is_live else None}


@app.post('/api/market/rename_soldier')
async def market_rename_soldier(body: MarketSoldierRenameRequest, request: Request):
    account_id, target, is_live = await _get_auth_target(request)
    from soldier import rename_soldier
    ok, msg, _record = rename_soldier(target, body.instance_id, body.nickname)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    if is_live:
        _sync_active_soldiers(target)
        game.persist_progress(target)
    else:
        await save_player_progress(db, account_id, target)
    return {'success': True, 'message': msg, 'progress': target if not is_live else None}


@app.post('/api/market/equipment_craft')
async def market_equipment_craft(body: EquipmentCraftRequest, request: Request):
    account_id, target, is_live = await _get_auth_target(request)
    from equipment import craft_equipment_item, calculate_player_equipment_stats
    ok, msg = craft_equipment_item(target, body.item_id)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    target['equipment_stats'] = calculate_player_equipment_stats(target.get('equipped_equipment', {}), target.get('equipment_levels', {}))
    if is_live:
        game.persist_progress(target)
    else:
        await save_player_progress(db, account_id, target)
    return {'success': True, 'message': msg, 'progress': target if not is_live else None}


@app.post('/api/market/equipment_upgrade')
async def market_equipment_upgrade(body: EquipmentUpgradeRequest, request: Request):
    account_id, target, is_live = await _get_auth_target(request)
    from equipment import upgrade_equipment_item, calculate_player_equipment_stats
    ok, msg = upgrade_equipment_item(target, body.item_id)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    target['equipment_stats'] = calculate_player_equipment_stats(target.get('equipped_equipment', {}), target.get('equipment_levels', {}))
    if is_live:
        game.persist_progress(target)
    else:
        await save_player_progress(db, account_id, target)
    return {'success': True, 'message': msg, 'progress': target if not is_live else None}


@app.post('/api/market/equipment_equip')
async def market_equipment_equip(body: EquipmentEquipRequest, request: Request):
    account_id, target, is_live = await _get_auth_target(request)
    from equipment import equip_equipment_item, calculate_player_equipment_stats
    ok, msg = equip_equipment_item(target, body.slot, body.item_id)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    target['equipment_stats'] = calculate_player_equipment_stats(target.get('equipped_equipment', {}), target.get('equipment_levels', {}))
    if is_live:
        game.persist_progress(target)
    else:
        await save_player_progress(db, account_id, target)
    return {'success': True, 'message': msg, 'progress': target if not is_live else None}


@app.post('/api/market/material_convert')
async def market_material_convert(body: MaterialConvertRequest, request: Request):
    account_id, target, is_live = await _get_auth_target(request)
    from equipment import convert_materials
    ok, msg = convert_materials(target, body.source_id, body.target_id)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    if is_live:
        game.persist_progress(target)
    else:
        await save_player_progress(db, account_id, target)
    return {'success': True, 'message': msg, 'progress': target if not is_live else None}


# ---------------------------------------------------------------------------
# Off-Game Market, VIP, Missions & Economy Endpoints (Section 2, 3, 6, 7, 8, 9, 13)
# ---------------------------------------------------------------------------

class CreateOrderRequest(BaseModel):
    sku: str
    request_id: Optional[str] = None


class SubmitOrderRequest(BaseModel):
    tx_hash: Optional[str] = None
    request_id: Optional[str] = None


class ClaimDeliveryRequest(BaseModel):
    request_id: Optional[str] = None


class StartMissionRequest(BaseModel):
    soldier_instance_id: str
    request_id: Optional[str] = None
    recall_active: bool = False


class ClaimMissionRequest(BaseModel):
    mission_id: str
    request_id: Optional[str] = None


class ClaimRewardPeriodRequest(BaseModel):
    period_id: Optional[str] = None
    request_id: Optional[str] = None


@app.get('/api/offgame-market/catalog')
async def get_offgame_market_catalog():
    from offgame_market import MARKET_CATALOG, LUCK_BOX_ODDS_TABLE, OFFGAME_MARKET_VERSION
    from market_payments import CHAIN_ID, TREASURY, CONFIRMATIONS
    return {
        'version': OFFGAME_MARKET_VERSION,
        'catalog': MARKET_CATALOG,
        'luck_box_odds': LUCK_BOX_ODDS_TABLE,
        'capabilities': {
            'purchase_enabled': True,
            'payment_mode': 'native_eth_quote',
            'chain_id': CHAIN_ID,
            'treasury': TREASURY,
            'confirmations_required': CONFIRMATIONS,
            'token_rewards_enabled': False,
            'missions_enabled': True,
            'vip_presets_enabled': False,
            'recolor_enabled': False,
            'disabled_reason_code': None,
        },
    }


@app.get('/api/account/economy')
async def get_account_economy(request: Request):
    account_id, target, is_live = await _get_auth_target(request)
    from offgame_market import get_vip_status, get_delivery_inbox
    vip_info = get_vip_status(target)
    inbox = await get_delivery_inbox(db, account_id)
    return {
        'account_id': account_id,
        'gold': target.get('gold', 0),
        'vip': vip_info,
        'active_badge': target.get('active_badge'),
        'unlocked_badges': target.get('unlocked_badges', []),
        'name_color': target.get('name_color'),
        'inbox_count': len([i for i in inbox if i.get('status') == 'pending']),
    }


@app.post('/api/offgame-market/orders')
async def create_market_order(body: CreateOrderRequest, request: Request):
    account_id, target, is_live = await _get_auth_target(request)
    from offgame_market import create_purchase_order, MARKET_CATALOG
    if body.sku not in MARKET_CATALOG:
        raise HTTPException(status_code=400, detail='Geçersiz SKU kodu.')
    try:
        if is_live:
            await game.flush_progress(target)
        order = await create_purchase_order(
            db=db,
            account_id=account_id,
            sku=body.sku,
            authenticated_wallet=account_id if account_id.startswith('0x') else None,
            request_id=body.request_id
        )
        from market_payments import create_quote
        quote = await create_quote(db, order)
        order['quote'] = quote
        order['status'] = 'awaiting_payment'
        await sync_db_to_file(db)
        return {'success': True, 'order': order}
    except Exception as e:
        log.exception('Could not create checkout quote')
        raise HTTPException(status_code=503, detail='PAYMENT_QUOTE_UNAVAILABLE')


@app.post('/api/offgame-market/orders/{order_id}/quote')
async def renew_market_order_quote(order_id: str, request: Request):
    account_id, _, _ = await _get_auth_target(request)
    order = await db.purchase_orders.find_one({'order_id': order_id, 'account_id': account_id, 'kind': {'$ne': 'access'}}, {'_id': 0})
    if not order:
        raise HTTPException(status_code=404, detail='ORDER_NOT_FOUND')
    if order.get('tx_hash') or order.get('status') not in ('created', 'awaiting_payment'):
        raise HTTPException(status_code=409, detail='ORDER_CANNOT_REQUOTE')
    from market_payments import create_quote
    try:
        quote = await create_quote(db, order)
        fresh = await db.purchase_orders.find_one({'order_id': order_id, 'account_id': account_id}, {'_id': 0})
        return {'success': True, 'order': fresh, 'quote': quote}
    except Exception:
        log.exception('Could not renew checkout quote')
        raise HTTPException(status_code=503, detail='PAYMENT_QUOTE_UNAVAILABLE')


@app.post('/api/offgame-market/orders/{order_id}/submit')
async def submit_market_order(order_id: str, body: SubmitOrderRequest, request: Request):
    account_id, live_target, is_live = await _get_auth_target(request)
    if not body.tx_hash:
        raise HTTPException(status_code=400, detail='TRANSACTION_HASH_REQUIRED')
    order = await db.purchase_orders.find_one({'order_id': order_id, 'account_id': account_id, 'kind': {'$ne': 'access'}}, {'_id': 0})
    if not order:
        raise HTTPException(status_code=404, detail='Order not found.')
    submitted_hash = body.tx_hash.lower()
    if order.get('tx_hash') and order['tx_hash'].lower() != submitted_hash:
        raise HTTPException(status_code=409, detail='ORDER_TRANSACTION_HASH_CONFLICT')
    if is_live:
        await game.flush_progress(live_target)
    from market_payments import verify_transaction, reserve_transaction_hash
    try:
        order = await reserve_transaction_hash(db, order, submitted_hash, account_id)
        if order.get('status') == 'fulfilled':
            if is_live and _apply_market_manifest_to_live(live_target, order):
                await _persist_live_after_account_mutation(
                    account_id, live_target,
                    merge_fields=('vip_until_utc', 'is_vip') if order.get('sku') == 'vip_30d' else ())
            return {'success': True, 'order': order, 'verified': True, 'status': 'paid',
                    'tx_hash': submitted_hash, 'chain_id': order.get('chain_id', 4663),
                    'confirmations': order.get('payment_confirmations', 0)}
        if order.get('status') == 'delivering' and order.get('payment_verified') is True:
            verification = {'verified': True, 'status': 'paid', 'tx_hash': submitted_hash,
                            'account_id': account_id, 'chain_id': order.get('chain_id', 4663),
                            'confirmations': order.get('payment_confirmations', 0)}
        else:
            verification = await verify_transaction(db, order, submitted_hash, account_id)
        if verification['status'] != 'paid':
            queued = await db.purchase_orders.update_one(
                {'order_id': order_id, 'account_id': account_id,
                 'status': {'$in': ['awaiting_payment', 'submitted', 'confirming']},
                 'tx_hash': order.get('tx_hash')},
                {'$set': {'status': verification['status'], 'tx_hash': body.tx_hash.lower(), 'chain_id': verification.get('chain_id', 4663)}})
            if queued.matched_count != 1:
                raise HTTPException(status_code=409, detail='ORDER_STATE_CONFLICT')
            await sync_db_to_file(db)
            return {'success': True, 'order': {'order_id': order_id, 'status': verification['status']}, **verification}
        from offgame_market import finalize_order_fulfillment
        final_order = await finalize_order_fulfillment(db, order_id, body.tx_hash.lower(), verified_payment=verification, authenticated_account=account_id)
        if is_live:
            _apply_market_manifest_to_live(live_target, final_order)
            await _persist_live_after_account_mutation(
                account_id, live_target,
                merge_fields=('vip_until_utc', 'is_vip') if final_order.get('sku') == 'vip_30d' else ())
        await sync_db_to_file(db)
        return {'success': True, 'order': final_order, **verification}
    except (ValueError, PermissionError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        log.exception('Payment verification could not complete')
        raise HTTPException(status_code=503, detail='PAYMENT_VERIFICATION_UNAVAILABLE')


@app.get('/api/offgame-market/orders/{order_id}')
async def get_market_order(order_id: str, request: Request):
    account_id, target, is_live = await _get_auth_target(request)
    order = await db.purchase_orders.find_one({'order_id': order_id, 'account_id': account_id}, {'_id': 0})
    if not order:
        raise HTTPException(status_code=404, detail='Sipariş bulunamadı.')
    return {'order': order}


@app.get('/api/offgame-market/orders')
async def list_market_orders(request: Request):
    account_id, target, is_live = await _get_auth_target(request)
    if db is None or not hasattr(db, 'purchase_orders'):
        raise HTTPException(status_code=503, detail='ORDER_STORAGE_UNAVAILABLE')
    docs = await db.purchase_orders.find({'account_id': account_id, 'kind': {'$ne': 'access'}}, {'_id': 0}).to_list(50)
    return {'orders': docs}


@app.post('/api/offgame-market/orders/{order_id}/reveal')
async def reveal_market_box(order_id: str, request: Request):
    account_id, target, is_live = await _get_auth_target(request)
    order = await db.purchase_orders.find_one({'order_id': order_id, 'account_id': account_id}, {'_id': 0})
    if not order:
        raise HTTPException(status_code=404, detail='Sipariş bulunamadı.')
    if order.get('sku') != 'equipment_luck_2':
        raise HTTPException(status_code=400, detail='Bu sipariş şans kutusu içermiyor.')
    if order.get('status') != 'fulfilled':
        raise HTTPException(status_code=400, detail='Sipariş henüz ödenmedi veya teslim edilmedi.')
    return {
        'success': True,
        'order_id': order_id,
        'box_results': order.get('box_results', []),
        'guaranteed_gold': order.get('manifest', {}).get('gold', 1000)
    }


@app.get('/api/delivery/inbox')
async def get_account_delivery_inbox(request: Request):
    account_id, target, is_live = await _get_auth_target(request)
    from offgame_market import get_delivery_inbox
    inbox = await get_delivery_inbox(db, account_id)
    return {'inbox': inbox}


@app.post('/api/delivery/{entitlement_id}/claim')
async def claim_delivery(entitlement_id: str, body: ClaimDeliveryRequest, request: Request):
    account_id, target, is_live = await _get_auth_target(request)
    from offgame_market import claim_delivery_item
    res = await claim_delivery_item(db, account_id, entitlement_id, request_id=body.request_id)
    if not res.get('success') and res.get('error_code') != 'BAG_FULL':
        raise HTTPException(status_code=400, detail=res.get('message', 'Teslimat yapılamadı.'))
    if is_live and res.get('success'):
        live_claims = target.setdefault('applied_delivery_claims', {})
        claim_id = res.get('claim_id')
        if claim_id and claim_id not in live_claims:
            live_claims[claim_id] = {'entitlement_id': entitlement_id,
                                     'claimed_items': dict(res.get('claimed_items') or {})}
            for item, count in (res.get('claimed_items') or {}).items():
                bag = target.setdefault('heal_items' if item in ('medkit', 'faid') else 'consumables', {})
                bag[item] = int(bag.get(item, 0)) + int(count)
            await _persist_live_after_account_mutation(account_id, target)
    return res


@app.get('/api/vip/status')
async def check_vip_status(request: Request):
    account_id, target, is_live = await _get_auth_target(request)
    from offgame_market import get_vip_status
    return get_vip_status(target)


# ---------------------------------------------------------------------------
# Soldier Missions & Period Rewards Endpoints (Section 6)
# ---------------------------------------------------------------------------

@app.get('/api/missions')
async def list_soldier_missions(request: Request):
    account_id, target, is_live = await _get_auth_target(request)
    from missions import get_account_missions
    missions = await get_account_missions(db, account_id)
    return {'missions': missions, 'server_time_utc': datetime.now(timezone.utc).isoformat()}


@app.get('/api/missions/roster')
async def get_mission_roster(request: Request):
    account_id, target, is_live = await _get_auth_target(request)
    from soldier import ensure_owned_soldiers, SOLDIER_CATALOG
    prior_roster_state = copy.deepcopy((target.get('owned_soldiers'), target.get('active_soldier_ids'), target.get('soldier_schema_version')))
    roster = ensure_owned_soldiers(target)
    soldiers = []
    for soldier in roster:
        tier_id = soldier.get('tier_id')
        spec = SOLDIER_CATALOG.get(tier_id) or {}
        soldiers.append({
            'instance_id': soldier.get('instance_id'), 'tier_id': tier_id,
            'nickname': soldier.get('nickname') or '', 'name': soldier.get('nickname') or spec.get('name') or tier_id,
            'runtime': dict(soldier.get('runtime') or {}),
            'current_mission_id': soldier.get('current_mission_id'),
            'is_active': soldier.get('instance_id') in (target.get('active_soldier_ids') or []),
        })
    if prior_roster_state != (target.get('owned_soldiers'), target.get('active_soldier_ids'), target.get('soldier_schema_version')):
        if is_live:
            game.persist_progress(target)
        else:
            await save_player_progress(db, account_id, target)
    return {'soldiers': soldiers}


@app.post('/api/missions/start')
async def start_mission(body: StartMissionRequest, request: Request):
    account_id, target, is_live = await _get_auth_target(request)
    if is_live:
        await game.flush_progress(target)
    from missions import start_soldier_mission
    res = await start_soldier_mission(
        db=db,
        account_id=account_id,
        soldier_instance_id=body.soldier_instance_id,
        request_id=body.request_id,
        recall_active=body.recall_active,
    )
    if not res.get('success'):
        raise HTTPException(status_code=400, detail=res.get('code', 'MISSION_START_FAILED'))
    if is_live:
        latest = await get_player_progress(db, account_id)
        target['active_soldier_ids'] = list(latest.get('active_soldier_ids') or [])
        for live_soldier in target.get('owned_soldiers') or []:
            persisted = next((s for s in latest.get('owned_soldiers') or [] if s.get('instance_id') == live_soldier.get('instance_id')), None)
            if persisted:
                live_soldier['current_mission_id'] = persisted.get('current_mission_id')
        _sync_active_soldiers(target)
        target['revision'] = latest.get('revision', target.get('revision', 1))
        game.persist_progress(target)
    return res


@app.post('/api/missions/claim')
async def claim_mission(body: ClaimMissionRequest, request: Request):
    account_id, target, is_live = await _get_auth_target(request)
    if is_live:
        await game.flush_progress(target)
    from missions import claim_soldier_mission
    res = await claim_soldier_mission(
        db=db,
        account_id=account_id,
        mission_id=body.mission_id,
        request_id=body.request_id
    )
    if not res.get('success'):
        raise HTTPException(status_code=400, detail=res.get('code', 'MISSION_CLAIM_FAILED'))
    if is_live:
        live_claims = target.setdefault('applied_mission_claims', {})
        if body.mission_id not in live_claims:
            target['gold'] = int(target.get('gold', 0)) + int(res.get('reward_gold', 0))
            live_claims[body.mission_id] = {'reward_gold': int(res.get('reward_gold', 0))}
            for live_soldier in target.get('owned_soldiers') or []:
                if live_soldier.get('current_mission_id') == body.mission_id:
                    live_soldier.pop('current_mission_id', None)
            await _persist_live_after_account_mutation(account_id, target)
            _sync_active_soldiers(target)
    return res


@app.get('/api/rewards/current')
async def get_current_rewards_period():
    return {
        'status': 'unconfigured',
        'message': 'Ekonomi yapılandırılmadı / Token claim kapalı',
        'budget_base_units': 0,
        'account_cap_base_units': 0,
        'policy_version': '1.0.0'
    }


@app.get('/api/rewards/history')
async def get_rewards_period_history():
    return {'history': []}


@app.post('/api/rewards/claim')
async def claim_rewards_period(body: ClaimRewardPeriodRequest):
    raise HTTPException(status_code=400, detail='Dönem token claim özelliği henüz yapılandırılmadı.')




@app.post('/api/join')
async def join(request: Request, body: JoinRequest):
    if body.weapon not in WEAPONS:
        raise HTTPException(422, 'Invalid weapon.')

    session_token = request.cookies.get('deadzone_session') or request.headers.get('Authorization', '').replace('Bearer ', '')
    user = await get_session_account(db, session_token) if session_token else None

    if not user:
        raise HTTPException(401, 'WALLET_SIGNATURE_REQUIRED')
    if not (user['paid_access'] or user['fee_exempt']):
        raise HTTPException(402, 'ONE_TIME_ACCESS_PAYMENT_REQUIRED')

    return await local_sessions.create(user, user['account'].get('skin') or body.skin)

# Legacy implementation retained for reference only; NOT registered as a route.
async def legacy_websocket(ws: WebSocket, token: str):
    session = pending.pop(token, None)
    if not session or session['expires'] < time.monotonic() or sum(not p.get('bot') for p in game.players.values()) >= 200:
        await ws.close(code=1008)
        return
    authenticated = await get_session_account(db, session.get('auth_token'))
    if (not authenticated or authenticated['account_id'] != session.get('account_id')
            or not authenticated['paid_access']):
        await ws.close(code=1008)
        return
    await ws.accept()
    # A browser can reconnect while its prior socket is still flushing. Read
    # only after that account's ordered persistence chain completes.
    if session.get('account_id'):
        await game.wait_for_progress(session['account_id'])
        session['progress'] = await get_player_progress(db, session['account_id'])
    player = await game.admit_player(session, ws)
    if player is None:
        await ws.close(code=1013, reason='Server is full.')
        return
    try:
        await ws.send_json({'type': 'welcome', 'id': player['id']})
        player['channel'].start()
        while True:
            data = await ws.receive_json()
            if not isinstance(data, dict):
                continue
            if data.get('type') == 'ping':
                await game.send(player, {'type': 'pong', 'time': data.get('time')})
            elif data.get('type') == 'input':
                game.set_input(player, data)
            elif data.get('type') == 'equip':
                if not equip_weapon(player, data.get('weapon')):
                    await game.send(player, {'type': 'action_error', 'message': 'The weapon could not be changed. Try again shortly.'})
                else:
                    game.persist_progress(player)
            elif data.get('type') == 'use_heal':
                use_heal_item(game, player, data.get('item'), time.monotonic())
                game.persist_progress(player)
            elif data.get('type') == 'allocate_stat':
                allocate_stat(game, player, data.get('stat'))
                game.persist_progress(player)
            elif data.get('type') == 'craft':
                if not craft_upgrade(game, player, data.get('recipe'), data.get('weapon'), time.monotonic()):
                    await game.send(player, {'type': 'action_error', 'message': 'Crafting failed. Check your parts and try again.'})
                else:
                    game.persist_progress(player)
            elif data.get('type') == 'equipment_craft':
                from equipment import craft_equipment_item, calculate_player_equipment_stats
                ok, msg = craft_equipment_item(player, data.get('item_id'))
                player['equipment_stats'] = calculate_player_equipment_stats(player.get('equipped_equipment', {}), player.get('equipment_levels', {}))
                if not ok:
                    await game.send(player, {'type': 'action_error', 'message': msg})
                else:
                    game.persist_progress(player)
                    await game.send(player, {'type': 'action_success', 'message': msg})
            elif data.get('type') == 'equipment_upgrade':
                from equipment import upgrade_equipment_item, calculate_player_equipment_stats
                ok, msg = upgrade_equipment_item(player, data.get('item_id'))
                player['equipment_stats'] = calculate_player_equipment_stats(player.get('equipped_equipment', {}), player.get('equipment_levels', {}))
                if not ok:
                    await game.send(player, {'type': 'action_error', 'message': msg})
                else:
                    game.persist_progress(player)
                    await game.send(player, {'type': 'action_success', 'message': msg})
            elif data.get('type') == 'equipment_equip':
                from equipment import equip_equipment_item, calculate_player_equipment_stats
                ok, msg = equip_equipment_item(player, data.get('slot'), data.get('item_id'))
                player['equipment_stats'] = calculate_player_equipment_stats(player.get('equipped_equipment', {}), player.get('equipment_levels', {}))
                if not ok:
                    await game.send(player, {'type': 'action_error', 'message': msg})
                else:
                    game.persist_progress(player)
                    await game.send(player, {'type': 'action_success', 'message': msg})
            elif data.get('type') == 'use_consumable':
                ok, msg = use_consumable(game, player, data.get('item_id'), data.get('request_id'))
                if ok:
                    game.persist_progress(player)
                    await game.send(player, {'type': 'action_success', 'message': msg})
                else:
                    await game.send(player, {'type': 'action_error', 'message': msg})
            elif data.get('type') == 'material_convert':
                from equipment import convert_materials
                ok, msg = convert_materials(player, data.get('source_id'), data.get('target_id'))
                if not ok:
                    await game.send(player, {'type': 'action_error', 'message': msg})
                else:
                    game.persist_progress(player)
                    await game.send(player, {'type': 'action_success', 'message': msg})
            elif data.get('type') == 'soldier_buy':
                from soldier import recruit_soldier
                ok, msg, _record = recruit_soldier(player)
                if ok:
                    _sync_active_soldiers(player); game.persist_progress(player)
                    await game.send(player, {'type': 'action_success', 'message': msg})
                else: await game.send(player, {'type': 'action_error', 'message': msg})
            elif data.get('type') == 'soldier_activate':
                instance_id = data.get('instance_id')
                if not isinstance(instance_id, str) or not instance_id:
                    await game.send(player, {'type': 'action_error', 'message': 'Mercenary ID is required.'})
                    continue
                from soldier import set_soldier_active
                ok, msg = set_soldier_active(player, instance_id, True)
                if ok:
                    _sync_active_soldiers(player); game.persist_progress(player)
                    await game.send(player, {'type': 'action_success', 'message': msg})
                else: await game.send(player, {'type': 'action_error', 'message': msg})
            elif data.get('type') == 'soldier_deactivate':
                instance_id = data.get('instance_id')
                if not isinstance(instance_id, str) or not instance_id:
                    await game.send(player, {'type': 'action_error', 'message': 'Mercenary ID is required.'})
                    continue
                from soldier import set_soldier_active
                ok, msg = set_soldier_active(player, instance_id, False)
                if ok:
                    _sync_active_soldiers(player); game.persist_progress(player)
                    await game.send(player, {'type': 'action_success', 'message': msg})
                else: await game.send(player, {'type': 'action_error', 'message': msg})
            elif data.get('type') == 'soldier_upgrade':
                from soldier import upgrade_soldier
                ok, msg, _record = upgrade_soldier(player, data.get('instance_id'))
                if ok:
                    _sync_active_soldiers(player); game.persist_progress(player)
                    await game.send(player, {'type': 'action_success', 'message': msg})
                else: await game.send(player, {'type': 'action_error', 'message': msg})
            elif data.get('type') == 'soldier_rename':
                from soldier import rename_soldier
                ok, msg, _record = rename_soldier(player, data.get('instance_id'), data.get('nickname'))
                if ok:
                    _sync_active_soldiers(player); game.persist_progress(player)
                    await game.send(player, {'type': 'action_success', 'message': msg})
                else: await game.send(player, {'type': 'action_error', 'message': msg})
            elif data.get('type') == 'sell_item':
                from equipment import execute_sell
                ok, msg, gold = execute_sell(player, data.get('category'), data.get('item_key'), int(data.get('amount', 1)))
                if not ok:
                    await game.send(player, {'type': 'action_error', 'message': msg})
                else:
                    game.persist_progress(player)
                    await game.send(player, {'type': 'action_success', 'message': msg, 'gold_earned': gold})
            elif data.get('type') == 'alliance_create':
                if not game.create_alliance(player, data.get('name')):
                    await game.send(player, {'type': 'action_error', 'message': 'Alliance names use 2–18 letters, numbers, spaces, or hyphens.'})
            elif data.get('type') == 'alliance_join':
                if not game.join_alliance(player, data.get('code')):
                    await game.send(player, {'type': 'action_error', 'message': 'Alliance code is invalid or the alliance is full.'})
            elif data.get('type') == 'alliance_leave':
                game.leave_alliance(player)
            elif data.get('type') == 'alliance_friendly_fire':
                if not game.set_alliance_friendly_fire(player, data.get('enabled')):
                    await game.send(player, {'type': 'action_error', 'message': 'Only the alliance leader can change friendly fire.'})
            elif data.get('type') == 'respawn' and player['hp'] <= 0:
                if time.monotonic()-player['died_at'] >= 10:
                    await save_score(player)
                    game.respawn(player)
    except (WebSocketDisconnect, RuntimeError, ValueError):
        pass
    finally:
        game.leave_alliance(player)
        # Queue and await an immutable save while companion actors still exist.
        # This closes the F5/rejoin window where an older periodic write could
        # otherwise overwrite a just-recorded recovery deadline.
        try:
            await game.flush_progress(player)
        finally:
            # A persistence outage must not leave a disconnected actor online.
            # Actor IDs are individual soldier instance IDs, not the owner ID.
            for actor_id, soldier in list(game.soldiers.items()):
                if soldier.get('owner_id') == player['id']:
                    game.soldiers.pop(actor_id, None)
            game.players.pop(player['id'], None)
            await player['channel'].stop()
            await save_score(player)

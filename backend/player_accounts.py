"""DEADZONE - Player Account & Persistent Progression Model (MongoDB)

Handles persistent EVM player accounts, profiles, and progression.
Progression persists across sessions, server restarts, and deaths.
"""

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from eth_utils import to_checksum_address
from weapon_parts import normalize_weapon_parts

log = logging.getLogger('deadzone.accounts')

LOCAL_STORAGE_FILE = Path(__file__).parent / ".local_storage.json"

DEFAULT_STATS = {
    'reload_speed': 0,
    'movement_speed': 0,
    'heal_multiplier': 0,
    'max_hp': 0,
    'stamina': 0
}

DEFAULT_WEAPONS_PROGRESS = {
    'glock18': {'ammo': 17, 'reserve': 102}
}


def create_initial_progress(account_id: str, env: str = 'robinhood') -> Dict[str, Any]:
    now_iso = datetime.now(timezone.utc).isoformat()
    return {
        'account_id': account_id.lower(),
        'environment': env,
        'gold': 150,
        'xp': 0,
        'level': 1,
        'stat_points': 0,
        'stats': dict(DEFAULT_STATS),
        'heal_items': {'medkit': 1, 'faid': 2},
        'consumables': {'energy_drink': 0},
        'energy_drink_expires_at': None,
        'unlocked_weapons': ['glock18'],
        'equipped_weapon': 'glock18',
        'weapons': dict(DEFAULT_WEAPONS_PROGRESS),
        'inventory': {
            'glock18': {'ammo': 17, 'reserve': 102}
        },
        'weapon_parts': [],
        'weapon_upgrades': {},
        'equipped_equipment': {'head': None, 'body': None, 'legs': None, 'hands': None, 'feet': None, 'backpack': None},
        'owned_equipment': [],
        'equipment_levels': {},
        'equipment_parts': {},
        'calibration': {'calibration_t1': 0, 'calibration_t2': 0, 'calibration_t3': 0},
        'calibration_progress': {'1': 0, '2': 0},
        'owned_soldier_tiers': [],
        'active_soldier_tier': None,
        'active_soldier_tiers': [],
        'owned_soldiers': [],
        'active_soldier_ids': [],
        'soldier_schema_version': 1,
        'total_score': 0,
        'kills': 0,
        'pvp': 0,
        'revision': 1,
        'updated_at': now_iso,
    }


def create_all_items_progress(account_id: str, env: str = 'robinhood') -> Dict[str, Any]:
    from world import WEAPONS
    from equipment import EQUIPMENT_CATALOG, EQUIPMENT_MATERIALS
    all_weapons = list(WEAPONS.keys())
    full_inventory = {
        w: {'ammo': WEAPONS[w]['mag'], 'reserve': WEAPONS[w]['reserve'] * 5}
        for w in all_weapons
    }
    weapon_parts = []
    # Tier 1 parts
    for p in ['barrel_common', 'grip_common', 'stock_common', 'spring_common']:
        weapon_parts.extend([{'id': p, 'tier': 1} for _ in range(25)])
    # Tier 2 parts
    for p in ['barrel_uncommon', 'receiver_uncommon', 'grip_uncommon', 'stock_uncommon']:
        weapon_parts.extend([{'id': p, 'tier': 2} for _ in range(25)])
    # Tier 3 parts
    for p in ['barrel_rare', 'receiver_rare', 'optic_rare', 'suppressor_rare']:
        weapon_parts.extend([{'id': p, 'tier': 3} for _ in range(25)])

    # Full upgrades for all weapons
    weapon_upgrades = {
        w: {
            'damage': 3,
            'range': 2,
            'mag': 2,
            'reload': 2,
            'optic': 1,
            'suppressor': 1,
        }
        for w in all_weapons
    }

    all_eq_ids = list(EQUIPMENT_CATALOG.keys())
    eq_parts = {k: 50 for k in EQUIPMENT_MATERIALS.keys() if 'calibration' not in k}

    now_iso = datetime.now(timezone.utc).isoformat()
    return {
        'account_id': account_id.lower(),
        'environment': env,
        'gold': 250000,
        'xp': 150000,
        'level': 35,
        'stat_points': 50,
        'stats': {
            'reload_speed': 5,
            'movement_speed': 5,
            'heal_multiplier': 5,
            'max_hp': 5,
            'stamina': 5
        },
        'heal_items': {'medkit': 50, 'faid': 50},
        'consumables': {'energy_drink': 10},
        'energy_drink_expires_at': None,
        'unlocked_weapons': all_weapons,
        'equipped_weapon': 'ak47',
        'weapons': full_inventory,
        'inventory': full_inventory,
        'weapon_parts': weapon_parts,
        'weapon_upgrades': weapon_upgrades,
        'equipped_equipment': {
            'head': 'helmet_t3',
            'body': 'vest_t3',
            'legs': 'legs_t3',
            'hands': 'hands_t3',
            'feet': 'feet_t3',
            'backpack': 'backpack_t3'
        },
        'owned_equipment': all_eq_ids,
        'equipment_levels': {eq_id: 2 for eq_id in all_eq_ids},
        'equipment_parts': eq_parts,
        'calibration': {'calibration_t1': 50, 'calibration_t2': 50, 'calibration_t3': 50},
        'calibration_progress': {'1': 0, '2': 0},
        'owned_soldier_tiers': ['soldier_s1', 'soldier_s2', 'soldier_s3', 'soldier_s4', 'soldier_s5'],
        'active_soldier_tier': 'soldier_s5',
        'active_soldier_tiers': ['soldier_s1', 'soldier_s2', 'soldier_s3', 'soldier_s4', 'soldier_s5'],
        # The test profile deliberately starts empty in the canonical field so
        # legacy tiers migrate once; normal saves retain generated IDs.
        'owned_soldiers': None,
        'active_soldier_ids': None,
        'total_score': 50000,
        'kills': 100,
        'pvp': 10,
        'revision': 1,
        'updated_at': now_iso,
    }


async def sync_db_from_file(db):
    if not LOCAL_STORAGE_FILE.exists():
        return
    try:
        with open(LOCAL_STORAGE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for doc in data.get('player_accounts', []):
            await db.player_accounts.update_one({'account_id': doc['account_id']}, {'$setOnInsert': doc}, upsert=True)
        for doc in data.get('player_progress', []):
            await db.player_progress.update_one({'account_id': doc['account_id']}, {'$setOnInsert': doc}, upsert=True)
        for doc in data.get('auth_sessions', []):
            await db.auth_sessions.update_one({'session_token': doc['session_token']}, {'$setOnInsert': doc}, upsert=True)
        for collection_name, key in [('purchase_orders', 'order_id'), ('access_entitlements', 'account_id'), ('delivery_inbox', 'entitlement_id'), ('soldier_missions', 'mission_id'), ('economy_ledger', 'transaction_id')]:
            for doc in data.get(collection_name, []):
                await getattr(db, collection_name).update_one({key: doc[key]}, {'$setOnInsert': doc}, upsert=True)
        log.info(f'Loaded persistent storage from {LOCAL_STORAGE_FILE}')
    except Exception as e:
        log.warning(f'Failed to load local storage: {e}')


async def sync_db_to_file(db):
    try:
        accounts = await db.player_accounts.find({}, {'_id': 0}).to_list(1000)
        progress = await db.player_progress.find({}, {'_id': 0}).to_list(1000)
        sessions = await db.auth_sessions.find({}, {'_id': 0}).to_list(1000)
        payload = {
            'player_accounts': accounts,
            'player_progress': progress,
            'auth_sessions': sessions,
            'purchase_orders': await db.purchase_orders.find({}, {'_id': 0}).to_list(10000),
            'access_entitlements': await db.access_entitlements.find({}, {'_id': 0}).to_list(10000),
            'delivery_inbox': await db.delivery_inbox.find({}, {'_id': 0}).to_list(10000),
            'soldier_missions': await db.soldier_missions.find({}, {'_id': 0}).to_list(10000),
            'economy_ledger': await db.economy_ledger.find({}, {'_id': 0}).to_list(10000),
            'saved_at': datetime.now(timezone.utc).isoformat()
        }
        with open(LOCAL_STORAGE_FILE, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log.warning(f'Failed to dump local storage: {e}')


async def setup_account_indexes(db):
    """Ensures unique and query indexes on player accounts and progress."""
    try:
        await db.player_accounts.create_index([('account_id', 1)], unique=True)
        await db.player_accounts.create_index([('normalized_nickname', 1)], unique=True, sparse=True)
        await db.player_progress.create_index([('account_id', 1)], unique=True)
        await db.purchase_orders.create_index([('account_id', 1), ('request_id', 1)], unique=True)
        await db.purchase_orders.create_index([('order_id', 1)], unique=True)
        await db.purchase_orders.create_index([('chain_id', 1), ('tx_hash', 1)], unique=True,
            partialFilterExpression={'tx_hash': {'$type': 'string'}})
        await db.soldier_missions.create_index([('account_id', 1), ('request_id', 1)], unique=True, sparse=True)
        await db.soldier_missions.create_index([('account_id', 1), ('soldier_instance_id', 1), ('status', 1)])
        await db.soldier_missions.create_index([('account_id', 1), ('soldier_instance_id', 1)], unique=True,
            partialFilterExpression={'status': 'active'})
        await db.economy_ledger.create_index([('request_id', 1)], unique=True)
        await db.delivery_inbox.create_index([('entitlement_id', 1)], unique=True)
        await db.soldier_missions.create_index([('mission_id', 1)], unique=True)
        await db.auth_challenges.create_index([('nonce', 1)], unique=True)
        await db.auth_challenges.create_index([('expires_at', 1)], expireAfterSeconds=0)
        await db.auth_sessions.create_index([('session_token', 1)], unique=True)
        await db.auth_sessions.create_index([('expires_at', 1)], expireAfterSeconds=0)
        log.info('Player account and session indexes established.')
    except Exception as e:
        log.warning(f'Index creation warning (may already exist or mock): {e}')

    await sync_db_from_file(db)

    # Seed the special development profile only once.  Its saved progress is
    # player state, so replacing it at every process start discards roster
    # instance ids, upgrades, inventory, and currency.
    dev_user = await db.player_accounts.find_one({'normalized_nickname': {'$in': ['lastz', 'babasiken31']}})
    if dev_user:
        dev_id = dev_user['account_id']
        if not await db.player_progress.find_one({'account_id': dev_id}):
            dev_prog = create_all_items_progress(dev_id)
            await db.player_progress.update_one({'account_id': dev_id}, {'$set': dev_prog}, upsert=True)
    elif await db.player_accounts.find_one({'account_id': '0x55c7d12daa84a74859e636cd53a48ced3d3cbd88'}):
        baba_id = '0x55c7d12daa84a74859e636cd53a48ced3d3cbd88'
        if not await db.player_progress.find_one({'account_id': baba_id}):
            baba_prog = create_all_items_progress(baba_id)
            await db.player_progress.update_one({'account_id': baba_id}, {'$set': baba_prog}, upsert=True)
    await sync_db_to_file(db)


async def get_account_by_address(db, address: str) -> Optional[Dict[str, Any]]:
    account_id = address.lower()
    return await db.player_accounts.find_one({'account_id': account_id}, {'_id': 0})


async def get_account_by_nickname(db, nickname: str) -> Optional[Dict[str, Any]]:
    norm = nickname.strip().lower()
    return await db.player_accounts.find_one({'normalized_nickname': norm}, {'_id': 0})


async def create_or_update_profile(db, address: str, nickname: str, skin: str = 'soldier') -> Dict[str, Any]:
    account_id = address.lower()
    clean_name = nickname.strip()
    norm_name = clean_name.lower()
    if len(clean_name) < 2 or len(clean_name) > 18:
        raise ValueError('Nickname must be between 2 and 18 characters.')

    # Check if another account holds this nickname
    existing = await db.player_accounts.find_one({'normalized_nickname': norm_name, 'account_id': {'$ne': account_id}})
    if existing:
        raise ValueError('This call sign is already registered by another survivor.')

    now_iso = datetime.now(timezone.utc).isoformat()
    checksum_addr = to_checksum_address(account_id)

    account_doc = {
        'account_id': account_id,
        'address': checksum_addr,
        'nickname': clean_name,
        'normalized_nickname': norm_name,
        'skin': skin or 'soldier',
        'last_login_at': now_iso,
        'schema_version': 1,
    }

    # Upsert account
    await db.player_accounts.update_one(
        {'account_id': account_id},
        {
            '$set': account_doc,
            '$setOnInsert': {'created_at': now_iso}
        },
        upsert=True
    )

    # Ensure progress document exists
    existing_progress = await db.player_progress.find_one({'account_id': account_id})
    if norm_name in ('lastz', 'babasiken31') and not existing_progress:
        init_prog = create_all_items_progress(account_id)
        await db.player_progress.update_one({'account_id': account_id}, {'$set': init_prog}, upsert=True)
    elif not existing_progress:
        init_prog = create_initial_progress(account_id)
        await db.player_progress.insert_one(init_prog)

    await sync_db_to_file(db)
    return await db.player_accounts.find_one({'account_id': account_id}, {'_id': 0})


async def get_player_progress(db, account_id: str) -> Dict[str, Any]:
    acc_id = account_id.lower()
    acc = await db.player_accounts.find_one({'account_id': acc_id})
    nick = (acc.get('nickname') or '').lower() if acc else ''

    if nick in ('lastz', 'babasiken31') or acc_id == '0x55c7d12daa84a74859e636cd53a48ced3d3cbd88':
        prog = await db.player_progress.find_one({'account_id': acc_id}, {'_id': 0})
        if not prog:
            prog = create_all_items_progress(acc_id)
            await db.player_progress.update_one({'account_id': acc_id}, {'$set': prog}, upsert=True)
            await sync_db_to_file(db)
        prog['weapon_parts'] = normalize_weapon_parts(prog.get('weapon_parts'))
        return prog

    prog = await db.player_progress.find_one({'account_id': acc_id}, {'_id': 0})
    if not prog:
        prog = create_initial_progress(acc_id)
        await db.player_progress.update_one({'account_id': acc_id}, {'$set': prog}, upsert=True)
        await sync_db_to_file(db)
    prog['weapon_parts'] = normalize_weapon_parts(prog.get('weapon_parts'))
    return prog


async def save_player_progress(db, account_id: str, progress_data: Dict[str, Any], backup=True):
    acc_id = account_id.lower()
    now_iso = datetime.now(timezone.utc).isoformat()
    progress_data['updated_at'] = now_iso
    progress_data['account_id'] = acc_id
    if 'weapon_parts' in progress_data:
        progress_data['weapon_parts'] = normalize_weapon_parts(progress_data['weapon_parts'])

    expected_revision = int(progress_data.get('revision', 1))
    persisted_fields = dict(progress_data)
    persisted_fields.pop('revision', None)
    result = await db.player_progress.update_one(
        {'account_id': acc_id, 'revision': expected_revision},
        {'$set': persisted_fields, '$inc': {'revision': 1}},
    )
    if result.matched_count != 1 and expected_revision == 1:
        result = await db.player_progress.update_one(
            {'account_id': acc_id, 'revision': {'$exists': False}},
            {'$set': {**persisted_fields, 'revision': expected_revision + 1}},
        )
    if result.matched_count != 1:
        # Never upsert a stale snapshot: that can recreate a deleted account or
        # overwrite a newer game/economy write after a restart or reconnect.
        raise RuntimeError('progress_revision_conflict')
    progress_data['revision'] = expected_revision + 1
    if backup:
        await sync_db_to_file(db)
    return progress_data


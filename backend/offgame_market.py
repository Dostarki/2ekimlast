import uuid
import secrets
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple

from economy import record_economy_ledger, mutate_gold_atomic

log = logging.getLogger(__name__)

OFFGAME_MARKET_VERSION = "1.0.0"

# Carrying capacity limits in active player bag
INVENTORY_LIMITS = {
    'medkit': 3,
    'faid': 5,
    'energy_drink': 10
}

# Duplicate equipment fallback pieces (Section 3)
EQUIPMENT_FALLBACKS = {
    'helmet_t1': {'fabric_t1': 2, 'plate_t1': 2, 'binding_t1': 1},
    'hands_t1': {'fabric_t1': 2, 'plate_t1': 2, 'binding_t1': 1},
    'vest_t1': {'fabric_t1': 3, 'plate_t1': 3, 'binding_t1': 2},
}

# Equipment luck box 15 materials and basis points (Section 13)
LUCK_BOX_ODDS_TABLE = [
    {'item_id': 'fabric_t1', 'bps': 1700, 'name': 'Kumaş T1', 'tier': 1, 'is_calibration': False},
    {'item_id': 'plate_t1', 'bps': 1700, 'name': 'Plaka T1', 'tier': 1, 'is_calibration': False},
    {'item_id': 'binding_t1', 'bps': 1700, 'name': 'Bağlantı T1', 'tier': 1, 'is_calibration': False},
    {'item_id': 'mechanism_t1', 'bps': 1700, 'name': 'Mekanizma T1', 'tier': 1, 'is_calibration': False},
    {'item_id': 'calibration_t1', 'bps': 400, 'name': 'Kalibrasyon T1', 'tier': 1, 'is_calibration': True},

    {'item_id': 'fabric_t2', 'bps': 550, 'name': 'Kumaş T2', 'tier': 2, 'is_calibration': False},
    {'item_id': 'plate_t2', 'bps': 550, 'name': 'Plaka T2', 'tier': 2, 'is_calibration': False},
    {'item_id': 'binding_t2', 'bps': 550, 'name': 'Bağlantı T2', 'tier': 2, 'is_calibration': False},
    {'item_id': 'mechanism_t2', 'bps': 550, 'name': 'Mekanizma T2', 'tier': 2, 'is_calibration': False},
    {'item_id': 'calibration_t2', 'bps': 100, 'name': 'Kalibrasyon T2', 'tier': 2, 'is_calibration': True},

    {'item_id': 'fabric_t3', 'bps': 110, 'name': 'Kumaş T3', 'tier': 3, 'is_calibration': False},
    {'item_id': 'plate_t3', 'bps': 110, 'name': 'Plaka T3', 'tier': 3, 'is_calibration': False},
    {'item_id': 'binding_t3', 'bps': 110, 'name': 'Bağlantı T3', 'tier': 3, 'is_calibration': False},
    {'item_id': 'mechanism_t3', 'bps': 110, 'name': 'Mekanizma T3', 'tier': 3, 'is_calibration': False},
    {'item_id': 'calibration_t3', 'bps': 60, 'name': 'Kalibrasyon T3', 'tier': 3, 'is_calibration': True},
]

# Off-Game Market Catalog (Section 3, 7, 13)
MARKET_CATALOG: Dict[str, Dict[str, Any]] = {
    'pack_field': {
        'sku': 'pack_field',
        'name': 'Saha Paketi',
        'cents': 200,
        'usd_str': '$2',
        'gold': 1000,
        'badge': 'SAHA',
        'name_color': '#c8d6a0',
        'recolor_eligible': False,
        'guaranteed_items': {'medkit': 1, 'faid': 2, 'energy_drink': 1},
        'equipment_materials': {'fabric_t1': 2, 'plate_t1': 2, 'binding_t1': 2, 'mechanism_t1': 1},
        'weapon_parts': {'barrel_common': 1, 'stock_common': 1},
        'guaranteed_equipment': {},
        'description': '1000 Gold, ilk yardım ve T1 başlangıç materyalleri. SAHA rozeti ve isim rengi.',
    },
    'pack_supply': {
        'sku': 'pack_supply',
        'name': 'İkmal Paketi',
        'cents': 400,
        'usd_str': '$4',
        'gold': 2000,
        'badge': 'İKMAL',
        'name_color': '#82ca9d',
        'recolor_eligible': False,
        'guaranteed_items': {'medkit': 2, 'faid': 3, 'energy_drink': 2},
        'equipment_materials': {'fabric_t1': 4, 'plate_t1': 4, 'binding_t1': 3, 'mechanism_t1': 2},
        'weapon_parts': {'barrel_common': 2, 'stock_common': 2, 'grip_common': 1, 'spring_common': 1},
        'guaranteed_equipment': {'helmet_t1': 1},
        'description': '2000 Gold, T1 Kask (+0), ikmal tıbbiye ve silah parçaları. İKMAL rozeti ve isim rengi.',
    },
    'pack_operator': {
        'sku': 'pack_operator',
        'name': 'Operatör Paketi',
        'cents': 600,
        'usd_str': '$6',
        'gold': 3500,
        'badge': 'OPERATÖR',
        'name_color': '#d5bf83',
        'recolor_eligible': True,
        'guaranteed_items': {'medkit': 3, 'faid': 4, 'energy_drink': 3},
        'equipment_materials': {'fabric_t1': 6, 'plate_t1': 6, 'binding_t1': 4, 'mechanism_t1': 3},
        'weapon_parts': {'barrel_common': 3, 'stock_common': 3, 'grip_common': 2, 'spring_common': 2},
        'guaranteed_equipment': {'helmet_t1': 1, 'hands_t1': 1},
        'description': '3500 Gold, T1 Kask ve Eldiven (+0), OPERATÖR rozeti ve model recolor hakkı.',
    },
    'pack_outpost': {
        'sku': 'pack_outpost',
        'name': 'Karakol Paketi',
        'cents': 1000,
        'usd_str': '$10',
        'gold': 6000,
        'badge': 'KARAKOL',
        'name_color': '#d95845',
        'recolor_eligible': True,
        'guaranteed_items': {'medkit': 4, 'faid': 6, 'energy_drink': 4},
        'equipment_materials': {'fabric_t1': 10, 'plate_t1': 10, 'binding_t1': 6, 'mechanism_t1': 4},
        'weapon_parts': {'barrel_common': 4, 'stock_common': 4, 'grip_common': 3, 'spring_common': 3},
        'guaranteed_equipment': {'helmet_t1': 1, 'vest_t1': 1, 'hands_t1': 1},
        'description': '6000 Gold, T1 Kask, Yelek ve Eldiven (+0), zengin mühimmat, KARAKOL rozeti ve recolor hakkı.',
    },
    'equipment_luck_2': {
        'sku': 'equipment_luck_2',
        'name': 'Ekipman Parçası Şans Kutusu',
        'cents': 200,
        'usd_str': '$2',
        'gold': 1000,
        'badge': 'ŞANS KUTUSU',
        'name_color': '#a78bfa',
        'recolor_eligible': False,
        'draw_count': 5,
        'guaranteed_items': {},
        'equipment_materials': {},
        'weapon_parts': {},
        'guaranteed_equipment': {},
        'description': 'Garantili 1000 Gold + 5 bağımsız çekim. T1/T2/T3 zırh malzemeleri ve nadir kalibrasyon parçaları.',
    },
    'vip_30d': {
        'sku': 'vip_30d',
        'name': 'VIP Üyelik (30 Gün)',
        'cents': 500,
        'usd_str': '$5',
        'gold': 0,
        'badge': 'VIP',
        'name_color': '#eab308',
        'recolor_eligible': False,
        'duration_days': 30,
        'perks': [
            '+%10 Aktif PvE Gold Bonusu',
            'VIP Özel İsim Rozeti ve Rengi',
            '3 Kayıtlı Loadout Yuvası'
        ],
        'nft_notice': "NFT satışları açılınca NFT'ye sahip üyeler, NFT'yi elinde tuttukları süre boyunca VIP sayılacaklar.",
        'description': '30 Gün boyunca aktif PvE gold kredisine +%10 bonus, 3 kayıtlı loadout ve VIP taktiksel rozeti.',
    }
}

# In-memory orders and deliveries store
_PURCHASE_ORDERS: Dict[str, Dict[str, Any]] = {}
_DELIVERY_INBOX: Dict[str, List[Dict[str, Any]]] = {}  # account_id -> [entitlements]


def roll_luck_box_draws(count: int = 5) -> List[Dict[str, Any]]:
    """Performs CSPRNG draws using secrets.randbelow(10000) adhering to Section 13."""
    results = []
    for idx in range(count):
        roll = secrets.randbelow(10000)
        accum = 0
        selected = LUCK_BOX_ODDS_TABLE[0]
        for opt in LUCK_BOX_ODDS_TABLE:
            accum += opt['bps']
            if roll < accum:
                selected = opt
                break
        results.append({
            'draw_index': idx + 1,
            'item_id': selected['item_id'],
            'name': selected['name'],
            'tier': selected['tier'],
            'is_calibration': selected['is_calibration'],
            'quantity': 1,
            'roll_bps': roll
        })
    return results


def resolve_order_manifest(sku: str, current_owned_equipment: List[str]) -> Dict[str, Any]:
    """Computes exact manifest and duplicate fallbacks for an order (Section 3)."""
    item_def = MARKET_CATALOG.get(sku)
    if not item_def:
        raise ValueError(f"Unknown SKU: {sku}")

    manifest: Dict[str, Any] = {
        'sku': sku,
        'gold': item_def.get('gold', 0),
        'items': dict(item_def.get('guaranteed_items', {})),
        'materials': dict(item_def.get('equipment_materials', {})),
        'weapon_parts': dict(item_def.get('weapon_parts', {})),
        'equipment_to_grant': [],
        'fallback_materials': {},
        'badge': item_def.get('badge'),
        'name_color': item_def.get('name_color'),
    }

    # Equipment duplicates resolution
    for eq_id in item_def.get('guaranteed_equipment', {}).keys():
        if eq_id in current_owned_equipment:
            # Grant duplicate fallback materials
            fb = EQUIPMENT_FALLBACKS.get(eq_id, {})
            for mat_k, mat_v in fb.items():
                manifest['fallback_materials'][mat_k] = manifest['fallback_materials'].get(mat_k, 0) + mat_v
                manifest['materials'][mat_k] = manifest['materials'].get(mat_k, 0) + mat_v
        else:
            manifest['equipment_to_grant'].append(eq_id)

    return manifest


async def create_purchase_order(
    db,
    account_id: str,
    sku: str,
    authenticated_wallet: Optional[str] = None,
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """Creates a purchase order in created state."""
    acc_id = account_id.lower()
    from player_accounts import get_player_progress

    prog = await get_player_progress(db, acc_id)
    owned_eq = prog.get('owned_equipment') or []

    manifest = resolve_order_manifest(sku, owned_eq)
    if db is None or not hasattr(db, 'purchase_orders'):
        raise RuntimeError('order_storage_unavailable')
    rid = request_id or str(uuid.uuid4())
    prior = await db.purchase_orders.find_one({'account_id': acc_id, 'request_id': rid}, {'_id': 0})
    if prior:
        if prior.get('sku') != sku:
            raise ValueError('request_id_conflict')
        return prior
    order_id = str(uuid.uuid4())
    now_dt = datetime.now(timezone.utc)

    sku_def = MARKET_CATALOG[sku]
    order = {
        'order_id': order_id,
        'account_id': acc_id,
        'authenticated_wallet': authenticated_wallet or '',
        'sku': sku,
        'sku_name': sku_def['name'],
        'cents': sku_def['cents'],
        'usd_str': sku_def['usd_str'],
        'manifest': manifest,
        'status': 'created',
        'created_at': now_dt.isoformat(),
        'expires_at': (now_dt + timedelta(minutes=15)).isoformat(),
        'request_id': rid,
        'box_results': None,
    }

    await db.purchase_orders.insert_one(order)
    order.pop('_id', None)
    _PURCHASE_ORDERS[order_id] = order

    return order


async def finalize_order_fulfillment(
    db,
    order_id: str,
    tx_hash: Optional[str] = None,
    verified_payment: Optional[Dict[str, Any]] = None,
    authenticated_account: Optional[str] = None,
) -> Dict[str, Any]:
    """Finalizes an order atomically adhering to Section 8 & 9.
    Grants gold, equipment, items (or routes overflow to inbox), and VIP days.
    """
    if not verified_payment or verified_payment.get('verified') is not True or verified_payment.get('status') != 'paid' or not tx_hash:
        raise PermissionError('verified_payment_adapter_required')
    verified_owner = (verified_payment.get('account_id') or authenticated_account or '').lower()
    if not verified_owner:
        raise PermissionError('order_owner_mismatch')
    order = await db.purchase_orders.find_one({'order_id': order_id}, {'_id': 0})
    if not order:
        if db is not None and hasattr(db, 'purchase_orders'):
            order = await db.purchase_orders.find_one({'order_id': order_id}, {'_id': 0})
        if not order:
            raise ValueError(f"Order not found: {order_id}")
    if order.get('account_id', '').lower() != verified_owner:
        raise PermissionError('order_owner_mismatch')
    if order.get('tx_hash') and order['tx_hash'].lower() != tx_hash.lower():
        raise PermissionError('delivery_transaction_mismatch')
    if verified_payment.get('chain_id') not in (None, 4663):
        raise PermissionError('payment_chain_mismatch')

    if order['status'] == 'fulfilled':
        return order  # Idempotent
    if order.get('status') != 'delivering':
        lock = await db.purchase_orders.update_one(
            {'order_id': order_id, 'account_id': order['account_id'], 'status': {'$in': ['awaiting_payment', 'submitted', 'confirming']},
             'tx_hash': order.get('tx_hash')},
            {'$set': {'status': 'delivering', 'tx_hash': tx_hash.lower(), 'chain_id': int(verified_payment.get('chain_id', 4663)),
                      'payment_verified': True, 'payment_confirmations': int(verified_payment.get('confirmations', 0)),
                      'payment_verified_at': datetime.now(timezone.utc).isoformat()}},
        )
        if lock.matched_count != 1:
            current = await db.purchase_orders.find_one({'order_id': order_id}, {'_id': 0})
            if current and current.get('status') == 'fulfilled':
                return current
            if not (current and current.get('status') == 'delivering'
                    and current.get('tx_hash', '').lower() == tx_hash.lower()
                    and current.get('payment_verified') is True):
                raise RuntimeError('order_state_conflict')
            order = current
    elif order.get('tx_hash') != tx_hash:
        raise PermissionError('delivery_transaction_mismatch')

    acc_id = order['account_id']
    sku = order['sku']
    sku_def = MARKET_CATALOG[sku]
    manifest = order['manifest']

    from player_accounts import get_player_progress, save_player_progress
    prog = await get_player_progress(db, acc_id)

    # Persist RNG output and the exact overflow entitlement before the account
    # CAS. A retry after a process crash must not reroll or recompute overflow
    # from a bag which may already contain the grant.
    if sku == 'equipment_luck_2' and not order.get('box_results'):
        candidate = roll_luck_box_draws(5)
        saved = await db.purchase_orders.update_one(
            {'order_id': order_id, 'status': 'delivering', 'tx_hash': tx_hash,
             'box_results': None},
            {'$set': {'box_results': candidate}})
        if saved.matched_count == 1:
            order['box_results'] = candidate
        else:
            latest = await db.purchase_orders.find_one({'order_id': order_id}, {'_id': 0})
            if not latest or not latest.get('box_results'):
                raise RuntimeError('luck_box_result_persist_failed')
            order['box_results'] = latest['box_results']

    # The grant marker and all account changes share the same CAS snapshot, so
    # a delivery retry after a crash cannot grant twice.
    applied = set(prog.get('applied_market_order_ids') or [])
    gold_to_grant = manifest.get('gold', 0)
    inbox_items = dict(order.get('grant_plan', {}).get('inbox_items') or {})
    if order_id not in applied:
        if gold_to_grant > 0:
            prog['gold'] = int(prog.get('gold', 0)) + int(gold_to_grant)

    # 2. Equipment materials & weapon parts
        eq_parts = prog.setdefault('equipment_parts', {})
        for mat_id, count in manifest.get('materials', {}).items():
            eq_parts[mat_id] = eq_parts.get(mat_id, 0) + count

        from weapon_parts import create_weapon_part
        wp_parts = prog.setdefault('weapon_parts', [])
        for part_id, count in manifest.get('weapon_parts', {}).items():
            for _ in range(count):
                wp_parts.append(create_weapon_part(part_id))

    # 3. Guaranteed equipment
        owned_eq = prog.setdefault('owned_equipment', [])
        for eq_id in manifest.get('equipment_to_grant', []):
            if eq_id not in owned_eq:
                owned_eq.append(eq_id)
                prog.setdefault('equipment_levels', {})[eq_id] = 0

    # 4. Badges and cosmetics
        if manifest.get('badge'):
            badges = prog.setdefault('unlocked_badges', [])
            if manifest['badge'] not in badges:
                badges.append(manifest['badge'])
            prog['active_badge'] = manifest['badge']
        if manifest.get('name_color'):
            prog['name_color'] = manifest['name_color']

    # 5. Bag capacity vs Delivery Inbox overflow (medkit, faid, energy_drink)
        heal_items = prog.setdefault('heal_items', {'medkit': 0, 'faid': 0})
        consumables = prog.setdefault('consumables', {'energy_drink': 0})

        grant_plan = order.get('grant_plan')
        if not grant_plan:
            inbox_items = {}
            for itm_id, qty in manifest.get('items', {}).items():
                limit = INVENTORY_LIMITS.get(itm_id, 999)
                current = heal_items.get(itm_id, 0) if itm_id in ('medkit', 'faid') else consumables.get(itm_id, 0)
                fit_qty = min(qty, max(0, limit - current))
                overflow_qty = qty - fit_qty
                if fit_qty:
                    if itm_id in ('medkit', 'faid'):
                        heal_items[itm_id] = current + fit_qty
                    else:
                        consumables[itm_id] = current + fit_qty
                if overflow_qty:
                    inbox_items[itm_id] = overflow_qty
            grant_plan = {'inbox_items': inbox_items}
            saved_plan = await db.purchase_orders.update_one(
                {'order_id': order_id, 'status': 'delivering', 'tx_hash': tx_hash, 'grant_plan': {'$exists': False}},
                {'$set': {'grant_plan': grant_plan}},
            )
            if saved_plan.matched_count != 1:
                latest = await db.purchase_orders.find_one({'order_id': order_id}, {'_id': 0})
                grant_plan = (latest or {}).get('grant_plan') or grant_plan
                inbox_items = dict(grant_plan.get('inbox_items') or {})
        else:
            # A prior attempt persisted the plan. Reapply only the bag portion
            # recorded in the plan so retries remain deterministic.
            for itm_id, qty in manifest.get('items', {}).items():
                limit = INVENTORY_LIMITS.get(itm_id, 999)
                overflow_qty = inbox_items.get(itm_id, 0)
                fit_qty = max(0, int(qty) - int(overflow_qty))
                if itm_id in ('medkit', 'faid'):
                    heal_items[itm_id] = int(heal_items.get(itm_id, 0)) + fit_qty
                else:
                    consumables[itm_id] = int(consumables.get(itm_id, 0)) + fit_qty

    # 6. Luck Box RNG draws if SKU is equipment_luck_2
        if sku == 'equipment_luck_2':
            for d in order['box_results']:
                m_id = d['item_id']
                if d.get('is_calibration'):
                    calib = prog.setdefault('calibration', {})
                    calib[m_id] = calib.get(m_id, 0) + 1
                else:
                    eq_parts[m_id] = eq_parts.get(m_id, 0) + 1

    # 7. VIP 30 days entitlement
        if sku == 'vip_30d':
            now_utc = datetime.now(timezone.utc)
            current_vip_str = prog.get('vip_until_utc')
            base_time = now_utc
            if current_vip_str:
                try:
                    curr_dt = datetime.fromisoformat(current_vip_str)
                    if curr_dt > base_time:
                        base_time = curr_dt
                except Exception:
                    pass
            new_vip_until = base_time + timedelta(days=30)
            prog['vip_until_utc'] = new_vip_until.isoformat()
            prog['is_vip'] = True

    # 8. Save progress
        applied.add(order_id)
        prog['applied_market_order_ids'] = list(applied)
        await save_player_progress(db, acc_id, prog)

    # 9. If any items overflowed, store in Delivery Inbox
    if inbox_items:
        entitlement = {
            'entitlement_id': f'delivery_{order_id}',
            'order_id': order_id,
            'account_id': acc_id,
            'items': inbox_items,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'status': 'pending'
        }
        if db is not None and hasattr(db, 'delivery_inbox'):
            await db.delivery_inbox.update_one({'entitlement_id': entitlement['entitlement_id']}, {'$setOnInsert': entitlement}, upsert=True)
        if not any(e.get('entitlement_id') == entitlement['entitlement_id'] for e in _DELIVERY_INBOX.setdefault(acc_id, [])):
            _DELIVERY_INBOX[acc_id].append(entitlement)

    # Mark order fulfilled
    await record_economy_ledger(db, acc_id, int(gold_to_grant), 'market_purchase', 'market', order_id, f"Purchase: {sku_def['name']}", request_id=f'market:{order_id}', account_revision=prog.get('revision', 1))
    order['status'] = 'fulfilled'
    order['tx_hash'] = tx_hash
    order['fulfilled_at'] = datetime.now(timezone.utc).isoformat()
    _PURCHASE_ORDERS[order_id] = order

    result = await db.purchase_orders.update_one(
        {'order_id': order_id, 'account_id': acc_id, 'status': 'delivering'},
        {'$set': order},
    )
    if result.matched_count != 1:
        raise RuntimeError('order_state_conflict')
    order.pop('_id', None)
    _PURCHASE_ORDERS[order_id] = order
    return order


async def get_delivery_inbox(db, account_id: str) -> List[Dict[str, Any]]:
    """Returns list of pending delivery inbox entitlements for account."""
    acc_id = account_id.lower()
    if db is None or not hasattr(db, 'delivery_inbox'):
        raise RuntimeError('delivery_storage_unavailable')
    return await db.delivery_inbox.find({'account_id': acc_id, 'status': 'pending'}, {'_id': 0}).to_list(100)


async def claim_delivery_item(db, account_id: str, entitlement_id: str, request_id: Optional[str] = None) -> Dict[str, Any]:
    """Transfers items from delivery inbox into player bag up to carrying limits."""
    acc_id = account_id.lower()
    from player_accounts import get_player_progress, save_player_progress
    if db is None or not hasattr(db, 'delivery_inbox'):
        raise RuntimeError('delivery_storage_unavailable')
    for _ in range(4):
        target_ent = await db.delivery_inbox.find_one(
            {'entitlement_id': entitlement_id, 'account_id': acc_id, 'status': 'pending'}, {'_id': 0})
        if not target_ent:
            return {'success': False, 'message': 'delivery_not_found_or_claimed'}
        version = int(target_ent.get('claim_version', 0))
        operation_id = request_id or f'{entitlement_id}:{version}'
        prog = await get_player_progress(db, acc_id)
        applied = prog.setdefault('applied_delivery_claims', {})
        receipt = applied.get(operation_id)
        if receipt:
            remaining_items = dict(receipt.get('remaining_items') or {})
            claimed_items = dict(receipt.get('claimed_items') or {})
        else:
            heal_items = prog.setdefault('heal_items', {'medkit': 0, 'faid': 0})
            consumables = prog.setdefault('consumables', {'energy_drink': 0})
            remaining_items, claimed_items = {}, {}
            for itm_id, qty in (target_ent.get('items') or {}).items():
                limit = INVENTORY_LIMITS.get(itm_id, 999)
                current = heal_items.get(itm_id, 0) if itm_id in ('medkit', 'faid') else consumables.get(itm_id, 0)
                fit_qty = min(int(qty), max(0, limit - int(current)))
                if fit_qty:
                    claimed_items[itm_id] = fit_qty
                    if itm_id in ('medkit', 'faid'):
                        heal_items[itm_id] = int(current) + fit_qty
                    else:
                        consumables[itm_id] = int(current) + fit_qty
                if fit_qty < int(qty):
                    remaining_items[itm_id] = int(qty) - fit_qty
            if not claimed_items:
                return {'success': False, 'code': 'BAG_FULL', 'error_code': 'BAG_FULL', 'claimed_items': {},
                        'remaining_items': remaining_items,
                        'entitlement_status': 'pending'}
            applied[operation_id] = {'entitlement_id': entitlement_id, 'claimed_items': claimed_items,
                                     'remaining_items': remaining_items}
            try:
                await save_player_progress(db, acc_id, prog)
            except RuntimeError as exc:
                if str(exc) == 'progress_revision_conflict':
                    continue
                raise

        status = 'pending' if remaining_items else 'claimed'
        result = await db.delivery_inbox.update_one(
            {'entitlement_id': entitlement_id, 'account_id': acc_id, 'status': 'pending', 'claim_version': version},
            {'$set': {'items': remaining_items, 'status': status, 'last_claim_request_id': operation_id},
             '$inc': {'claim_version': 1}},
        )
        if result.matched_count == 1:
            return {'success': True, 'claimed_items': claimed_items, 'remaining_items': remaining_items,
                    'error_code': None, 'claim_id': operation_id, 'entitlement_status': status}
        # The progress marker is durable; a retry will finish the inbox CAS
        # without applying the items a second time.
    raise RuntimeError('delivery_claim_conflict')


def get_vip_status(player_progress: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluates effective VIP status for player (Section 7)."""
    now_utc = datetime.now(timezone.utc)
    vip_str = player_progress.get('vip_until_utc')
    is_active = False
    remaining_seconds = 0

    if vip_str:
        try:
            exp_dt = datetime.fromisoformat(vip_str)
            if exp_dt > now_utc:
                is_active = True
                remaining_seconds = int((exp_dt - now_utc).total_seconds())
        except Exception:
            pass

    return {
        'is_vip': is_active,
        'vip_until_utc': vip_str if is_active else None,
        'remaining_seconds': remaining_seconds,
        'bonus_pve_gold_pct': 10 if is_active else 0,
        'nft_notice': MARKET_CATALOG['vip_30d']['nft_notice']
    }

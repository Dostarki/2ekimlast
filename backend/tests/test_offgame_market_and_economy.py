import pytest
import math
import sys
import os
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from economy import compute_vip_gold_bonus, mutate_gold_atomic
from pvp_rewards import (
    calculate_raw_pvp_xp,
    get_pair_multiplier,
    get_daily_remaining_cap,
    record_daily_xp,
    evaluate_pvp_kill,
    PVP_DAILY_XP_CAP
)
from offgame_market import (
    MARKET_CATALOG,
    LUCK_BOX_ODDS_TABLE,
    resolve_order_manifest,
    roll_luck_box_draws,
    create_purchase_order,
    finalize_order_fulfillment,
    claim_delivery_item,
    get_vip_status
)
from missions import (
    start_soldier_mission,
    claim_soldier_mission,
    MISSION_DURATION_HOURS
)
from loot import (
    craft_upgrade,
    CRAFT_RECIPES,
    WEAPON_UPGRADE_LIMITS,
    MAX_UPGRADE_TIERS_PER_STAT,
    pickup_loot
)


class MockDB:
    def __init__(self):
        self.player_accounts = self
        self.player_progress = self
        self.economy_ledger = self
        self.purchase_orders = self
        self.delivery_inbox = self
        self.soldier_missions = self
        self._data = {}

    async def find_one(self, query, projection=None):
        acc = query.get('account_id')
        return self._data.get(acc)

    async def update_one(self, query, update, upsert=False):
        acc = query.get('account_id')
        doc = self._data.setdefault(acc, {'account_id': acc})
        if '$set' in update:
            doc.update(update['$set'])
        if '$inc' in update:
            for k, v in update['$inc'].items():
                doc[k] = doc.get(k, 0) + v
        return doc

    async def insert_one(self, doc):
        acc = doc.get('account_id')
        self._data[acc] = doc
        return doc


def test_pvp_xp_formula_and_scaling():
    # Plan Section 15 validation
    assert calculate_raw_pvp_xp(1) == 30
    assert calculate_raw_pvp_xp(5) == 39
    assert calculate_raw_pvp_xp(10) == 52
    assert calculate_raw_pvp_xp(20) == 76
    assert calculate_raw_pvp_xp(30) == 101
    assert calculate_raw_pvp_xp(40) == 125
    assert calculate_raw_pvp_xp(50) == 150
    assert calculate_raw_pvp_xp(99) == 150  # clamped to 50 max
    assert calculate_raw_pvp_xp(0) == 30   # clamped to 1 min


def test_pvp_anti_farm_and_daily_cap():
    killer = {'account_id': 'killer_001', 'id': 'k1'}
    victim = {'account_id': 'victim_001', 'id': 'v1', 'level': 50}

    # 1st kill: 100% (150 XP)
    eval1 = evaluate_pvp_kill(killer, victim, now=1000.0)
    assert eval1['granted_xp'] == 150
    assert eval1['multiplier'] == 1.0

    # 2nd kill in rolling 30m: 25% (floor(150 * 0.25) = 37 XP)
    eval2 = evaluate_pvp_kill(killer, victim, now=1100.0)
    assert eval2['granted_xp'] == 37
    assert eval2['multiplier'] == 0.25

    # 3rd kill in rolling 30m: 0% (0 XP)
    eval3 = evaluate_pvp_kill(killer, victim, now=1200.0)
    assert eval3['granted_xp'] == 0
    assert eval3['multiplier'] == 0.0
    assert eval3['reason'] == 'repeat_kill_limit'

    # Same alliance: 0 XP
    killer_allied = {'account_id': 'k_ally', 'alliance_id': 'A1'}
    victim_allied = {'account_id': 'v_ally', 'alliance_id': 'A1', 'level': 20}
    eval_ally = evaluate_pvp_kill(killer_allied, victim_allied, now=1000.0)
    assert eval_ally['granted_xp'] == 0
    assert eval_ally['reason'] == 'same_alliance'


def test_vip_pve_gold_bonus_integer_remainder():
    # 10 gold -> 10% = 1 gold, rem = 0
    b1, r1 = compute_vip_gold_bonus(10, is_vip=True, remainder=0)
    assert b1 == 1 and r1 == 0

    # 5 gold -> 50/100 = 0 gold, rem = 50
    b2, r2 = compute_vip_gold_bonus(5, is_vip=True, remainder=0)
    assert b2 == 0 and r2 == 50

    # Next 5 gold -> (50 + 50)/100 = 1 gold, rem = 0
    b3, r3 = compute_vip_gold_bonus(5, is_vip=True, remainder=r2)
    assert b3 == 1 and r3 == 0

    # Not VIP -> 0 bonus
    b4, r4 = compute_vip_gold_bonus(100, is_vip=False, remainder=0)
    assert b4 == 0 and r4 == 0


def test_market_catalog_packages_and_odds():
    assert MARKET_CATALOG['pack_field']['cents'] == 200
    assert MARKET_CATALOG['pack_field']['gold'] == 1000

    assert MARKET_CATALOG['pack_supply']['cents'] == 400
    assert MARKET_CATALOG['pack_supply']['gold'] == 2000

    assert MARKET_CATALOG['pack_operator']['cents'] == 600
    assert MARKET_CATALOG['pack_operator']['gold'] == 3500

    assert MARKET_CATALOG['pack_outpost']['cents'] == 1000
    assert MARKET_CATALOG['pack_outpost']['gold'] == 6000

    # Odds table total exactly 10000 basis points
    total_bps = sum(entry['bps'] for entry in LUCK_BOX_ODDS_TABLE)
    assert total_bps == 10000
    assert len(LUCK_BOX_ODDS_TABLE) == 15


def test_duplicate_equipment_fallback():
    # When player does not own helmet_t1
    m1 = resolve_order_manifest('pack_supply', current_owned_equipment=[])
    assert 'helmet_t1' in m1['equipment_to_grant']
    assert m1['fallback_materials'] == {}

    # When player already owns helmet_t1, grant fallback materials
    m2 = resolve_order_manifest('pack_supply', current_owned_equipment=['helmet_t1'])
    assert 'helmet_t1' not in m2['equipment_to_grant']
    # Fallback for helmet_t1: fabric_t1: 2, plate_t1: 2, binding_t1: 1
    assert m2['fallback_materials'].get('fabric_t1') == 2
    assert m2['fallback_materials'].get('plate_t1') == 2
    assert m2['fallback_materials'].get('binding_t1') == 1


def test_weapon_craft_upgrade_limits():
    game = type('Game', (), {'events': []})()
    player = {
        'id': 'p1',
        'hp': 100,
        'inventory': {'ak47': True},
        'weapon_parts': [{'id': 'barrel_common'} for _ in range(50)],
        'weapon_upgrades': {},
        'weapon_upgrade_counts': {}
    }

    # upgrade_damage_t1 takes 3 barrel_common and adds 1.05x damage
    # Max tier is 3
    assert craft_upgrade(game, player, 'upgrade_damage_t1', 'ak47', 0) is True
    assert craft_upgrade(game, player, 'upgrade_damage_t1', 'ak47', 0) is True
    assert craft_upgrade(game, player, 'upgrade_damage_t1', 'ak47', 0) is True
    # 4th upgrade should be rejected because MAX_UPGRADE_TIERS_PER_STAT is 3
    assert craft_upgrade(game, player, 'upgrade_damage_t1', 'ak47', 0) is False

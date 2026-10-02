"""DEADZONE — Loot, XP/Leveling, Heal, Stats & Crafting backend module."""

import math
import random
import time
import uuid
from weapon_parts import WEAPON_PARTS


# ---------------------------------------------------------------------------
# Loot tables
# ---------------------------------------------------------------------------

LOOT_TABLES = {
    'normal':    {'gold': (5, 15),   'xp': (20, 40),   'part_tier': 1, 'part_chance': .35, 'medkit_chance': .12, 'faid_chance': .20, 'energy_drink_chance': .08},
    'hellhound': {'gold': (10, 20),  'xp': (30, 50),   'part_tier': 1, 'part_chance': .35, 'medkit_chance': .10, 'faid_chance': .22},
    'armored':   {'gold': (20, 40),  'xp': (50, 80),   'part_tier': 2, 'part_chance': .40, 'medkit_chance': .18, 'faid_chance': .15},
    'immolator': {'gold': (30, 50),  'xp': (60, 100),  'part_tier': 2, 'part_chance': .45, 'medkit_chance': .22, 'faid_chance': .10},
    'hive':      {'gold': (25, 45),  'xp': (50, 90),   'part_tier': 2, 'part_chance': .42, 'medkit_chance': .20, 'faid_chance': .12},
}

BOSS_LOOT = {
    'gold': (200, 500), 'xp': (500, 1000),
    'part_tier': 3, 'part_count': (3, 5),
    'medkit_count': 2,
}

# ---------------------------------------------------------------------------
# Heal items
# ---------------------------------------------------------------------------

HEAL_ITEMS = {
    'medkit': {'heal': 50, 'use_time': 3.0, 'name': 'Medkit',        'max_stack': 3},
    'faid':   {'heal': 25, 'use_time': 1.5, 'name': 'First Aid Kit', 'max_stack': 5},
}

ENERGY_DRINK_ID = 'energy_drink'
ENERGY_DRINK_DURATION = 60
ENERGY_DRINK_MAX_STACK = 10

def use_consumable(game, player, item_id, request_id=None, now_utc=None):
    """Atomically consume a supported utility item. Expiry is wall-clock UTC so it survives restart."""
    if item_id != ENERGY_DRINK_ID or player.get('hp', 0) <= 0:
        return False, 'This consumable cannot be used right now.'
    used = player.setdefault('consumable_requests', {})
    if request_id and request_id in used:
        return True, 'Energy drink already consumed.'
    stock = player.setdefault('consumables', {}).get(ENERGY_DRINK_ID, 0)
    if not isinstance(stock, int) or stock < 1:
        return False, 'No energy drinks in stock.'
    now_utc = float(now_utc if now_utc is not None else time.time())
    player['consumables'][ENERGY_DRINK_ID] = stock - 1
    player['energy_drink_expires_at'] = now_utc + ENERGY_DRINK_DURATION
    if request_id:
        used[request_id] = now_utc
        # Bound replay bookkeeping; persisted account data must not grow forever.
        for key, stamped in list(used.items()):
            if now_utc - stamped > 300:
                used.pop(key, None)
    game.events.append({'type': 'consumable_used', 'owner': player['id'], 'item_id': item_id})
    return True, 'ENERGY DRINK: 60 SEC ×2 STAMINA REGENERATION.'


# ---------------------------------------------------------------------------
# XP / Level
# ---------------------------------------------------------------------------

MAX_LEVEL = 50


def xp_for_level(level):
    """Total cumulative XP required to reach *level*."""
    if level <= 1:
        return 0
    return sum(i * 100 for i in range(1, level))


def level_from_xp(xp):
    """Return (level, progress_in_level, xp_needed_for_next)."""
    level, total = 1, 0
    while level < MAX_LEVEL:
        needed = level * 100
        if total + needed > xp:
            return level, xp - total, needed
        total += needed
        level += 1
    return MAX_LEVEL, 0, 0


def grant_xp(game, player, amount):
    """Add *amount* XP to *player*, handle level-ups and stat point grants."""
    old_level = player.get('level', 1)
    player['xp'] = player.get('xp', 0) + amount
    new_level, _progress, _needed = level_from_xp(player['xp'])
    new_level = min(new_level, MAX_LEVEL)
    player['level'] = new_level

    if new_level > old_level:
        points = sum(2 if (old_level + i) % 5 == 0 else 1
                     for i in range(1, new_level - old_level + 1))
        player['stat_points'] = player.get('stat_points', 0) + points
        game.events.append({
            'type': 'level_up', 'owner': player['id'],
            'level': new_level, 'points': points,
        })

    game.events.append({
        'type': 'xp_gain', 'owner': player['id'], 'amount': amount,
    })


# ---------------------------------------------------------------------------
# Stat allocation
# ---------------------------------------------------------------------------

VALID_STATS = {
    'reload_speed':    10,
    'move_speed':       8,
    'heal_multiplier':  8,
    'durability':      10,
    'stamina_regen':    8,
}

DEFAULT_STATS = {k: 0 for k in VALID_STATS}


def max_hp(player):
    return 100 + 5 * player.get('stats', DEFAULT_STATS).get('durability', 0)


def player_stat(player, stat_id):
    return player.get('stats', DEFAULT_STATS).get(stat_id, 0)


def allocate_stat(game, player, stat_id):
    if player['hp'] <= 0 or stat_id not in VALID_STATS:
        return
    if player.get('stat_points', 0) <= 0:
        return
    stats = player.setdefault('stats', dict(DEFAULT_STATS))
    current = stats.get(stat_id, 0)
    if current >= VALID_STATS[stat_id]:
        return
    stats[stat_id] = current + 1
    player['stat_points'] -= 1
    # If durability just increased, raise current HP proportionally.
    if stat_id == 'durability':
        player['hp'] = min(max_hp(player), player['hp'] + 5)
    game.events.append({
        'type': 'stat_allocated', 'owner': player['id'],
        'stat': stat_id, 'value': current + 1,
    })


# ---------------------------------------------------------------------------
# Loot generation & pickup
# ---------------------------------------------------------------------------

def _make_drop(kind, x, z, now, **kwargs):
    ox = random.uniform(-1.5, 1.5)
    oz = random.uniform(-1.5, 1.5)
    ttl = 60 if kind == 'xp' else 90 if kind in ('medkit', 'faid') else 120
    return {
        'id': f'loot_{uuid.uuid4().hex[:8]}',
        'kind': kind,
        'x': round(x + ox, 2),
        'z': round(z + oz, 2),
        'expires': now + ttl,
        **kwargs,
    }


def generate_loot(enemy_type, x, z, now, is_boss=False):
    """Return a list of loot drop dicts for a killed enemy."""
    items = []

    if is_boss:
        tbl = BOSS_LOOT
        items.append(_make_drop('gold', x, z, now, amount=random.randint(*tbl['gold'])))
        items.append(_make_drop('xp', x, z, now, amount=random.randint(*tbl['xp']), auto_pickup=True))
        for _ in range(random.randint(*tbl['part_count'])):
            part = random.choice(WEAPON_PARTS[tbl['part_tier']])
            items.append(_make_drop('part', x, z, now, part_id=part, tier=tbl['part_tier']))
        for _ in range(tbl['medkit_count']):
            items.append(_make_drop('medkit', x, z, now))
        # Boss drops 2-4 T2/T3 equipment parts
        for _ in range(random.randint(2, 4)):
            t = random.choice([2, 3])
            m_pool = ['fabric', 'plate', 'binding', 'mechanism']
            mat_id = f"{random.choice(m_pool)}_t{t}"
            items.append(_make_drop('equipment_part', x, z, now, part_id=mat_id, tier=t))
        # 40% chance for calibration cartridge
        if random.random() < 0.40:
            cal_id = random.choice(['calibration_t2', 'calibration_t3'])
            items.append(_make_drop('calibration', x, z, now, calibration_id=cal_id, tier=2 if cal_id == 'calibration_t2' else 3))
        return items

    tbl = LOOT_TABLES.get(enemy_type, LOOT_TABLES['normal'])
    items.append(_make_drop('gold', x, z, now, amount=random.randint(*tbl['gold'])))
    items.append(_make_drop('xp', x, z, now, amount=random.randint(*tbl['xp']), auto_pickup=True))

    if random.random() < tbl['part_chance']:
        part = random.choice(WEAPON_PARTS[tbl['part_tier']])
        items.append(_make_drop('part', x, z, now, part_id=part, tier=tbl['part_tier']))

    # Equipment material drops based on enemy type
    eq_chance = 0.0
    eq_tiers = [1]
    if enemy_type in ('normal', 'runner'):
        eq_chance = 0.18
        eq_tiers = [1]
    elif enemy_type in ('spitter', 'tank'):
        eq_chance = 0.28
        eq_tiers = [1, 2]
    elif enemy_type in ('immolator', 'hive'):
        eq_chance = 0.32
        eq_tiers = [2]
    elif enemy_type in ('stalker', 'witch'):
        eq_chance = 0.38
        eq_tiers = [2, 3]

    if random.random() < eq_chance:
        t = random.choice(eq_tiers)
        m_pool = ['fabric', 'plate', 'binding', 'mechanism']
        mat_id = f"{random.choice(m_pool)}_t{t}"
        items.append(_make_drop('equipment_part', x, z, now, part_id=mat_id, tier=t))

    if random.random() < tbl['medkit_chance']:
        items.append(_make_drop('medkit', x, z, now))
    elif random.random() < tbl['faid_chance']:
        items.append(_make_drop('faid', x, z, now))
    if random.random() < tbl.get('energy_drink_chance', .08):
        items.append(_make_drop('energy_drink', x, z, now))

    return items


def pickup_loot(game, player, drop, _now):
    """Apply a single loot drop to *player*."""
    kind = drop['kind']
    if kind == 'gold':
        base_amt = drop['amount']
        # Effective VIP comes from its UTC deadline. The cached boolean is
        # retained for old snapshots/UI compatibility but can never outlive it.
        is_vip = False
        vip_str = player.get('vip_until_utc')
        if vip_str:
            try:
                from datetime import datetime, timezone
                if datetime.fromisoformat(vip_str) > datetime.now(timezone.utc):
                    is_vip = True
            except Exception:
                is_vip = False
        player['is_vip'] = is_vip
        if not is_vip:
            player['bonus_numerator_remainder'] = 0
        bonus = 0
        if is_vip:
            from economy import compute_vip_gold_bonus
            rem = player.get('bonus_numerator_remainder', 0)
            bonus, new_rem = compute_vip_gold_bonus(base_amt, True, rem)
            player['bonus_numerator_remainder'] = new_rem

        total_gain = base_amt + bonus
        player['gold'] = player.get('gold', 0) + total_gain
        game.events.append({'type': 'loot_pickup', 'owner': player['id'],
                            'kind': 'gold', 'amount': total_gain, 'base_amount': base_amt, 'vip_bonus': bonus})
    elif kind == 'xp':
        grant_xp(game, player, drop['amount'])
    elif kind == 'energy_drink':
        inv = player.setdefault('consumables', {'energy_drink': 0})
        if inv.get('energy_drink', 0) >= ENERGY_DRINK_MAX_STACK:
            return
        inv['energy_drink'] = inv.get('energy_drink', 0) + 1
        game.events.append({'type': 'loot_pickup', 'owner': player['id'], 'kind': kind})
    elif kind in ('medkit', 'faid'):
        inv = player.setdefault('heal_items', {})
        info = HEAL_ITEMS[kind]
        current = inv.get(kind, 0)
        if current < info['max_stack']:
            inv[kind] = current + 1
            game.events.append({'type': 'loot_pickup', 'owner': player['id'], 'kind': kind})
        else:
            return  # stack full, leave the drop on the ground
    elif kind == 'part':
        parts = player.setdefault('weapon_parts', [])
        parts.append({'id': drop['part_id'], 'tier': drop['tier']})
        game.events.append({'type': 'loot_pickup', 'owner': player['id'],
                            'kind': 'part', 'part_id': drop['part_id'], 'tier': drop['tier']})
    elif kind == 'equipment_part':
        parts = player.setdefault('equipment_parts', {})
        pid = drop['part_id']
        parts[pid] = parts.get(pid, 0) + 1
        game.events.append({'type': 'loot_pickup', 'owner': player['id'],
                            'kind': 'equipment_part', 'part_id': pid, 'tier': drop['tier']})
    elif kind == 'calibration':
        cal = player.setdefault('calibration', {})
        cid = drop['calibration_id']
        cal[cid] = cal.get(cid, 0) + 1
        game.events.append({'type': 'loot_pickup', 'owner': player['id'],
                            'kind': 'calibration', 'calibration_id': cid, 'tier': drop['tier']})
    game.persist_progress(player)


# ---------------------------------------------------------------------------
# Heal item usage
# ---------------------------------------------------------------------------

def use_heal_item(game, player, item_id, now):
    if player['hp'] <= 0 or player['hp'] >= max_hp(player):
        return
    if now < player.get('heal_until', 0):
        return
    inv = player.get('heal_items', {})
    count = inv.get(item_id, 0)
    if count <= 0 or item_id not in HEAL_ITEMS:
        return
    info = HEAL_ITEMS[item_id]
    player['heal_duration'] = info['use_time']
    player['heal_until'] = now + info['use_time']
    player['heal_pending'] = {'item': item_id, 'heal': info['heal']}
    inv[item_id] = count - 1


def complete_heal(game, player, now):
    """Called every tick; finishes heal when the cast time expires."""
    if not player.get('heal_until') or now < player['heal_until']:
        return
    pending = player.pop('heal_pending', None)
    player['heal_until'] = 0
    if pending and player['hp'] > 0:
        multiplier = 1.0 + 0.10 * player_stat(player, 'heal_multiplier')
        amount = round(pending['heal'] * multiplier)
        player['hp'] = min(max_hp(player), player['hp'] + amount)
        game.events.append({'type': 'heal', 'owner': player['id'], 'amount': amount})


# ---------------------------------------------------------------------------
# Crafting
# ---------------------------------------------------------------------------

CRAFT_RECIPES = {
    'upgrade_damage_t1':  {'parts': {'barrel_common': 3},
                           'effect': {'stat': 'damage', 'multiplier': 1.05}},
    'upgrade_range_t1':   {'parts': {'stock_common': 2, 'grip_common': 1},
                           'effect': {'stat': 'range', 'multiplier': 1.05}},
    'upgrade_mag_t1':     {'parts': {'spring_common': 2, 'grip_common': 1},
                           'effect': {'stat': 'mag', 'multiplier': 1.20}},
    'upgrade_damage_t2':  {'parts': {'barrel_uncommon': 3, 'receiver_uncommon': 1},
                           'effect': {'stat': 'damage', 'multiplier': 1.10}},
    'upgrade_range_t2':   {'parts': {'stock_uncommon': 2, 'grip_uncommon': 2},
                           'effect': {'stat': 'range', 'multiplier': 1.10}},
    'upgrade_reload_t2':  {'parts': {'receiver_uncommon': 2, 'grip_uncommon': 1},
                           'effect': {'stat': 'reload', 'multiplier': 0.85}},
    'upgrade_damage_t3':  {'parts': {'barrel_rare': 2, 'receiver_rare': 1},
                           'effect': {'stat': 'damage', 'multiplier': 1.15}},
    'upgrade_optic_t3':   {'parts': {'optic_rare': 2, 'receiver_rare': 1},
                           'effect': {'stat': 'range', 'multiplier': 1.20}},
    'craft_suppressor':   {'parts': {'suppressor_rare': 2, 'barrel_rare': 1},
                           'effect': {'stat': 'spread', 'multiplier': 0.70}},

    # Weapon crafting recipes (assemble new weapons from parts that exist in world.WEAPONS)
    'craft_weapon_shotgun': {
        'type': 'weapon', 'weapon': 'shotgun',
        'parts': {'barrel_common': 2, 'stock_common': 2},
    },
    'craft_weapon_ak47': {
        'type': 'weapon', 'weapon': 'ak47',
        'parts': {'receiver_uncommon': 2, 'barrel_uncommon': 2, 'stock_uncommon': 1},
    },
    'craft_weapon_m4': {
        'type': 'weapon', 'weapon': 'm4',
        'parts': {'receiver_uncommon': 2, 'barrel_uncommon': 1, 'stock_uncommon': 2},
    },
    'craft_weapon_ak117': {
        'type': 'weapon', 'weapon': 'ak117',
        'parts': {'receiver_uncommon': 2, 'spring_common': 2, 'grip_uncommon': 2},
    },
    'craft_weapon_ak107': {
        'type': 'weapon', 'weapon': 'ak107',
        'parts': {'receiver_uncommon': 3, 'barrel_uncommon': 2},
    },
    'craft_weapon_flamethrower': {
        'type': 'weapon', 'weapon': 'flamethrower',
        'parts': {'barrel_rare': 2, 'receiver_rare': 2, 'spring_common': 2},
    },
    'craft_weapon_rocket': {
        'type': 'weapon', 'weapon': 'rocket',
        'parts': {'optic_rare': 2, 'receiver_rare': 2, 'barrel_rare': 2},
    },
    'craft_weapon_minigun': {
        'type': 'weapon', 'weapon': 'minigun',
        'parts': {'receiver_rare': 3, 'barrel_rare': 2, 'spring_common': 3},
    },
    'craft_weapon_lava': {
        'type': 'weapon', 'weapon': 'lava',
        'parts': {'receiver_rare': 2, 'barrel_rare': 2, 'optic_rare': 2},
    },
}

WEAPON_UPGRADE_LIMITS = {
    'damage': {'min': 1.0, 'max': 1.50},    # max +50% damage
    'range': {'min': 1.0, 'max': 1.50},     # max +50% range
    'mag': {'min': 1.0, 'max': 2.00},       # max 2.0x magazine
    'reload': {'min': 0.60, 'max': 1.0},    # max -40% reload time
    'spread': {'min': 0.50, 'max': 1.0},    # max -50% spread
}
MAX_UPGRADE_TIERS_PER_STAT = 3


def _count_parts(parts):
    counts = {}
    for p in parts:
        counts[p['id']] = counts.get(p['id'], 0) + 1
    return counts


def craft_upgrade(game, player, recipe_id, target_weapon, _now):
    from world import WEAPONS
    if player['hp'] <= 0 or recipe_id not in CRAFT_RECIPES:
        return False

    recipe = CRAFT_RECIPES[recipe_id]
    if recipe.get('type') == 'weapon':
        target_weapon = recipe.get('weapon', target_weapon)
        # A stale client recipe must never consume materials for a weapon that
        # is absent from the authoritative catalogue.
        if target_weapon not in WEAPONS or target_weapon in player.get('inventory', {}):
            return False  # Already unlocked
    else:
        if target_weapon not in WEAPONS or target_weapon not in player.get('inventory', {}):
            return False

        # Enforce weapon upgrade ceilings and max tiers
        upgrades = player.setdefault('weapon_upgrades', {})
        weapon_mods = upgrades.setdefault(target_weapon, {})
        upgrade_counts = player.setdefault('weapon_upgrade_counts', {}).setdefault(target_weapon, {})
        effect = recipe['effect']
        stat = effect['stat']
        current_count = upgrade_counts.get(stat, 0)
        if current_count >= MAX_UPGRADE_TIERS_PER_STAT:
            return False

        current = weapon_mods.get(stat, 1.0)
        new_val = round(current * effect['multiplier'], 4)
        limits = WEAPON_UPGRADE_LIMITS.get(stat)
        if limits:
            if effect['multiplier'] > 1.0 and (current >= limits['max'] or new_val > limits['max']):
                return False
            if effect['multiplier'] < 1.0 and (current <= limits['min'] or new_val < limits['min']):
                return False

    parts = player.get('weapon_parts', [])
    available = _count_parts(parts)

    for part_id, count in recipe['parts'].items():
        if available.get(part_id, 0) < count:
            return False

    # Consume parts
    for part_id, count in recipe['parts'].items():
        to_remove = count
        new_parts = []
        for p in parts:
            if p['id'] == part_id and to_remove > 0:
                to_remove -= 1
            else:
                new_parts.append(p)
        parts = new_parts
    player['weapon_parts'] = parts

    # If this is a weapon assembly craft
    if recipe.get('type') == 'weapon':
        from inventory import unlock_weapon
        if not unlock_weapon(player, target_weapon):
            return False
        game.events.append({
            'type': 'craft_success', 'owner': player['id'],
            'recipe': recipe_id, 'weapon': target_weapon,
            'weapon_unlocked': True,
        })
        return True

    # Apply weapon upgrade
    upgrades = player.setdefault('weapon_upgrades', {})
    weapon_mods = upgrades.setdefault(target_weapon, {})
    upgrade_counts = player.setdefault('weapon_upgrade_counts', {}).setdefault(target_weapon, {})
    effect = recipe['effect']
    stat = effect['stat']
    current = weapon_mods.get(stat, 1.0)
    new_val = round(current * effect['multiplier'], 4)
    limits = WEAPON_UPGRADE_LIMITS.get(stat)
    if limits:
        new_val = max(limits['min'], min(limits['max'], new_val))
    weapon_mods[stat] = new_val
    upgrade_counts[stat] = upgrade_counts.get(stat, 0) + 1

    game.events.append({
        'type': 'craft_success', 'owner': player['id'],
        'recipe': recipe_id, 'weapon': target_weapon,
    })
    return True


def get_effective_weapon(player, weapon_id):
    """Return a weapon dict with the player's crafting upgrades applied."""
    from world import WEAPONS
    base = dict(WEAPONS[weapon_id])
    upgrades = player.get('weapon_upgrades', {}).get(weapon_id, {})
    for stat, multiplier in upgrades.items():
        if stat in base:
            if stat == 'mag':
                base[stat] = int(round(base[stat] * multiplier))
            else:
                base[stat] = round(base[stat] * multiplier, 2)
    return base

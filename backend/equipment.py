"""DEADZONE - Equipment, Materials, Recipes, and Stats System

Defines the 18 equipment pieces (6 slots x 3 tiers), +0/+1/+2 upgrade paths,
crafting material families (Fabric, Plate, Binding, Mechanism, Calibration),
sell price tables, and equipment stat calculations.
"""

from typing import Dict, Any, List, Optional, Tuple

EQUIPMENT_SLOTS = ['head', 'body', 'legs', 'hands', 'feet', 'backpack']

# 18 Base Equipment Items
EQUIPMENT_CATALOG = {
    # HEAD (Armor)
    'helmet_t1': {
        'id': 'helmet_t1', 'slot': 'head', 'tier': 1, 'name': 'Field Helmet',
        'level_req': 1, 'base_stat': {'armor': 4}, 'description': 'Mat steel shell with fabric chinstrap.'
    },
    'helmet_t2': {
        'id': 'helmet_t2', 'slot': 'head', 'tier': 2, 'name': 'Ballistic Helmet',
        'level_req': 15, 'base_stat': {'armor': 6}, 'description': 'Angular ballistic shell with side rails and brow pad.'
    },
    'helmet_t3': {
        'id': 'helmet_t3', 'slot': 'head', 'tier': 3, 'name': 'Composite Helmet',
        'level_req': 30, 'base_stat': {'armor': 8}, 'description': 'Cutaway composite shell with sealed bindings.'
    },

    # BODY (Armor)
    'vest_t1': {
        'id': 'vest_t1', 'slot': 'body', 'tier': 1, 'name': 'Light Vest',
        'level_req': 1, 'base_stat': {'armor': 10}, 'description': 'Thin fabric panel with exposed stitching and two pouches.'
    },
    'vest_t2': {
        'id': 'vest_t2', 'slot': 'body', 'tier': 2, 'name': 'Plate Carrier',
        'level_req': 15, 'base_stat': {'armor': 15}, 'description': 'Front and back ballistic plates with three magazine pouches.'
    },
    'vest_t3': {
        'id': 'vest_t3', 'slot': 'body', 'tier': 3, 'name': 'Assault Vest',
        'level_req': 30, 'base_stat': {'armor': 20}, 'description': 'Segmented chest plate with side protection and enclosed pouches.'
    },

    # LEGS (Armor)
    'legs_t1': {
        'id': 'legs_t1', 'slot': 'legs', 'tier': 1, 'name': 'Reinforced Leg Armor',
        'level_req': 1, 'base_stat': {'armor': 6}, 'description': 'Fabric thigh pads and compact knee protectors.'
    },
    'legs_t2': {
        'id': 'legs_t2', 'slot': 'legs', 'tier': 2, 'name': 'Ballistic Leg Guards',
        'level_req': 15, 'base_stat': {'armor': 9}, 'description': 'Strapped hard kneepads with outer thigh plates.'
    },
    'legs_t3': {
        'id': 'legs_t3', 'slot': 'legs', 'tier': 3, 'name': 'Composite Leg Armor',
        'level_req': 30, 'base_stat': {'armor': 12}, 'description': 'Articulated segmented thigh and knee plating.'
    },

    # HANDS (Reload Reduction)
    'hands_t1': {
        'id': 'hands_t1', 'slot': 'hands', 'tier': 1, 'name': 'Field Gloves',
        'level_req': 1, 'base_stat': {'reload_speed': 0.02}, 'description': 'Fingerless fabric gloves with leather palm reinforcement.'
    },
    'hands_t2': {
        'id': 'hands_t2', 'slot': 'hands', 'tier': 2, 'name': 'Grip Gloves',
        'level_req': 15, 'base_stat': {'reload_speed': 0.04}, 'description': 'Full-finger gloves with rubber knuckle guard.'
    },
    'hands_t3': {
        'id': 'hands_t3', 'slot': 'hands', 'tier': 3, 'name': 'Operator Gloves',
        'level_req': 30, 'base_stat': {'reload_speed': 0.06}, 'description': 'Composite knuckle guard, reinforced palm, and wrist cinch.'
    },

    # FEET (Movement Speed)
    'feet_t1': {
        'id': 'feet_t1', 'slot': 'feet', 'tier': 1, 'name': 'Field Boots',
        'level_req': 1, 'base_stat': {'movement_speed': 0.01}, 'description': 'Leather and canvas with flexible sole.'
    },
    'feet_t2': {
        'id': 'feet_t2', 'slot': 'feet', 'tier': 2, 'name': 'Tactical Boots',
        'level_req': 15, 'base_stat': {'movement_speed': 0.02}, 'description': 'Thick ankle support, lugged tread, and reinforced toe cap.'
    },
    'feet_t3': {
        'id': 'feet_t3', 'slot': 'feet', 'tier': 3, 'name': 'Operations Boots',
        'level_req': 30, 'base_stat': {'movement_speed': 0.03}, 'description': 'Layered ankle protection, shielded laces, and composite toe.'
    },

    # BACKPACK (Stamina Regen)
    'backpack_t1': {
        'id': 'backpack_t1', 'slot': 'backpack', 'tier': 1, 'name': 'Field Pack',
        'level_req': 1, 'base_stat': {'stamina_regen': 0.03}, 'description': 'Compact rolltop canvas field bag.'
    },
    'backpack_t2': {
        'id': 'backpack_t2', 'slot': 'backpack', 'tier': 2, 'name': 'Supply Pack',
        'level_req': 15, 'base_stat': {'stamina_regen': 0.06}, 'description': 'Rectangular utility pack with side pouches.'
    },
    'backpack_t3': {
        'id': 'backpack_t3', 'slot': 'backpack', 'tier': 3, 'name': 'Expedition Pack',
        'level_req': 30, 'base_stat': {'stamina_regen': 0.09}, 'description': 'Rigid back panel and three-compartment operations pack.'
    },
}

# Upgrade Level Requirements: Tier -> {1: req_lvl, 2: req_lvl}
UPGRADE_LEVEL_REQS = {
    1: {1: 5, 2: 10},
    2: {1: 20, 2: 25},
    3: {1: 35, 2: 40}
}

# 15 Crafting Materials
EQUIPMENT_MATERIALS = {
    # Fabric
    'fabric_t1': {'id': 'fabric_t1', 'name': 'Ballistic Fabric', 'family': 'fabric', 'tier': 1},
    'fabric_t2': {'id': 'fabric_t2', 'name': 'Aramid Fiber', 'family': 'fabric', 'tier': 2},
    'fabric_t3': {'id': 'fabric_t3', 'name': 'Composite Fiber', 'family': 'fabric', 'tier': 3},

    # Plate
    'plate_t1': {'id': 'plate_t1', 'name': 'Steel Plate', 'family': 'plate', 'tier': 1},
    'plate_t2': {'id': 'plate_t2', 'name': 'Ceramic Plate', 'family': 'plate', 'tier': 2},
    'plate_t3': {'id': 'plate_t3', 'name': 'Composite Plate', 'family': 'plate', 'tier': 3},

    # Binding
    'binding_t1': {'id': 'binding_t1', 'name': 'Nylon Strap', 'family': 'binding', 'tier': 1},
    'binding_t2': {'id': 'binding_t2', 'name': 'Reinforced Binding', 'family': 'binding', 'tier': 2},
    'binding_t3': {'id': 'binding_t3', 'name': 'Titanium Binding', 'family': 'binding', 'tier': 3},

    # Mechanism
    'mechanism_t1': {'id': 'mechanism_t1', 'name': 'Simple Mechanism', 'family': 'mechanism', 'tier': 1},
    'mechanism_t2': {'id': 'mechanism_t2', 'name': 'Precision Mechanism', 'family': 'mechanism', 'tier': 2},
    'mechanism_t3': {'id': 'mechanism_t3', 'name': 'Micro Mechanism', 'family': 'mechanism', 'tier': 3},

    # Calibration Cartridges
    'calibration_t1': {'id': 'calibration_t1', 'name': 'T1 Calibration Cartridge', 'family': 'calibration', 'tier': 1},
    'calibration_t2': {'id': 'calibration_t2', 'name': 'T2 Calibration Cartridge', 'family': 'calibration', 'tier': 2},
    'calibration_t3': {'id': 'calibration_t3', 'name': 'T3 Calibration Cartridge', 'family': 'calibration', 'tier': 3},
}

# Base Crafting Requirements by Slot: {family: count}
SLOT_CRAFT_REQUIREMENTS = {
    'head':     {'fabric': 2, 'plate': 4, 'binding': 2, 'mechanism': 0},
    'body':     {'fabric': 4, 'plate': 6, 'binding': 2, 'mechanism': 0},
    'legs':     {'fabric': 4, 'plate': 4, 'binding': 2, 'mechanism': 0},
    'hands':    {'fabric': 3, 'plate': 0, 'binding': 2, 'mechanism': 3},
    'feet':     {'fabric': 3, 'plate': 2, 'binding': 2, 'mechanism': 1},
    'backpack': {'fabric': 5, 'plate': 0, 'binding': 2, 'mechanism': 1},
}

BASE_CRAFT_GOLD = {1: 100, 2: 300, 3: 900}
UPGRADE_1_GOLD = {1: 75, 2: 225, 3: 675}
UPGRADE_2_GOLD = {1: 125, 2: 375, 3: 1125}
CONVERT_GOLD = {1: 10, 2: 30, 3: 90}

# Sell Prices to Merchant
SELL_PRICES = {
    # Materials
    'materials': {
        'fabric_t1': 3, 'fabric_t2': 9, 'fabric_t3': 27,
        'plate_t1': 3, 'plate_t2': 9, 'plate_t3': 27,
        'binding_t1': 3, 'binding_t2': 9, 'binding_t3': 27,
        'mechanism_t1': 3, 'mechanism_t2': 9, 'mechanism_t3': 27,
        'calibration_t1': 10, 'calibration_t2': 30, 'calibration_t3': 90,
    },
    # Weapon Parts
    'weapon_parts_tier': {1: 3, 2: 9, 3: 27},
    # Base Equipment +0
    'equipment_base': {
        'head': {1: 25, 2: 75, 3: 225},
        'body': {1: 30, 2: 90, 3: 270},
        'legs': {1: 28, 2: 84, 3: 252},
        'hands': {1: 25, 2: 75, 3: 225},
        'feet': {1: 25, 2: 75, 3: 225},
        'backpack': {1: 25, 2: 75, 3: 225},
    },
    # Upgrade additional sell value
    'upgrade_bonus': {
        1: {1: 15, 2: 40},
        2: {1: 45, 2: 120},
        3: {1: 135, 2: 360}
    },
    # Supplies
    'supplies': {
        'faid': 4,
        'medkit': 8
    },
    # Weapons
    'weapons': {
        'shotgun': 8,
        'ak47': 30,
        'flamethrower': 70,
        'rocket': 110
    }
}


def get_equipment_stat(item_id: str, upgrade_level: int = 0) -> Dict[str, float]:
    """Calculates total effective stats for an equipment item at its upgrade level (0, 1, or 2)."""
    base = EQUIPMENT_CATALOG.get(item_id)
    if not base:
        return {}
    slot = base['slot']
    upgrade_level = max(0, min(2, upgrade_level))
    stats = {}

    if slot in ('head', 'body', 'legs'):
        armor = base['base_stat']['armor'] + (1 * upgrade_level)
        stats['armor'] = armor
    elif slot == 'hands':
        reduction = base['base_stat']['reload_speed'] + (0.01 * upgrade_level)
        stats['reload_speed'] = round(reduction, 3)
    elif slot == 'feet':
        speed = base['base_stat']['movement_speed'] + (0.005 * upgrade_level)
        stats['movement_speed'] = round(speed, 4)
    elif slot == 'backpack':
        regen = base['base_stat']['stamina_regen'] + (0.015 * upgrade_level)
        stats['stamina_regen'] = round(regen, 3)

    return stats


def calculate_player_equipment_stats(equipped_dict: Any, levels_dict: Optional[Dict[str, int]] = None) -> Dict[str, float]:
    """Computes aggregate stats from all 6 equipped items. Accepts either (player_dict) or (equipped_dict, levels_dict)."""
    if levels_dict is None and isinstance(equipped_dict, dict) and ('equipped_equipment' in equipped_dict or 'equipment_levels' in equipped_dict):
        levels_dict = equipped_dict.get('equipment_levels', {})
        equipped_dict = equipped_dict.get('equipped_equipment', {})
    elif levels_dict is None:
        levels_dict = {}

    equipped_dict = equipped_dict or {}
    total_armor = 0
    reload_bonus = 0.0
    move_speed_bonus = 0.0
    stamina_regen_bonus = 0.0

    for slot in EQUIPMENT_SLOTS:
        item_id = equipped_dict.get(slot)
        if not item_id or item_id not in EQUIPMENT_CATALOG:
            continue
        upg_lvl = levels_dict.get(item_id, 0)
        item_stats = get_equipment_stat(item_id, upg_lvl)

        if 'armor' in item_stats:
            total_armor += item_stats['armor']
        if 'reload_speed' in item_stats:
            reload_bonus += item_stats['reload_speed']
        if 'movement_speed' in item_stats:
            move_speed_bonus += item_stats['movement_speed']
        if 'stamina_regen' in item_stats:
            stamina_regen_bonus += item_stats['stamina_regen']

    # Clamping rules
    clamped_armor = max(0, min(60, total_armor))
    clamped_reload_bonus = min(0.15, reload_bonus)
    clamped_move_speed = min(0.10, move_speed_bonus)
    clamped_stamina_regen = min(0.30, stamina_regen_bonus)

    # Physical damage reduction multiplier
    damage_multiplier = 100.0 / (100.0 + clamped_armor) if clamped_armor > 0 else 1.0

    return {
        'total_armor': clamped_armor,
        'damage_reduction_pct': round((1.0 - damage_multiplier) * 100.0, 1),
        'damage_multiplier': round(damage_multiplier, 4),
        'reload_speed_reduction': round(clamped_reload_bonus, 3),
        'movement_speed_bonus': round(clamped_move_speed, 4),
        'stamina_regen_bonus': round(clamped_stamina_regen, 3),
    }


def get_craft_recipe(item_id: str) -> Optional[Dict[str, Any]]:
    """Returns material requirements and gold cost for initially crafting an equipment item (+0)."""
    item = EQUIPMENT_CATALOG.get(item_id)
    if not item:
        return None
    slot = item['slot']
    tier = item['tier']
    req_counts = SLOT_CRAFT_REQUIREMENTS[slot]

    required_parts = {}
    for family, count in req_counts.items():
        if count > 0:
            part_id = f"{family}_t{tier}"
            required_parts[part_id] = count

    required_parts[f"calibration_t{tier}"] = 1

    return {
        'item_id': item_id,
        'tier': tier,
        'slot': slot,
        'level_req': item['level_req'],
        'required_parts': required_parts,
        'gold': BASE_CRAFT_GOLD[tier]
    }


def get_upgrade_recipe(item_id: str, current_level: int) -> Optional[Dict[str, Any]]:
    """Returns material requirements and gold cost for upgrading from current_level to next level."""
    if current_level >= 2:
        return None
    item = EQUIPMENT_CATALOG.get(item_id)
    if not item:
        return None

    tier = item['tier']
    target_level = current_level + 1
    req_player_level = UPGRADE_LEVEL_REQS[tier][target_level]

    if target_level == 1:
        # F2 P1 B1 M1 + 1 Calibration
        required_parts = {
            f"fabric_t{tier}": 2,
            f"plate_t{tier}": 1,
            f"binding_t{tier}": 1,
            f"mechanism_t{tier}": 1,
            f"calibration_t{tier}": 1,
        }
        gold = UPGRADE_1_GOLD[tier]
    else:
        # F3 P2 B2 M1 + 2 Calibration
        required_parts = {
            f"fabric_t{tier}": 3,
            f"plate_t{tier}": 2,
            f"binding_t{tier}": 2,
            f"mechanism_t{tier}": 1,
            f"calibration_t{tier}": 2,
        }
        gold = UPGRADE_2_GOLD[tier]

    return {
        'item_id': item_id,
        'target_level': target_level,
        'req_player_level': req_player_level,
        'required_parts': required_parts,
        'gold': gold
    }


def craft_equipment_item(player: Dict[str, Any], item_id: str) -> Tuple[bool, str]:
    """Crafts a new +0 equipment item for the player."""
    recipe = get_craft_recipe(item_id)
    if not recipe:
        return False, "Invalid equipment recipe."

    player_level = player.get('level', 1)
    if player_level < recipe['level_req']:
        return False, f"Level too low. Required level: {recipe['level_req']}."

    owned = player.setdefault('owned_equipment', [])
    if item_id in owned:
        return False, "You already own this equipment."

    gold_cost = recipe['gold']
    if player.get('gold', 0) < gold_cost:
        return False, f"Insufficient gold. Required: {gold_cost} gold."

    parts = player.setdefault('equipment_parts', {})
    calibration = player.setdefault('calibration', {})

    # Check requirements
    for part_id, needed in recipe['required_parts'].items():
        if part_id.startswith('calibration_'):
            if calibration.get(part_id, 0) < needed:
                return False, f"Insufficient calibration cartridges: {part_id} ({calibration.get(part_id, 0)}/{needed})."
        else:
            if parts.get(part_id, 0) < needed:
                return False, f"Insufficient materials: {part_id} ({parts.get(part_id, 0)}/{needed})."

    # Consume resources
    player['gold'] -= gold_cost
    for part_id, needed in recipe['required_parts'].items():
        if part_id.startswith('calibration_'):
            calibration[part_id] -= needed
        else:
            parts[part_id] -= needed

    owned.append(item_id)
    player.setdefault('equipment_levels', {})[item_id] = 0

    # Auto-equip if slot is empty
    equipped = player.setdefault('equipped_equipment', {})
    slot = recipe['slot']
    if not equipped.get(slot):
        equipped[slot] = item_id

    return True, f"{EQUIPMENT_CATALOG[item_id]['name']} successfully crafted!"


def upgrade_equipment_item(player: Dict[str, Any], item_id: str) -> Tuple[bool, str]:
    """Upgrades an owned equipment item to +1 or +2."""
    owned = player.get('owned_equipment', [])
    if item_id not in owned:
        return False, "You do not own this equipment."

    levels = player.setdefault('equipment_levels', {})
    current_level = levels.get(item_id, 0)
    recipe = get_upgrade_recipe(item_id, current_level)
    if not recipe:
        return False, "This equipment is already at maximum level (+2)."

    player_level = player.get('level', 1)
    if player_level < recipe['req_player_level']:
        return False, f"Level too low for upgrade. Required level: {recipe['req_player_level']}."

    gold_cost = recipe['gold']
    if player.get('gold', 0) < gold_cost:
        return False, f"Insufficient gold. Required: {gold_cost} gold."

    parts = player.setdefault('equipment_parts', {})
    calibration = player.setdefault('calibration', {})

    for part_id, needed in recipe['required_parts'].items():
        if part_id.startswith('calibration_'):
            if calibration.get(part_id, 0) < needed:
                return False, f"Insufficient calibration cartridges: {part_id} ({calibration.get(part_id, 0)}/{needed})."
        else:
            if parts.get(part_id, 0) < needed:
                return False, f"Insufficient materials: {part_id} ({parts.get(part_id, 0)}/{needed})."

    # Consume resources
    player['gold'] -= gold_cost
    for part_id, needed in recipe['required_parts'].items():
        if part_id.startswith('calibration_'):
            calibration[part_id] -= needed
        else:
            parts[part_id] -= needed

    levels[item_id] = recipe['target_level']
    return True, f"{EQUIPMENT_CATALOG[item_id]['name']} upgraded to level +{recipe['target_level']}!"


def equip_equipment_item(player: Dict[str, Any], slot: str, item_id: Optional[str]) -> Tuple[bool, str]:
    """Equips or unequips an item in the given slot."""
    if slot not in EQUIPMENT_SLOTS:
        return False, "Invalid equipment slot."

    equipped = player.setdefault('equipped_equipment', {})

    if not item_id:
        equipped.pop(slot, None)
        return True, f"{slot.capitalize()} slot unequipped."

    if item_id not in player.get('owned_equipment', []):
        return False, "You do not own this equipment."

    info = EQUIPMENT_CATALOG.get(item_id)
    if not info or info['slot'] != slot:
        return False, "Equipment cannot be equipped to this slot."

    equipped[slot] = item_id
    return True, f"{info['name']} equipped."


def convert_materials(player: Dict[str, Any], source_id: str, target_id: str) -> Tuple[bool, str]:
    """Converts 3 of source_id material into 1 of target_id material using appropriate gold cost."""
    is_source_cal = source_id.startswith('calibration_')
    is_target_cal = target_id.startswith('calibration_')

    if is_source_cal != is_target_cal:
        return False, "Different material types cannot be converted."

    if is_source_cal:
        s_tier = int(source_id.split('_t')[1])
        t_tier = int(target_id.split('_t')[1])
        if t_tier != s_tier + 1:
            return False, "Can only convert to the next tier calibration cartridge."
        gold_cost = 30 if s_tier == 1 else 90

        cal = player.setdefault('calibration', {})
        if cal.get(source_id, 0) < 3:
            return False, f"At least 3 {source_id} required for conversion."
        if player.get('gold', 0) < gold_cost:
            return False, f"Insufficient gold. Required: {gold_cost} gold."

        player['gold'] -= gold_cost
        cal[source_id] -= 3
        cal[target_id] = cal.get(target_id, 0) + 1
        return True, f"Successfully converted 3x {source_id} into 1x {target_id} cartridge."

    # Normal equipment materials
    s_info = EQUIPMENT_MATERIALS.get(source_id)
    t_info = EQUIPMENT_MATERIALS.get(target_id)
    if not s_info or not t_info:
        return False, "Invalid material."

    if s_info['family'] != t_info['family']:
        return False, "Conversion only allowed within the same material family."

    if t_info['tier'] != s_info['tier'] + 1:
        return False, "Can only convert to the next tier material."

    gold_cost = CONVERT_GOLD.get(s_info['tier'], 10)
    parts = player.setdefault('equipment_parts', {})
    if parts.get(source_id, 0) < 3:
        return False, f"At least 3 {s_info['name']} required for conversion."
    if player.get('gold', 0) < gold_cost:
        return False, f"Insufficient gold. Required: {gold_cost} gold."

    player['gold'] -= gold_cost
    parts[source_id] -= 3
    parts[target_id] = parts.get(target_id, 0) + 1
    return True, f"Successfully converted 3x {s_info['name']} into 1x {t_info['name']}."


def execute_sell(player: Dict[str, Any], category: str, item_key: str, amount: int = 1) -> Tuple[bool, str, int]:
    """Sells items/equipment/weapons for gold according to the fixed price catalog."""
    if amount <= 0:
        return False, "Invalid sale quantity.", 0

    if category == 'materials':
        # Check if in equipment_parts or calibration
        if item_key in SELL_PRICES['materials']:
            unit_price = SELL_PRICES['materials'][item_key]
            if item_key.startswith('calibration_'):
                cal = player.setdefault('calibration', {})
                if cal.get(item_key, 0) < amount:
                    return False, "Insufficient calibration cartridges.", 0
                cal[item_key] -= amount
            else:
                parts = player.setdefault('equipment_parts', {})
                if parts.get(item_key, 0) < amount:
                    return False, "Insufficient materials.", 0
                parts[item_key] -= amount
            total_gold = unit_price * amount
            player['gold'] = player.get('gold', 0) + total_gold
            return True, f"Sold {amount}x material(s). +{total_gold} gold earned.", total_gold

    elif category == 'weapon_parts':
        # Weapon parts stored in list player['weapon_parts'] as {'id': ..., 'tier': ...}
        # item_key is part_id
        from weapon_parts import PART_TIERS, normalize_weapon_parts
        if item_key not in PART_TIERS:
            return False, "Unknown weapon part.", 0
        weapon_parts = normalize_weapon_parts(player.get('weapon_parts'))
        matching = [p for p in weapon_parts if isinstance(p, dict) and p.get('id') == item_key]
        if len(matching) < amount:
            return False, "Insufficient weapon parts.", 0
        tier = PART_TIERS[item_key]
        unit_price = SELL_PRICES['weapon_parts_tier'].get(tier, 3)
        to_remove = amount
        new_list = []
        for p in weapon_parts:
            if isinstance(p, dict) and p.get('id') == item_key and to_remove > 0:
                to_remove -= 1
            else:
                new_list.append(p)
        player['weapon_parts'] = new_list
        total_gold = unit_price * amount
        player['gold'] = player.get('gold', 0) + total_gold
        return True, f"Sold {amount}x weapon part(s). +{total_gold} gold earned.", total_gold

    elif category == 'equipment':
        # item_key is equipment item_id
        owned = player.get('owned_equipment', [])
        if item_key not in owned:
            return False, "You do not own this equipment.", 0
        info = EQUIPMENT_CATALOG.get(item_key)
        if not info:
            return False, "Invalid equipment.", 0

        slot = info['slot']
        tier = info['tier']
        base_val = SELL_PRICES['equipment_base'][slot][tier]
        upg_lvl = player.get('equipment_levels', {}).get(item_key, 0)
        upg_val = SELL_PRICES['upgrade_bonus'].get(tier, {}).get(upg_lvl, 0) if upg_lvl > 0 else 0
        total_gold = base_val + upg_val

        # Unequip if currently equipped
        equipped = player.setdefault('equipped_equipment', {})
        if equipped.get(slot) == item_key:
            equipped.pop(slot, None)

        owned.remove(item_key)
        player.get('equipment_levels', {}).pop(item_key, None)
        player['gold'] = player.get('gold', 0) + total_gold
        return True, f"Sold {info['name']}. +{total_gold} gold earned.", total_gold

    elif category == 'supplies':
        if item_key not in SELL_PRICES['supplies']:
            return False, "Invalid consumable item.", 0
        unit_price = SELL_PRICES['supplies'][item_key]
        inv = player.setdefault('heal_items', {})
        if inv.get(item_key, 0) < amount:
            return False, "Insufficient medical supplies.", 0
        inv[item_key] -= amount
        total_gold = unit_price * amount
        player['gold'] = player.get('gold', 0) + total_gold
        return True, f"Sold {amount}x medical supply. +{total_gold} gold earned.", total_gold

    elif category == 'weapons':
        if item_key == 'glock18':
            return False, "Starter weapon (Glock 18) cannot be sold.", 0
        if item_key not in SELL_PRICES['weapons']:
            return False, "Invalid or unsellable weapon.", 0
        inv = player.setdefault('inventory', {})
        if item_key not in inv:
            return False, "You do not own this weapon.", 0

        total_gold = SELL_PRICES['weapons'][item_key]
        inv.pop(item_key, None)
        player.get('weapon_upgrades', {}).pop(item_key, None)

        # If currently equipped weapon is sold, switch to glock18
        if player.get('weapon') == item_key:
            from inventory import equip_weapon
            equip_weapon(player, 'glock18')

        player['gold'] = player.get('gold', 0) + total_gold
        return True, f"Sold {item_key.upper()} weapon. +{total_gold} gold earned.", total_gold

    return False, "Invalid category.", 0

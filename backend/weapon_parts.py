"""Shared part catalogue and non-destructive compatibility for older saves."""

WEAPON_PARTS = {
    1: ['barrel_common', 'grip_common', 'stock_common', 'spring_common'],
    2: ['barrel_uncommon', 'receiver_uncommon', 'grip_uncommon', 'stock_uncommon'],
    3: ['barrel_rare', 'receiver_rare', 'optic_rare', 'suppressor_rare'],
}
PART_TIERS = {part_id: tier for tier, parts in WEAPON_PARTS.items() for part_id in parts}


def create_weapon_part(part_id):
    """New grants must always include the catalogue's authoritative tier."""
    return {'id': part_id, 'tier': PART_TIERS[part_id]}


def normalize_weapon_parts(parts):
    """Repair known parts without deleting, deduplicating or re-granting items.

    Unknown legacy records remain in persistent storage for investigation.
    """
    result = []
    for part in parts or []:
        if isinstance(part, dict):
            part = dict(part)
            part_id = part.get('id')
            if isinstance(part_id, str) and part_id in PART_TIERS:
                part['tier'] = PART_TIERS[part_id]
        result.append(part)
    return result


def weapon_parts_snapshot(parts):
    result = []
    for part in normalize_weapon_parts(parts):
        if not isinstance(part, dict) or not isinstance(part.get('id'), str):
            continue
        tier = part.get('tier')
        result.append({'id': part['id'], 'tier': tier if type(tier) is int and tier in WEAPON_PARTS else 0})
    return result
import time
from world import WEAPONS


def new_inventory(unlocked=None):
    unlocked = unlocked or ['glock18']
    if 'glock18' not in unlocked:
        unlocked = ['glock18'] + list(unlocked)
    inv = {}
    for w in unlocked:
        if w in WEAPONS:
            inv[w] = {'ammo': WEAPONS[w]['mag'], 'reserve': WEAPONS[w]['reserve']}
    return inv


def inventory_snapshot(player):
    inv = player.get('inventory', {})
    return {key: {
        **({'ammo': player['ammo'], 'reserve': player['reserve']} if key == player['weapon'] else dict(slot)),
        'infinite_reserve': WEAPONS.get(key, {}).get('infinite_reserve', False),
    } for key, slot in inv.items()}


def unlock_weapon(player, weapon):
    if weapon in WEAPONS and weapon not in player.setdefault('inventory', {}):
        player['inventory'][weapon] = {'ammo': WEAPONS[weapon]['mag'], 'reserve': WEAPONS[weapon]['reserve']}
        return True
    return False


def equip_weapon(player, weapon, now=None):
    now = time.monotonic() if now is None else now
    if (player['hp'] <= 0 or not isinstance(weapon, str) or weapon not in WEAPONS or
            weapon not in player.get('inventory', {}) or now < player.get('weapon_ready_at', 0)):
        return False
    if weapon == player['weapon']:
        return True
    player['inventory'][player['weapon']] = {'ammo': player['ammo'], 'reserve': player['reserve']}
    slot = player['inventory'][weapon]
    player.update(weapon=weapon, ammo=slot['ammo'], reserve=slot['reserve'], reload_until=0, trigger=False, weapon_ready_at=now+.3)
    player['controls']['fire'] = False
    return True
import time

from combat import hurt
from world import safe_zone_at
from soldier import RECOVERY_SECONDS, runtime_snapshot


def damage_player(game, player, amount, name, now):
    if player.get('is_soldier'):
        if player.get('hp', 0) <= 0 or player.get('status') == 'recovering' or safe_zone_at(player['x'], player['z']):
            return False
        player['hp'] = max(0, player['hp'] - amount)
        game.events.append({'type': 'damage', 'owner': '', 'target': player['id'], 'amount': amount, 'x': player['x'], 'z': player['z'], 'zombie': False})
        if player['hp'] <= 0:
            player['status'] = 'recovering'
            player['recovery_until_utc'] = time.time() + RECOVERY_SECONDS
            player['reloading_until'] = 0.0
            player['next_shot'] = 0.0
            owner = game.players.get(player.get('owner_id'))
            if owner:
                for record in owner.get('owned_soldiers') or []:
                    if record.get('instance_id') == player.get('id'):
                        record['runtime'] = runtime_snapshot(player)
                        break
            # owner filtering prevents this private alert leaking to observers.
            game.events.append({'type': 'soldier_down', 'owner': player.get('owner_id'), 'soldier_id': player['id'], 'name': player.get('name', 'Companion'), 'slot': int(player.get('slot_index', 0)) + 1})
            if owner and getattr(game, 'persist_progress', None):
                game.persist_progress(owner)
            game.events.append({'type': 'kill', 'owner': '', 'name': name, 'target': player.get('name', 'Companion'), 'x': player['x'], 'z': player['z'], 'zombie': False, 'skin': player.get('skin', 'soldier'), 'weapon': player.get('weapon', 'glock18')})
        return True
    if player['hp'] <= 0 or player['awaiting_input'] or player['protected_until'] > now or safe_zone_at(player['x'], player['z']):
        return False
    hurt(game, player, amount, None, now, source_name=name)
    return True


def apply_status(player, kind, source, name, now, duration=5):
    effects = player.setdefault('statuses', {})
    previous = effects.get(kind, {})
    effects[kind] = {'source': source, 'name': name, 'until': now+duration,
                     'next_tick': previous.get('next_tick', now+1), 'damage': 3 if kind == 'bleeding' else 4}


def dismiss_hive(game, owner):
    game.swarms[:] = [s for s in game.swarms if s['owner'] != owner]
    for player in game.players.values():
        if safe_zone_at(player['x'], player['z']):
            player.get('statuses', {}).clear()
            continue
        poison = player.get('statuses', {}).get('poison')
        if poison and poison['source'] == owner:
            player['statuses'].pop('poison', None)


def update_statuses(game, now):
    for player in game.players.values():
        for kind, effect in list(player.get('statuses', {}).items()):
            source = game.zombies.get(effect['source']) if kind == 'poison' else None
            if player['hp'] <= 0 or now >= effect['until'] or (kind == 'poison' and (not source or source['hp'] <= 0)):
                player['statuses'].pop(kind, None)
                continue
            if now >= effect['next_tick']:
                effect['next_tick'] = now+1
                damage_player(game, player, effect['damage'], effect['name'], now)

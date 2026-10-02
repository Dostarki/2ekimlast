import math
import random
import uuid
from world import WEAPONS, safe_zone_at, wall_distance
from combat_rewards import handle_kill
from loot import player_stat


def targets(game):
    return list(game.zombies.values())+list(game.players.values())+list(game.bosses.values())


def allied_fire_disabled(game, owner, target):
    return bool(owner and not target.get('zombie') and owner.get('alliance_id')
                and owner.get('alliance_id') == target.get('alliance_id')
                and not game.alliances.get(owner['alliance_id'], {}).get('friendly_fire', True))


def apply_armor_reduction(target, amount, source_name):
    if not target.get('zombie') and not target.get('boss') and source_name not in ('Fire', 'Fiery explosion', 'Poison', 'Lava', 'Gas', 'Swarm'):
        eq_stats = target.get('equipment_stats')
        if eq_stats and 'damage_multiplier' in eq_stats:
            amount = max(1, round(amount * eq_stats['damage_multiplier']))
    return amount


def record_damage_feedback(game, target, dealt, owner, now):
    if dealt:
        game.events.append({'type': 'damage', 'owner': owner['id'] if owner else '', 'target': target['id'], 'amount': dealt,
                            'x': target['x'], 'z': target['z'], 'zombie': target.get('zombie', False)})
    if target.get('zombie') and not target.get('boss') and (target['hp'] <= 0 or now-target.get('last_hurt_sound', 0) >= .6):
        target['last_hurt_sound'] = now
        game.events.append({'type': 'enemy_sound', 'action': 'death' if target['hp'] <= 0 else 'hurt', 'enemy_type': target.get('enemy_type', 'normal'), 'owner': target['id'], 'x': target['x'], 'z': target['z']})


def _death_explosion(game, target, now):
    if target.get('zombie') and target.get('enemy_type') == 'immolator' and not target.get('death_exploded'):
        target['death_exploded'] = True
        explode(game, {'id': target['id'], 'kind': 'enemy_fire', 'x': target['x'], 'z': target['z'], 'owner': None}, now)


def hurt(game, target, amount, owner, now, source_name='Fire'):
    if target['hp'] <= 0 or target.get('protected_until', 0) > now:
        return
    if owner is None and not target.get('zombie') and safe_zone_at(target['x'], target['z']):
        return False
    if allied_fire_disabled(game, owner, target):
        return False
    before = target['hp']
    target['hp'] = max(0, before - apply_armor_reduction(target, amount, source_name))
    record_damage_feedback(game, target, before - target['hp'], owner, now)
    if target['hp'] <= 0:
        handle_kill(game, target, owner, now, source_name)
        _death_explosion(game, target, now)
    return True


def explode(game,projectile,now):
    x,z = projectile['x'],projectile['z']
    owner_id = projectile.get('owner') or ''
    owner = game.players.get(owner_id)
    if projectile['kind'] == 'lava':
        game.fires.append({'id':projectile['id'],'x':x,'z':z,'r':3.8,'until':now+8,'owner':projectile['owner'],'last_damage':0})
        radius,damage = 2.8,WEAPONS['lava']['damage']
    elif projectile['kind'] == 'enemy_fire': radius,damage = 6,90
    else: radius,damage = 8,WEAPONS['rocket']['damage']
    game.events.append({'type':'explosion','kind':projectile['kind'],'x':x,'z':z,'r':radius,'owner':owner_id})
    for e in targets(game):
        distance = math.hypot(e['x']-x,e['z']-z)
        if distance < radius and wall_distance(x,z,e['x'],e['z']) > .95:
            hurt(game,e,round(damage*(1-distance/radius*.7)),owner,now,source_name='Fiery explosion' if projectile['kind'] == 'enemy_fire' else 'Fire')


def update_projectiles(game,dt,now):
    for projectile in list(game.projectiles):
        step = min(projectile['remaining'],projectile['speed']*dt)
        x,z = projectile['x'],projectile['z']
        nx,nz = x+projectile['dx']*step,z+projectile['dz']*step
        fraction = wall_distance(x,z,nx,nz)
        # Stop just in front of the surface so the explosion is on the visible side.
        projectile['x'],projectile['z'] = x+(nx-x)*max(0,fraction-.02),z+(nz-z)*max(0,fraction-.02)
        projectile['remaining'] -= step
        impact = fraction < 1 or projectile['remaining'] <= .01
        if projectile['kind'] == 'rocket':
            for e in targets(game):
                if e['id'] == projectile['owner'] or e['hp'] <= 0 or allied_fire_disabled(game, game.players.get(projectile['owner']), e): continue
                vx,vz = e['x']-x,e['z']-z
                along = max(0,min(step,vx*projectile['dx']+vz*projectile['dz']))
                if math.hypot(vx-along*projectile['dx'],vz-along*projectile['dz'])<e.get('radius', .9):
                    projectile['x'],projectile['z']=x+along*projectile['dx'],z+along*projectile['dz']; impact=True; break
        if impact:
            explode(game,projectile,now); game.projectiles.remove(projectile)
    for fire in list(game.fires):
        if now>=fire['until']: game.fires.remove(fire); continue
        if now-fire['last_damage'] < .35: continue
        fire['last_damage']=now
        for e in targets(game):
            if math.hypot(e['x']-fire['x'],e['z']-fire['z'])<fire['r'] and wall_distance(fire['x'],fire['z'],e['x'],e['z'])>.95:
                hurt(game,e,12,game.players.get(fire['owner']),now)


def _can_fire(player, weapon, now):
    return not (player['hp'] <= 0 or now < player.get('weapon_ready_at', 0)
                or player['reload_until'] or player['ammo'] <= 0
                or now - player['last_shot'] < weapon['rate'] - .005)


def _notify_companion(game, player, now):
    companion = getattr(game, 'soldiers', {}).get(player['id'])
    if companion and companion.get('status') == 'active':
        companion['target_aim_x'] = player['x'] + math.sin(player['angle']) * 25.0
        companion['target_aim_z'] = player['z'] + math.cos(player['angle']) * 25.0
        companion['command_lease_until'] = max(companion.get('command_lease_until', 0), now + 1.2)


def _shot_event(player, kind, endpoint, hit=False):
    return {'type': 'shot', 'kind': kind, 'weapon': player['weapon'], 'owner': player['id'],
            'x': player['x'], 'z': player['z'], 'tx': endpoint[0], 'tz': endpoint[1], 'hit': hit}


def _visible_reach(player, weapon, direction):
    dx, dz = direction
    return weapon['range'] * wall_distance(player['x'], player['z'],
        player['x'] + dx * weapon['range'], player['z'] + dz * weapon['range'])


def _can_hit(game, player, target):
    return target['id'] != player['id'] and target['hp'] > 0 and not allied_fire_disabled(game, player, target)


def _fire_projectile(game, player, weapon, now):
    dx, dz = math.sin(player['angle']), math.cos(player['angle'])
    reach = weapon['range'] if weapon['kind'] == 'rocket' else min(weapon['range'], max(3, player.get('aim_distance', 20)))
    game.projectiles.append({'id': uuid.uuid4().hex[:10], 'kind': weapon['kind'], 'owner': player['id'],
        'x': player['x'], 'z': player['z'], 'dx': dx, 'dz': dz,
        'speed': 45 if weapon['kind'] == 'rocket' else 24, 'remaining': reach, 'total': reach})
    game.events.append(_shot_event(player, weapon['kind'], (player['x'] + dx * reach, player['z'] + dz * reach)))


def _fire_flame(game, player, weapon, now):
    dx, dz = math.sin(player['angle']), math.cos(player['angle'])
    reach = _visible_reach(player, weapon, (dx, dz))
    game.events.append(_shot_event(player, 'flame', (player['x'] + dx * reach, player['z'] + dz * reach)))
    for target in targets(game):
        if not _can_hit(game, player, target):
            continue
        ex, ez = target['x'] - player['x'], target['z'] - player['z']
        along = ex * dx + ez * dz
        if (0 < along < reach and abs(ex * dz - ez * dx) < .7 + along * .25
                and wall_distance(player['x'], player['z'], target['x'], target['z']) > .95):
            hurt(game, target, weapon['damage'], player, now)


def _bullet_target(game, player, nearby, ray, now):
    dx, dz, nearest = ray
    target = None
    for candidate in nearby:
        if not _can_hit(game, player, candidate) or candidate.get('protected_until', 0) > now:
            continue
        ex, ez = candidate['x'] - player['x'], candidate['z'] - player['z']
        along = ex * dx + ez * dz
        if 0 < along < nearest and abs(ex * dz - ez * dx) < candidate.get('radius', .72):
            target, nearest = candidate, along
    return target, nearest


def _fire_bullets(game, player, weapon, now):
    reach_box = weapon['range'] + 2
    nearby = [target for target in targets(game) if abs(target['x'] - player['x']) < reach_box
              and abs(target['z'] - player['z']) < reach_box]
    for _ in range(weapon['pellets']):
        angle = player['angle'] + random.uniform(-weapon['spread'], weapon['spread'])
        dx, dz = math.sin(angle), math.cos(angle)
        reach = _visible_reach(player, weapon, (dx, dz))
        target, nearest = _bullet_target(game, player, nearby, (dx, dz, reach), now)
        game.events.append(_shot_event(player, 'bullet',
            (player['x'] + dx * nearest, player['z'] + dz * nearest), hit=target is not None))
        if target:
            hurt(game, target, weapon['damage'], player, now)


def _auto_reload(player, weapon, now):
    if player['ammo'] != 0 or not (weapon.get('infinite_reserve') or player['reserve'] > 0):
        return
    reload_mult = ((1.0 - 0.05 * player_stat(player, 'reload_speed'))
                   * (1.0 - player.get('equipment_stats', {}).get('reload_speed_reduction', 0.0)))
    player['reload_duration'] = max(0.2, weapon['reload'] * reload_mult)
    player['reload_until'] = now + player['reload_duration']


WEAPON_HANDLERS = {'rocket': _fire_projectile, 'lava': _fire_projectile, 'flame': _fire_flame}


def shoot(game, player, now):
    weapon = WEAPONS[player['weapon']]
    if not _can_fire(player, weapon, now):
        return
    if safe_zone_at(player['x'], player['z']):
        if now - player.get('last_safe_zone_shot_warn', 0) >= 1.5:
            player['last_safe_zone_shot_warn'] = now
            game.events.append({'type': 'safe_zone_warning', 'owner': player['id'],
                                'message': 'You cannot fire in the safe zone.'})
        return
    player['last_shot'] = now
    player['ammo'] -= 1
    _notify_companion(game, player, now)
    WEAPON_HANDLERS.get(weapon['kind'], _fire_bullets)(game, player, weapon, now)
    _auto_reload(player, weapon, now)

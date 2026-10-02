import math
import random
import uuid
from world import WEAPONS, safe_zone_at, wall_distance
from enemy_types import ENEMY_TYPES


def targets(game):
    return list(game.zombies.values())+list(game.players.values())+list(game.bosses.values())


def allied_fire_disabled(game, owner, target):
    return bool(owner and not target.get('zombie') and owner.get('alliance_id')
                and owner.get('alliance_id') == target.get('alliance_id')
                and not game.alliances.get(owner['alliance_id'], {}).get('friendly_fire', True))


def hurt(game,target,amount,owner,now,source_name='Fire'):
    if target['hp'] <= 0 or target.get('protected_until',0)>now: return
    # Enemy and environmental effects have no player owner.  Player-originated
    # damage remains subject only to the existing alliance/PvP rule.
    if owner is None and not target.get('zombie') and safe_zone_at(target['x'], target['z']):
        return False
    # Alliance FF only covers deliberate player-on-player attacks. Enemy and world
    # damage have no player owner and therefore remain unaffected.
    if allied_fire_disabled(game, owner, target):
        return False
    if not target.get('zombie') and not target.get('boss') and source_name not in ('Fire', 'Fiery explosion', 'Poison', 'Lava', 'Gas', 'Swarm'):
        eq_stats = target.get('equipment_stats')
        if eq_stats and 'damage_multiplier' in eq_stats:
            amount = max(1, round(amount * eq_stats['damage_multiplier']))
    before = target['hp']
    target['hp'] = max(0,target['hp']-amount)
    dealt = before - target['hp']
    if dealt:
        game.events.append({'type': 'damage', 'owner': owner['id'] if owner else '', 'target': target['id'], 'amount': dealt,
                            'x': target['x'], 'z': target['z'], 'zombie': target.get('zombie', False)})
    if target.get('zombie') and not target.get('boss') and (target['hp'] <= 0 or now-target.get('last_hurt_sound', 0) >= .6):
        target['last_hurt_sound'] = now
        game.events.append({'type': 'enemy_sound', 'action': 'death' if target['hp'] <= 0 else 'hurt', 'enemy_type': target.get('enemy_type', 'normal'), 'owner': target['id'], 'x': target['x'], 'z': target['z']})
    if target['hp'] > 0: return True
    zombie = target.get('zombie',False)
    if owner and owner['id'] != target['id']:
        owner['kills' if zombie else 'pvp'] += 1
        owner['score'] += 2500 if target.get('boss') else 100 if zombie else 25
    game.events.append({'type':'kill','owner':owner['id'] if owner else '', 'name':owner['name'] if owner else source_name, 'target':target['name'] if target.get('boss') else ENEMY_TYPES.get(target.get('enemy_type'), {}).get('name', 'Infected') if zombie else target['name'],'x':target['x'],'z':target['z'],'zombie':zombie,'skin':target.get('skin','soldier'),'weapon':target.get('weapon','ak47'),'enemy_type':target.get('enemy_type','normal'),'boss_type':target.get('boss_type')})
    if target.get('boss'):
        from boss_catalog import boss_died
        boss_died(game, target, now)
    if zombie and target.get('enemy_type') == 'hive':
        # Remove all insects and their active poison in the same simulation tick as the kill.
        from enemy_damage import dismiss_hive
        dismiss_hive(game, target['id'])
    if not zombie:
        target['killer'] = owner['name'] if owner else source_name
        target['died_at'] = now
        game.persist(target)
        # Award level-scaled PvP XP with anti-farm limits (Section 15)
        if owner:
            from pvp_rewards import evaluate_pvp_kill
            from loot import grant_xp
            eval_res = evaluate_pvp_kill(owner, target, now)
            xp_to_grant = eval_res.get('granted_xp', 0)
            if xp_to_grant > 0:
                grant_xp(game, owner, xp_to_grant)
            game.events.append({
                'type': 'xp_gain',
                'owner': owner['id'],
                'source': 'pvp',
                'amount': xp_to_grant,
                'victim_level': eval_res.get('victim_level', 1),
                'reason': eval_res.get('reason', 'valid'),
                'raw_xp': eval_res.get('raw_xp', 0),
            })
    # Generate loot drops from killed zombies/bosses.
    if zombie and owner:
        from loot import generate_loot, grant_xp as _grant_xp
        loot_items = generate_loot(target.get('enemy_type', 'normal'), target['x'], target['z'], now, is_boss=target.get('boss', False))
        for item in loot_items:
            if item.get('auto_pickup'):
                _grant_xp(game, owner, item['amount'])
            else:
                game.loot_drops.append(item)
        # Calibration pity counter
        pity = owner.setdefault('calibration_progress', {'elite_kills': 0, 'boss_kills': 0})
        if target.get('boss'):
            pity['boss_kills'] = pity.get('boss_kills', 0) + 1
            if pity['boss_kills'] >= 5:
                pity['boss_kills'] = 0
                cid = random.choice(['calibration_t2', 'calibration_t3'])
                cal = owner.setdefault('calibration', {})
                cal[cid] = cal.get(cid, 0) + 1
                game.events.append({'type': 'calibration_guaranteed', 'owner': owner['id'], 'calibration_id': cid})
        elif target.get('enemy_type') in ('spitter', 'tank', 'immolator', 'hive', 'stalker', 'witch'):
            pity['elite_kills'] = pity.get('elite_kills', 0) + 1
            if pity['elite_kills'] >= 15:
                pity['elite_kills'] = 0
                cid = 'calibration_t1'
                cal = owner.setdefault('calibration', {})
                cal[cid] = cal.get(cid, 0) + 1
                game.events.append({'type': 'calibration_guaranteed', 'owner': owner['id'], 'calibration_id': cid})
    if zombie and target.get('enemy_type') == 'immolator' and not target.get('death_exploded'):
        target['death_exploded'] = True
        explode(game, {'id': target['id'], 'kind': 'enemy_fire', 'x': target['x'], 'z': target['z'], 'owner': None}, now)
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


def shoot(game,p,now):
    w = WEAPONS[p['weapon']]
    if p['hp'] <= 0 or now < p.get('weapon_ready_at', 0) or p['reload_until'] or p['ammo']<=0 or now-p['last_shot']<w['rate']-.005: return
    if safe_zone_at(p['x'], p['z']):
        if now - p.get('last_safe_zone_shot_warn', 0) >= 1.5:
            p['last_safe_zone_shot_warn'] = now
            game.events.append({'type': 'safe_zone_warning', 'owner': p['id'], 'message': 'You cannot fire in the safe zone.'})
        return
    p['last_shot']=now; p['ammo']-=1
    dx,dz=math.sin(p['angle']),math.cos(p['angle'])

    # Fire-support lease for active companion soldier
    if hasattr(game, 'soldiers') and p['id'] in game.soldiers:
        s = game.soldiers[p['id']]
        if s and s.get('status') == 'active':
            s['target_aim_x'] = p['x'] + dx * 25.0
            s['target_aim_z'] = p['z'] + dz * 25.0
            s['command_lease_until'] = max(s.get('command_lease_until', 0), now + 1.2)

    if w['kind'] in ('rocket','lava'):
        reach = w['range'] if w['kind']=='rocket' else min(w['range'],max(3,p.get('aim_distance',20)))
        projectile={'id':uuid.uuid4().hex[:10],'kind':w['kind'],'owner':p['id'],'x':p['x'],'z':p['z'],'dx':dx,'dz':dz,'speed':45 if w['kind']=='rocket' else 24,'remaining':reach,'total':reach}
        game.projectiles.append(projectile)
        game.events.append({'type':'shot','kind':w['kind'],'weapon':p['weapon'],'owner':p['id'],'x':p['x'],'z':p['z'],'tx':p['x']+dx*reach,'tz':p['z']+dz*reach,'hit':False})
    elif w['kind']=='flame':
        reach=w['range']*wall_distance(p['x'],p['z'],p['x']+dx*w['range'],p['z']+dz*w['range'])
        game.events.append({'type':'shot','kind':'flame','weapon':p['weapon'],'owner':p['id'],'x':p['x'],'z':p['z'],'tx':p['x']+dx*reach,'tz':p['z']+dz*reach,'hit':False})
        for e in targets(game):
            if e['id']==p['id'] or e['hp']<=0 or allied_fire_disabled(game, p, e): continue
            ex,ez=e['x']-p['x'],e['z']-p['z']; along=ex*dx+ez*dz
            if 0<along<reach and abs(ex*dz-ez*dx)<.7+along*.25 and wall_distance(p['x'],p['z'],e['x'],e['z'])>.95:
                hurt(game,e,w['damage'],p,now)
    else:
        reach_box = w['range']+2
        nearby = [e for e in targets(game) if abs(e['x']-p['x']) < reach_box and abs(e['z']-p['z']) < reach_box]
        for _ in range(w['pellets']):
            angle=p['angle']+random.uniform(-w['spread'],w['spread']);dx,dz=math.sin(angle),math.cos(angle)
            reach=w['range']*wall_distance(p['x'],p['z'],p['x']+dx*w['range'],p['z']+dz*w['range'])
            target,nearest=None,reach
            for e in nearby:
                if e['id']==p['id'] or e['hp']<=0 or e.get('protected_until',0)>now or allied_fire_disabled(game, p, e): continue
                ex,ez=e['x']-p['x'],e['z']-p['z']; along=ex*dx+ez*dz
                if 0<along<nearest and abs(ex*dz-ez*dx)<e.get('radius', .72): target,nearest=e,along
            game.events.append({'type':'shot','kind':'bullet','weapon':p['weapon'],'owner':p['id'],'x':p['x'],'z':p['z'],'tx':p['x']+dx*nearest,'tz':p['z']+dz*nearest,'hit':target is not None})
            if target: hurt(game,target,w['damage'],p,now)
    if p['ammo']==0 and (w.get('infinite_reserve') or p['reserve'] > 0):
        from loot import player_stat
        reload_mult = (1.0 - 0.05 * player_stat(p, 'reload_speed')) * (1.0 - p.get('equipment_stats', {}).get('reload_speed_reduction', 0.0))
        actual_reload = max(0.2, w['reload'] * reload_mult)
        p['reload_duration'] = actual_reload
        p['reload_until'] = now + actual_reload

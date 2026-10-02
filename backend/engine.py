import asyncio
import copy
import logging
import math
import random
import time
import uuid
from world import WEAPONS, free, move, interior_at, safe_zone_at
from combat import shoot, update_projectiles
from zombies import update_zombies
from enemy_types import spawn_enemies
from enemy_damage import update_statuses
from boss_catalog import initial_bosses, boss_snapshot
from bosses import update_bosses
from network import ClientChannel
from game_settings import GameSettings, zombie_target
from population import maintain_population, actor_grid, near
from inventory import new_inventory, inventory_snapshot
from weapon_parts import normalize_weapon_parts, weapon_parts_snapshot
from spawning import spawn_position
from bots import update_bots, remove_bot
from loot import (
    pickup_loot, complete_heal, grant_xp,
    max_hp, player_stat, DEFAULT_STATS, HEAL_ITEMS,
    level_from_xp,
)


VIEW = 85


def _compact(e, fields):
    return {k: round(e[k], 2) if isinstance(e[k], float) else e[k] for k in fields}


def actor_view(e, now):
    result = _compact(e, ['id', 'name', 'weapon', 'skin', 'x', 'z', 'angle', 'hp'])
    result['firing'] = e['hp'] > 0 and not e['reload_until'] and now-e['last_shot'] < .24
    result['running'] = math.hypot(e['vx'], e['vz']) > 6.1
    result['reloading'] = max(0, e['reload_until']-now)
    result['reload_duration'] = WEAPONS[e['weapon']]['reload']
    result['alliance_id'] = e.get('alliance_id', '')
    result['equipped_equipment'] = e.get('equipped_equipment') or {}
    return result


def zombie_view(e, now):
    view = e.get('_view')
    if view is None or e.get('_view_at') != now:
        view = {**_compact(e, ['id', 'x', 'z', 'angle', 'hp', 'variant', 'mode']), 'enemy_type': e.get('enemy_type', 'normal'), 'runner': e.get('runner', False),
                'max_hp': e.get('max_hp', 100), 'pack': e.get('pack', ''), 'attacking': e.get('attack_until', 0) > now}
        e['_view'], e['_view_at'] = view, now
    return view


class Game:
    def __init__(self, save_score, save_progress=None):
        self.players, self.zombies = {}, {}
        self.soldiers = {}
        # Alliances intentionally live only for the current server session.
        self.alliances = {}
        self.events, self.drops = [], []
        self.loot_drops = []
        self.projectiles, self.fires = [], []
        self.swarms = []
        self.bosses = initial_bosses()
        self.boss_projectiles, self.boss_zones = [], []
        self.save_score = save_score
        self.save_progress = save_progress
        self.counter = 0
        self.tasks = set()
        self.tick_seq = 0
        self.tick_ms = 0
        self.tick_overruns = 0
        self.settings = GameSettings().model_dump()
        self.zombie_factor = 1
        self.zombie_target = zombie_target(self.settings)
        self.next_population_at = 0
        self.admission_lock = asyncio.Lock()
        self.progress_save_tails = {}

    def progress_snapshot(self, player):
        """Freeze durable data before scheduling async persistence.

        Save jobs must never observe a later roster mutation or look up a
        removed live actor after a disconnect.
        """
        from soldier import runtime_snapshot
        # WebSocket/channel objects are live transport handles and cannot be
        # copied. They are not durable progression in any case.
        snapshot = copy.deepcopy({key: value for key, value in player.items()
                                  if key not in ('ws', 'channel')})
        for soldier in self.soldiers.values():
            if soldier.get('owner_id') == player.get('id'):
                for record in snapshot.get('owned_soldiers') or []:
                    if record.get('instance_id') == soldier.get('id'):
                        record['runtime'] = runtime_snapshot(soldier)
                        break
        return snapshot

    def persist_progress(self, player):
        if player.get('bot') or not self.save_progress or not player.get('account_id'):
            return
        snapshot = self.progress_snapshot(player)
        account_id = snapshot['account_id']
        previous = self.progress_save_tails.get(account_id)

        async def save_in_order():
            if previous:
                try:
                    receipt = await previous
                    # Snapshots queued in the same tick share an old revision.
                    # Advance ONLY over our own successful predecessor, never
                    # over another actor's or an external economy write.
                    if receipt and receipt['owner'] is player:
                        snapshot['revision'] = max(snapshot.get('revision', 1), receipt['revision'])
                except Exception:
                    # A failed older write must not block newer durable state.
                    pass
            expected_revision = snapshot.get('revision', 1)
            await self.save_progress(snapshot)
            if player.get('revision', 1) == expected_revision:
                player['revision'] = snapshot.get('revision')
            return {'owner': player, 'revision': snapshot.get('revision', expected_revision)}

        task = asyncio.create_task(save_in_order())
        self.progress_save_tails[account_id] = task
        def complete(done):
            self.tasks.discard(done)
            if self.progress_save_tails.get(account_id) is done:
                self.progress_save_tails.pop(account_id, None)
            if not done.cancelled() and (error := done.exception()) is not None:
                # Retrieve background failures, while awaited flushes still fail
                # visibly. Never silently discard a failed progress write.
                logging.error('Progress save failed for player %s', player.get('id'),
                              exc_info=(type(error), error, error.__traceback__))
        self.tasks.add(task)
        task.add_done_callback(complete)
        return task

    async def flush_progress(self, player):
        task = self.persist_progress(player)
        if task:
            await task

    async def wait_for_progress(self, account_id):
        """Make a reconnect read the newest queued write for its account."""
        pending = self.progress_save_tails.get(account_id)
        if pending:
            try:
                await pending
            except Exception:
                pass

    def persist(self, player):
        if player.get('bot'):
            return
        if self.save_score:
            task = asyncio.create_task(self.save_score(dict(player)))
            self.tasks.add(task)
            task.add_done_callback(self.tasks.discard)
        self.persist_progress(player)

    async def admit_player(self, session, ws):
        # Called AFTER websocket acceptance: concurrent handshakes cannot overbook.
        async with self.admission_lock:
            if sum(not p.get('bot') for p in self.players.values()) >= 200:
                return None
            if len(self.players) >= 200:
                victim = next((p for p in self.players.values() if p.get('bot')), None)
                if victim is None:
                    return None
                remove_bot(self, victim)
            return self.add_player(session, ws)

    def add_player(self, session, ws, bot=False):
        account_id = session.get('account_id', '')
        saved_progress = session.get('progress') or {}
        player = {
            'id': uuid.uuid4().hex[:12],
            'account_id': account_id,
            'name': session['name'],
            'weapon': saved_progress.get('equipped_weapon', session.get('weapon', 'glock18')),
            'skin': session.get('skin', 'soldier'),
            'ws': ws,
            'bot': bot
        }
        if not bot:
            player['channel'] = ClientChannel(ws)
        self.reset(player, initial=True, saved_progress=saved_progress)
        self.players[player['id']] = player
        return player

    def reset(self, p, initial=False, saved_progress=None):
        now = time.monotonic()
        x, z = (0.0, 0.0) if not p.get('bot') else spawn_position(self)
        p['weapon_ready_at'] = 0
        for key in ('path', 'next_path', 'roam_until', 'roam_x', 'roam_z'):
            p.pop(key, None)

        if initial:
            prog = saved_progress or {}
            p['revision'] = prog.get('revision', 1)
            p['applied_market_order_ids'] = list(prog.get('applied_market_order_ids') or [])
            p['applied_mission_claims'] = copy.deepcopy(prog.get('applied_mission_claims') or {})
            p['applied_delivery_claims'] = copy.deepcopy(prog.get('applied_delivery_claims') or {})
            for field in ('vip_until_utc', 'is_vip', 'bonus_numerator_remainder', 'unlocked_badges', 'active_badge', 'name_color'):
                if field in prog:
                    p[field] = copy.deepcopy(prog[field])
            p['gold'] = prog.get('gold', 150)
            p['xp'] = prog.get('xp', 0)
            p['level'] = prog.get('level', 1)
            p['stat_points'] = prog.get('stat_points', 0)
            p['stats'] = dict(prog.get('stats', DEFAULT_STATS))
            p['heal_items'] = dict(prog.get('heal_items', {'medkit': 1, 'faid': 2}))
            p['weapon_parts'] = normalize_weapon_parts(prog.get('weapon_parts'))
            p['weapon_upgrades'] = dict(prog.get('weapon_upgrades', {}))
            p['equipped_equipment'] = dict(prog.get('equipped_equipment') or {})
            p['owned_equipment'] = list(prog.get('owned_equipment') or [])
            p['equipment_levels'] = dict(prog.get('equipment_levels') or {})
            p['equipment_parts'] = dict(prog.get('equipment_parts') or {})
            p['calibration'] = dict(prog.get('calibration') or {})
            p['calibration_progress'] = dict(prog.get('calibration_progress') or {'elite_kills': 0, 'boss_kills': 0})
            p['owned_soldiers'] = list(prog.get('owned_soldiers') or []) if isinstance(prog.get('owned_soldiers'), list) else None
            p['active_soldier_ids'] = list(prog.get('active_soldier_ids') or []) if isinstance(prog.get('active_soldier_ids'), list) else None
            p['owned_soldier_tiers'] = list(prog.get('owned_soldier_tiers') or [])
            # Old saves held one active tier. Canonical form is a unique owned
            # roster of at most five; keep the scalar for old clients.
            active = prog.get('active_soldier_tiers')
            if not isinstance(active, list):
                active = [prog.get('active_soldier_tier')] if prog.get('active_soldier_tier') else []
            from soldier import canonical_tier, ensure_owned_soldiers
            owned = {canonical_tier(v) for v in p['owned_soldier_tiers']}
            p['owned_soldier_tiers'] = [v for v in dict.fromkeys(canonical_tier(v) for v in p['owned_soldier_tiers']) if v]
            p['active_soldier_tiers'] = [v for v in dict.fromkeys(canonical_tier(v) for v in active) if v in owned][:5]
            p['active_soldier_tier'] = p['active_soldier_tiers'][0] if p['active_soldier_tiers'] else None
            ensure_owned_soldiers(p)
            p['consumables'] = dict(prog.get('consumables') or {'energy_drink': 0})
            p['energy_drink_expires_at'] = prog.get('energy_drink_expires_at')
            unlocked = prog.get('unlocked_weapons') or ['glock18']
            p['inventory'] = dict(prog.get('inventory') or new_inventory(unlocked=unlocked))
            for w in unlocked:
                if w in WEAPONS and w not in p['inventory']:
                    p['inventory'][w] = {'ammo': WEAPONS[w]['mag'], 'reserve': WEAPONS[w]['reserve']}
            equipped = prog.get('equipped_weapon') or p.get('weapon') or 'glock18'
            p['weapon'] = equipped if equipped in p['inventory'] else 'glock18'
        else:
            # Preserved across death/respawn: weapons, parts, upgrades, items, gold, level, and stats persist!
            p.setdefault('gold', 0)
            p.setdefault('xp', 0)
            p.setdefault('level', 1)
            p.setdefault('stat_points', 0)
            p.setdefault('stats', dict(DEFAULT_STATS))
            p.setdefault('heal_items', {})
            p.setdefault('weapon_parts', [])
            p.setdefault('weapon_upgrades', {})
            p.setdefault('inventory', new_inventory())
            p.setdefault('equipped_equipment', {})
            p.setdefault('owned_equipment', [])
            p.setdefault('equipment_levels', {})
            p.setdefault('equipment_parts', {})
            p.setdefault('calibration', {})
            p.setdefault('calibration_progress', {'elite_kills': 0, 'boss_kills': 0})
            p.setdefault('owned_soldier_tiers', [])
            p.setdefault('owned_soldiers', [])
            p.setdefault('active_soldier_ids', [])
            p.setdefault('active_soldier_tier', None)
            p.setdefault('active_soldier_tiers', [p['active_soldier_tier']] if p['active_soldier_tier'] else [])
            p.setdefault('consumables', {'energy_drink': 0})
            p.setdefault('energy_drink_expires_at', None)

        from equipment import calculate_player_equipment_stats
        p['equipment_stats'] = calculate_player_equipment_stats(p.get('equipped_equipment', {}), p.get('equipment_levels', {}))
        # A respawn keeps the companion actors (and their ammo, HP and recovery
        # state) under the player's new id.  Do not create a second roster here.
        has_runtime_roster = any(s.get('owner_id') == p.get('id') for s in self.soldiers.values())
        if p.get('active_soldier_ids') and not p.get('bot') and not has_runtime_roster:
            from soldier import reconcile_soldier_roster
            reconcile_soldier_roster(self, p)

        p['heal_until'] = 0
        p['heal_pending'] = None
        hp = max_hp(p)
        curr_weapon = p.get('weapon', 'glock18')
        if curr_weapon not in WEAPONS:
            curr_weapon = 'glock18'
            p['weapon'] = curr_weapon
        slot = p.get('inventory', {}).get(curr_weapon, {})
        ammo = slot.get('ammo', WEAPONS[curr_weapon]['mag'])
        reserve = slot.get('reserve', WEAPONS[curr_weapon]['reserve'])
        p.update(x=x, z=z, angle=0, hp=hp, ammo=ammo, reserve=reserve, aim_distance=20, vx=0, vz=0,
                 score=0, kills=0, pvp=0, stamina=100, reload_until=0, last_shot=0, killer='',
                 protected_until=now+12, awaiting_input=True, input_time=now, born=now, died_at=0, last_spawn=now, trigger=False,
                 statuses={}, input_seq=0, ack_seq=0, controls={'x': 0, 'z': 0, 'fire': False, 'sprint': False})

    def alliance_snapshot(self, player):
        alliance_id = player.get('alliance_id', '')
        alliance = self.alliances.get(alliance_id)
        if not alliance:
            return None
        members = [self.players[member_id] for member_id in alliance['members'] if member_id in self.players]
        return {
            'id': alliance_id,
            'name': alliance['name'],
            'code': alliance['code'],
            'leader_id': alliance['leader_id'],
            'friendly_fire': alliance['friendly_fire'],
            'members': [{'id': member['id'], 'name': member['name']} for member in members],
        }

    def leave_alliance(self, player):
        alliance_id = player.pop('alliance_id', '')
        alliance = self.alliances.get(alliance_id)
        if not alliance:
            return False
        alliance['members'].discard(player['id'])
        if not alliance['members']:
            self.alliances.pop(alliance_id, None)
        elif alliance['leader_id'] == player['id']:
            alliance['leader_id'] = next(iter(alliance['members']))
        return True

    def create_alliance(self, player, name):
        if not isinstance(name, str):
            return None
        name = ' '.join(name.strip().split())
        if not 2 <= len(name) <= 18 or not all(char.isalnum() or char in ' -' for char in name):
            return None
        self.leave_alliance(player)
        alliance_id = uuid.uuid4().hex[:10]
        code = uuid.uuid4().hex[:6].upper()
        self.alliances[alliance_id] = {'name': name, 'code': code, 'leader_id': player['id'], 'members': {player['id']}, 'friendly_fire': False}
        player['alliance_id'] = alliance_id
        return self.alliance_snapshot(player)

    def join_alliance(self, player, code):
        if not isinstance(code, str):
            return None
        alliance = next((value for value in self.alliances.values() if value['code'] == code.strip().upper()), None)
        if not alliance or len(alliance['members']) >= 12:
            return None
        self.leave_alliance(player)
        alliance['members'].add(player['id'])
        player['alliance_id'] = next(key for key, value in self.alliances.items() if value is alliance)
        return self.alliance_snapshot(player)

    def set_alliance_friendly_fire(self, player, enabled):
        alliance = self.alliances.get(player.get('alliance_id', ''))
        if not alliance or alliance['leader_id'] != player['id'] or not isinstance(enabled, bool):
            return False
        alliance['friendly_fire'] = enabled
        return True

    def respawn(self, p):
        if p['hp'] > 0 or time.monotonic()-p['died_at'] < 10:
            return False
        old_id = p['id']
        p['id'] = uuid.uuid4().hex[:12]
        alliance = self.alliances.get(p.get('alliance_id', ''))
        if alliance:
            alliance['members'].discard(old_id)
            alliance['members'].add(p['id'])
            if alliance['leader_id'] == old_id:
                alliance['leader_id'] = p['id']
        self.players.pop(old_id, None)
        # Soldiers are keyed by their actor id, never by their owner id.  Keep
        # those stable actors across respawn and point them at the new player.
        for soldier in self.soldiers.values():
            if soldier.get('owner_id') == old_id:
                soldier['owner_id'] = p['id']
                soldier['owner_name'] = p.get('name', '')
        self.reset(p)
        self.players[p['id']] = p
        return True

    def spawn_zombies(self, p, count):
        if self.zombie_factor:
            spawn_enemies(self, p, max(1, round(count*self.zombie_factor)))

    def set_input(self, p, data):
        try:
            x, z, angle = float(data.get('x', 0)), float(data.get('z', 0)), float(data.get('angle', 0))
            if not all(math.isfinite(v) for v in (x, z, angle)):
                return
        except (TypeError, ValueError, OverflowError):
            return
        length = max(1, math.hypot(x, z))
        seq = data.get('seq', 0)
        if isinstance(seq, int) and not isinstance(seq, bool) and 0 <= seq <= 9007199254740991:
            p['input_seq'] = max(p['input_seq'], seq)
        p['controls'] = {'x': x/length, 'z': z/length, 'fire': data.get('fire') is True, 'sprint': data.get('sprint') is True}
        p['angle'] = angle % math.tau
        if data.get('fire_pressed') is True and data.get('fire') is True:p['trigger']=True
        try:
            distance=float(data.get('aim_distance',20))
            if math.isfinite(distance): p['aim_distance']=max(3,min(110,distance))
        except (ValueError,TypeError): pass
        p['input_time'] = time.monotonic()
        if p['awaiting_input'] and (abs(x)+abs(z) > .05 or data.get('fire') is True):
            p['awaiting_input'] = False
            p['born'] = p['input_time']
            p['protected_until'] = p['input_time']+12
            p['last_spawn'] = p['input_time']
        # Taking an offensive action cancels protection: no invulnerable firing.
        if data.get('fire') is True:
            p['protected_until'] = 0
        w = WEAPONS[p['weapon']]
        if data.get('reload') and not p['reload_until'] and p['ammo'] < w['mag'] and (w.get('infinite_reserve') or p['reserve'] > 0):
            reload_mult = (1.0 - 0.05 * player_stat(p, 'reload_speed')) * (1.0 - p.get('equipment_stats', {}).get('reload_speed_reduction', 0.0))
            p['reload_until'] = p['input_time']+max(0.2, w['reload']*reload_mult)

    async def send(self, player, data):
        player['channel'].control(data)

    def update(self, dt, now):
        update_bots(self, now)
        for s in self.soldiers.values():
            s['is_soldier'] = True
            s['awaiting_input'] = False
            s['protected_until'] = 0
        # Player input, stamina, respawn protection, healing and loot are
        # player-only.  Companions have their own AI update below.  Keeping
        # their targetability in a separate list avoids treating an NPC actor
        # as a network-controlled player (input_time/controls KeyError).
        living_players = [p for p in self.players.values() if p['hp'] > 0]
        living_targets = living_players + [s for s in self.soldiers.values() if s.get('hp', 0) > 0 and s.get('status') == 'active']
        for p in living_players:
            if p['awaiting_input']:
                p['protected_until'] = now+12
            c = p['controls'] if now-p['input_time'] < .4 else {'x': 0, 'z': 0, 'fire': False, 'sprint': False}
            running = c['sprint'] and p['stamina'] > 1 and (abs(c['x'])+abs(c['z']) > 0)
            # Apply stat bonuses and equipment modifiers: movement speed.
            eq_stats = p.get('equipment_stats', {})
            move_mult = (1.0 + 0.03 * player_stat(p, 'move_speed')) * (1.0 + eq_stats.get('movement_speed_bonus', 0.0))
            base_speed = (10 if running else 6) * move_mult
            speed = base_speed * (.45 if p.get('statuses', {}).get('webbed', {}).get('until', 0) > now else 1)
            p['vx'],p['vz']=c['x']*speed,c['z']*speed
            # Apply stat bonuses and equipment modifiers: stamina regen.
            regen_rate = 13 * (1.0 + 0.08 * player_stat(p, 'stamina_regen')) * (1.0 + eq_stats.get('stamina_regen_bonus', 0.0))
            if float(p.get('energy_drink_expires_at') or 0) > time.time():
                regen_rate *= 2
            p['stamina'] = max(0, min(100, p['stamina']+(-22 if running else regen_rate)*dt))
            move(p, c['x']*speed*dt, c['z']*speed*dt)
            p['ack_seq'] = p['input_seq']
            if p['reload_until'] and now >= p['reload_until']:
                weapon = WEAPONS[p['weapon']]
                missing = max(0, weapon['mag']-p['ammo'])
                amount = missing if weapon.get('infinite_reserve') else min(missing, p['reserve'])
                p['ammo'] += amount
                if not weapon.get('infinite_reserve'):
                    p['reserve'] -= amount
                p['reload_until'] = 0
            if c['fire'] or p['trigger']:
                shoot(self, p, now)
                p['trigger']=False
            # Roadside resupply stations replenish ammo/health once per minute per player.
            sx, sz = round((p['x']-11)/80)*80+11, round(p['z']/80)*80
            if math.hypot(p['x']-sx, p['z']-sz) < 2.6 and now-p.get('supplied', -1000) > 60:
                w=WEAPONS[p['weapon']]
                p['reserve'] = min(w['reserve']*2, p['reserve']+w['mag']*3)
                p['hp'] = min(max_hp(p), p['hp']+30)
                p['supplied'] = now
                grant_xp(self, p, 10)
                self.events.append({'type': 'supply', 'owner': p['id']})
            # Complete pending heal casts.
            complete_heal(self, p, now)
        maintain_population(self, now)
        update_zombies(self, living_targets, dt, now)
        update_projectiles(self,dt,now)
        update_statuses(self, now)
        update_bosses(self, dt, now)
        from soldier import update_soldier
        for s in list(self.soldiers.values()):
            owner = self.players.get(s.get('owner_id'))
            if owner:
                update_soldier(s, owner, self, dt, now)
        # Companions are legal hostile AI targets and retain their own recovery
        # state; never let a roster rebuild refill ammo/HP.
        for s in self.soldiers.values():
            s['is_soldier'] = True
            s['awaiting_input'] = False
            s['protected_until'] = 0
        living_players = [p for p in self.players.values() if p['hp'] > 0]
        # Legacy ammo drops (kept for backward compat but no longer generated).
        for drop in list(self.drops):
            picked = next((p for p in living_players if math.hypot(p['x']-drop['x'], p['z']-drop['z']) < 2), None)
            if picked:
                w=WEAPONS[picked['weapon']]
                picked['reserve'] = min(w['reserve']*2, picked['reserve']+w['mag'])
                picked['hp'] = min(max_hp(picked), picked['hp']+12)
                self.events.append({'type': 'supply', 'owner': picked['id']})
            if picked or drop['expires'] < now:
                self.drops.remove(drop)
        # New loot drop pickup loop.
        for drop in list(self.loot_drops):
            if drop['expires'] < now:
                self.loot_drops.remove(drop)
                continue
            picker = next((p for p in living_players if math.hypot(p['x']-drop['x'], p['z']-drop['z']) < 2.2), None)
            if picker:
                pickup_loot(self, picker, drop, now)
                self.loot_drops.remove(drop)

    def snapshot(self, p, now, shared=None):
        def close(e):
            return (e['x']-p['x'])**2+(e['z']-p['z'])**2 < 85**2
        def compact(e, fields):
            return {k: round(e[k], 2) if isinstance(e[k], float) else e[k] for k in fields}
        # Apply reload-speed stat and equipment reduction to effective reload duration sent to client.
        eq_stats = p.get('equipment_stats') or {}
        reload_mult = (1.0 - 0.05 * player_stat(p, 'reload_speed')) * (1.0 - eq_stats.get('reload_speed_reduction', 0.0))
        me = compact(p, ['id', 'name', 'weapon', 'skin', 'x', 'z', 'angle', 'hp', 'ammo', 'reserve', 'score', 'kills', 'pvp', 'stamina', 'killer','vx','vz'])
        me['interior']=interior_at(p['x'],p['z'])
        me['safe_zone'] = safe_zone_at(p['x'], p['z'])
        me['alliance'] = self.alliance_snapshot(p)
        me['input_seq'] = p['ack_seq']
        me['inventory'] = inventory_snapshot(p)
        me['infinite_reserve'] = WEAPONS[p['weapon']].get('infinite_reserve', False)
        me['respawn_in'] = round(max(0, 10-(now-p['died_at'])), 2) if p['hp'] <= 0 else 0
        me['reload_duration'] = round(WEAPONS[p['weapon']]['reload'] * reload_mult, 3)
        me['statuses'] = {kind: round(max(0, effect['until']-now), 1) for kind, effect in p.get('statuses', {}).items() if effect['until'] > now}
        me.update(reloading=max(0, p['reload_until']-now), protected=max(0, p['protected_until']-now), awaiting_input=p['awaiting_input'], survived=0 if p['awaiting_input'] else int((p['died_at'] or now)-p['born']))
        # New progression fields.
        me['gold'] = p.get('gold', 0)
        me['xp'] = p.get('xp', 0)
        me['level'] = p.get('level', 1)
        me['stat_points'] = p.get('stat_points', 0)
        me['player_stats'] = p.get('stats', DEFAULT_STATS)
        me['max_hp'] = max_hp(p)
        me['heal_items'] = p.get('heal_items') or {}
        expires = float(p.get('energy_drink_expires_at') or 0)
        me['consumables'] = p.get('consumables') or {'energy_drink': 0}
        me['energy_drink_expires_at'] = expires or None
        me['energy_drink_remaining'] = round(max(0, expires - time.time()), 1)
        parts = weapon_parts_snapshot(p.get('weapon_parts'))
        me['weapon_parts_count'] = len(parts)
        me['weapon_parts'] = parts
        upgs = p.get('weapon_upgrades') or {}
        me['weapon_upgrades'] = upgs.get(p['weapon'], {})

        # Equipment & Soldier progression fields
        me['equipped_equipment'] = p.get('equipped_equipment') or {}
        me['owned_equipment'] = p.get('owned_equipment') or []
        me['equipment_levels'] = p.get('equipment_levels') or {}
        me['equipment_parts'] = p.get('equipment_parts') or {}
        me['calibration'] = p.get('calibration') or {}
        me['calibration_progress'] = p.get('calibration_progress') or {'elite_kills': 0, 'boss_kills': 0}
        me['equipment_stats'] = eq_stats
        me['owned_soldier_tiers'] = p.get('owned_soldier_tiers') or []
        # This is per-instance data, separate from the compatibility tier list.
        own_by_id = {s['id']: s for s in self.soldiers.values() if s.get('owner_id') == p['id']}
        soldiers_state = []
        for record in p.get('owned_soldiers') or []:
            runtime = (own_by_id.get(record.get('instance_id')) or record.get('runtime') or {})
            recovering = runtime.get('status') == 'recovering'
            soldiers_state.append({
                'id': record.get('instance_id'), 'instance_id': record.get('instance_id'), 'tier_id': record.get('tier_id'),
                'name': (own_by_id.get(record.get('instance_id')) or {}).get('name', record.get('nickname') or record.get('tier_id', 'Companion')),
                'nickname': record.get('nickname', ''),
                'active': record.get('instance_id') in (p.get('active_soldier_ids') or []),
                'hp': runtime.get('hp', 0 if recovering else None),
                'max_hp': (own_by_id.get(record.get('instance_id')) or {}).get('max_hp'),
                'status': runtime.get('status', 'inactive' if not record.get('active') else 'active'),
                'recovery_time': round(max(0, float(runtime.get('recovery_until_utc') or 0) - time.time()), 1) if recovering else 0,
            })
        me['owned_soldiers'] = soldiers_state
        me['soldiers'] = soldiers_state
        me['active_soldier_ids'] = p.get('active_soldier_ids') or []
        me['active_soldier_tier'] = p.get('active_soldier_tier', None)
        me['active_soldier_tiers'] = p.get('active_soldier_tiers') or []
        own_soldiers = [s for s in self.soldiers.values() if s.get('owner_id') == p['id']]
        soldier = own_soldiers[0] if own_soldiers else None
        if soldier:
            me['soldier'] = {
                'id': soldier['id'],
                'tier': soldier['tier'],
                'tier_name': soldier.get('tier_name', ''),
                'x': round(soldier['x'], 2),
                'z': round(soldier['z'], 2),
                'angle': round(soldier['angle'], 3),
                'hp': soldier['hp'],
                'max_hp': soldier['max_hp'],
                'skin': soldier.get('skin', 'guard'),
                'weapon': soldier.get('weapon', 'glock18'),
                'status': soldier.get('status', 'active'),
                'recovery_time': round(max(0, float(soldier.get('recovery_until_utc') or 0) - time.time()), 1) if soldier.get('status') == 'recovering' else 0,
            }
        else:
            me['soldier'] = None

        heal_rem = round(max(0, p.get('heal_until', 0) - now), 2) if p.get('heal_until') else 0
        me['heal_progress'] = heal_rem
        me['heal_time'] = heal_rem
        me['healing'] = heal_rem > 0
        me['heal_duration'] = round(p.get('heal_duration', 3.0), 2)
        heal_pend = p.get('heal_pending') or {}
        me['heal_item'] = heal_pend.get('item', '')

        _lvl, xp_progress, xp_needed = level_from_xp(p.get('xp', 0))
        me['xp_progress'] = xp_progress
        me['xp_needed'] = xp_needed
        if shared is None:
            shared = self.shared_snapshot(now)
        return {'type': 'state', 'me': me, 'online': len(self.players),
                'seq': self.tick_seq, 'server_time': round(now*1000, 2), 'tick_ms': round(self.tick_ms, 2), 'time_of_day': self.settings['time_of_day'],
                'bosses': shared['bosses'],
                'boss_projectiles': [{k: e[k] for k in ['id', 'owner', 'kind', 'x', 'z', 'y', 'dx', 'dz']} for e in self.boss_projectiles if close(e)],
                'boss_zones': [{k: e[k] for k in ['id', 'owner', 'x', 'z', 'r']} for e in self.boss_zones if close(e)],
                'players': [shared['actors'][e['id']] for e in near(shared['player_grid'], VIEW, p['x'], p['z']) if e['id'] != p['id'] and close(e)],
                'soldiers': [{
                    'id': s['id'],
                    'owner_id': s['owner_id'],
                    'owner_name': s.get('owner_name', ''),
                    'tier': s['tier'],
                    'name': s.get('name', f"Soldier S{s['tier']}"),
                    'tier_name': s.get('name', ''),
                    'x': round(s['x'], 2),
                    'z': round(s['z'], 2),
                    'angle': round(s['angle'], 3),
                    'hp': s['hp'],
                    'max_hp': s['max_hp'],
                    'skin': s.get('skin', 'guard'),
                    'weapon': s.get('weapon', 'glock18'),
                    'equipped_equipment': s.get('equipped_equipment') or {},
                    'status': s.get('status', 'active'),
                    'recovery_time': round(max(0, float(s.get('recovery_until_utc') or 0) - time.time()), 1) if s.get('status') == 'recovering' else 0,
                    'firing': s.get('firing', False),
                } for s in self.soldiers.values() if close(s)],
                'zombies': [zombie_view(e, now) for e in near(shared['zombie_grid'], VIEW, p['x'], p['z']) if close(e)],
                'swarms': [compact(e, ['id', 'owner', 'target', 'x', 'z']) for e in self.swarms if close(e)],
                'projectiles': [compact(e,['id','kind','owner','x','z','dx','dz','remaining','total']) for e in self.projectiles if close(e)],
                'fires': [{**compact(e,['id','x','z','r']), 'ttl':round(e['until']-now,2)} for e in self.fires if close(e)],
                'drops': [{k: e[k] for k in ('id', 'x', 'z')} for e in self.drops if close(e)],
                'loot_drops': [{'id': d['id'], 'kind': d['kind'], 'x': round(d['x'], 1), 'z': round(d['z'], 1), 'tier': d.get('tier', 0), 'part_id': d.get('part_id', ''), 'calibration_id': d.get('calibration_id', '')} for d in self.loot_drops if close(d)],
                'events': [e for e in self.events if (e.get('type') == 'damage' and (e.get('owner') == p['id'] or e.get('target') == p['id'])) or (e.get('type') != 'damage' and (e.get('owner') == p['id'] or 'x' not in e or close(e)))],
                'leaders': shared['leaders']}

    def shared_snapshot(self, now):
        return {'actors': {e['id']: actor_view(e, now) for e in self.players.values()},
                'player_grid': actor_grid(self.players.values(), VIEW),
                'zombie_grid': actor_grid(self.zombies.values(), VIEW),
                'bosses': [boss_snapshot(b, now) for b in self.bosses.values()],
                'leaders': [{k: e[k] for k in ('id', 'name', 'score', 'kills', 'pvp')}
                            for e in sorted(self.players.values(), key=lambda e: -e['score'])[:10]]}

    async def run(self):
        previous = time.monotonic()
        while True:
            now = time.monotonic()
            dt, previous = min(now-previous, .1), now
            try:
                self.events = []
                self.update(dt, now)
                self.tick_seq += 1
                shared = self.shared_snapshot(now)
                for p in list(self.players.values()):
                    if not p.get('bot'):
                        try:
                            p['channel'].offer(self.snapshot(p, now, shared))
                            p.pop('_snapshot_failed', None)
                        except Exception:
                            # One damaged profile must not stop all other players.
                            if not p.get('_snapshot_failed'):
                                logging.exception('Player snapshot failed: %s', p['id'])
                            p['_snapshot_failed'] = True
                if self.tick_seq % 100 == 0:
                    for p in list(self.players.values()):
                        if not p.get('bot') and p.get('account_id'):
                            self.persist_progress(p)
                if not self.players:
                    self.drops.clear()
                    self.loot_drops.clear()
                    self.projectiles.clear()
                    self.fires.clear()
                    self.swarms.clear()
            except Exception:
                logging.exception('World tick failed')
            self.tick_ms = (time.monotonic()-now)*1000
            if self.tick_ms > 50:
                self.tick_overruns += 1
            await asyncio.sleep(max(.001, .05-(time.monotonic()-now)))

"""Real Python/Pymunk simulation running inside a browser Web Worker.

This module has no database, authentication or network dependencies.
"""
import copy
import json
import time
from engine import Game
from game_settings import apply_settings
from inventory import equip_weapon, inventory_snapshot
from loot import use_heal_item, use_consumable, allocate_stat, craft_upgrade
from population import maintain_population
from bots import balance_bots
from equipment import (craft_equipment_item, upgrade_equipment_item,
                       equip_equipment_item, convert_materials, execute_sell,
                       calculate_player_equipment_stats)
from soldier import (recruit_soldier, set_soldier_active, upgrade_soldier,
                     rename_soldier, reconcile_soldier_roster)

# Only gameplay progress leaves this worker. Entitlements, access, VIP and
# payment/delivery metadata remain exclusively server-owned.
PROGRESS_FIELDS = '''gold xp level stat_points stats heal_items consumables
energy_drink_expires_at weapon_parts weapon_upgrades equipped_equipment
owned_equipment equipment_levels equipment_parts calibration calibration_progress
owned_soldier_tiers active_soldier_tier active_soldier_tiers owned_soldiers
active_soldier_ids soldier_schema_version'''.split()


class LocalRuntime:
    def __init__(self, bootstrap):
        self.game = Game(None)
        self.game.local_simulation = True
        apply_settings(self.game, bootstrap['settings'])
        self.player = self.game.add_player(bootstrap, None)
        self.completed = {'score': 0, 'kills': 0, 'pvp': 0}
        self.sequence = 0
        self.revision = bootstrap['progress'].get('revision', 1)
        self.previous = time.monotonic()
        # The worker calls prepare_step cooperatively until the full requested
        # count exists. No fixed iteration count silently caps large worlds.

    def prepare_step(self):
        self.game.next_population_at = 0
        self.game.next_bot_balance = 0
        maintain_population(self.game, time.monotonic())
        balance_bots(self.game, time.monotonic())
        zombies = len(self.game.zombies)
        bots = sum(bool(p.get('bot')) for p in self.game.players.values())
        return json.dumps({'ready': zombies >= self.game.zombie_target and bots == self.game.settings['bot_count'],
                           'zombies': zombies, 'target': self.game.zombie_target, 'bots': bots})

    def configure(self, settings):
        if settings != self.game.settings:
            apply_settings(self.game, settings)

    def tick(self):
        started = time.monotonic()
        dt, self.previous = min(.1, max(0, started - self.previous)), started
        self.game.events = []
        self.game.update(dt, started)
        self.game.tick_seq += 1
        self.game.tick_ms = (time.monotonic() - started) * 1000
        state = self.game.snapshot(self.player, started)
        state['simulation'] = 'local'
        state['population'] = {'zombies': len(self.game.zombies),
                               'bots': sum(bool(p.get('bot')) for p in self.game.players.values())}
        messages = self.player['channel'].controls[:]
        self.player['channel'].controls.clear()
        return json.dumps({'state': state, 'messages': messages})

    def report(self):
        self.sequence += 1
        p = self.game.progress_snapshot(self.player)
        progress = {key: p[key] for key in PROGRESS_FIELDS if key in p}
        progress['inventory'] = inventory_snapshot(p)
        progress['unlocked_weapons'] = list(p['inventory'])
        progress['equipped_weapon'] = p['weapon']
        return json.dumps({'type': 'report', 'sequence': self.sequence,
                           'revision': self.revision, 'progress': progress,
                           'weapon': p['weapon'], 'hp': p['hp'],
                           **{key: self.completed[key] + p[key] for key in self.completed}})

    def action(self, data):
        p, game, now = self.player, self.game, time.monotonic()
        kind = data.get('type')
        if kind == 'input':
            game.set_input(p, data)
            return
        if kind == 'respawn':
            old = {key: p[key] for key in self.completed}
            if game.respawn(p):
                for key in old:
                    self.completed[key] += old[key]
            return
        if p['hp'] <= 0:
            return
        result = None
        if kind == 'equip':
            result = (equip_weapon(p, data.get('weapon')), 'Weapon unavailable.')
        elif kind == 'use_heal':
            use_heal_item(game, p, data.get('item'), now)
        elif kind == 'use_consumable':
            result = use_consumable(game, p, data.get('item_id'), data.get('request_id'))
        elif kind == 'allocate_stat':
            allocate_stat(game, p, data.get('stat'))
        elif kind == 'craft':
            result = (craft_upgrade(game, p, data.get('recipe'), data.get('weapon'), now), 'Check the required parts.')
        elif kind == 'equipment_craft':
            result = craft_equipment_item(p, data.get('item_id'))
        elif kind == 'equipment_upgrade':
            result = upgrade_equipment_item(p, data.get('item_id'))
        elif kind == 'equipment_equip':
            result = equip_equipment_item(p, data.get('slot'), data.get('item_id'))
        elif kind == 'material_convert':
            result = convert_materials(p, data.get('source_id'), data.get('target_id'))
        elif kind == 'sell_item':
            result = execute_sell(p, data.get('category'), data.get('item_key'), int(data.get('amount', 1)))
        elif kind == 'soldier_buy':
            result = recruit_soldier(p)
        elif kind in ('soldier_activate', 'soldier_deactivate'):
            result = set_soldier_active(p, data.get('instance_id'), kind == 'soldier_activate')
        elif kind == 'soldier_upgrade':
            result = upgrade_soldier(p, data.get('instance_id'))
        elif kind == 'soldier_rename':
            result = rename_soldier(p, data.get('instance_id'), data.get('nickname'))
        elif kind.startswith('alliance_'):
            result = (False, 'Survivors have separate worlds; shared combat alliances are unavailable.')
        if kind.startswith('equipment_'):
            p['equipment_stats'] = calculate_player_equipment_stats(p['equipped_equipment'], p['equipment_levels'])
        if kind.startswith('soldier_') and result and result[0]:
            reconcile_soldier_roster(game, p)
        if result and not result[0]:
            p['channel'].control({'type': 'action_error', 'message': result[1]})
        elif result and kind not in ('equip', 'craft'):
            p['channel'].control({'type': 'action_success', 'message': result[1]})

    def acknowledge(self, message):
        self.revision = message['revision']


runtime = None


def initialize(raw):
    global runtime
    runtime = LocalRuntime(json.loads(raw))


def command(raw):
    data = json.loads(raw)
    if data['type'] == 'settings':
        runtime.configure(data['settings'])
    elif data['type'] == 'saved':
        runtime.acknowledge(data)
    else:
        runtime.action(data)
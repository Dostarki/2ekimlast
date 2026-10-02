import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import soldier as soldier_module
import engine as engine_module
from soldier import create_soldier_instance, update_soldier, reconcile_soldier_roster, ensure_owned_soldiers, recruit_soldier, upgrade_soldier, set_soldier_active, rename_soldier
from loot import use_consumable, ENERGY_DRINK_DURATION, ENERGY_DRINK_MAX_STACK
from enemy_damage import damage_player
from engine import Game as EngineGame
from enemy_types import make_enemy


class Game:
    def __init__(self):
        self.players, self.zombies, self.bosses, self.alliances, self.soldiers = {}, {}, {}, {}, {}
        self.events = []


def owner():
    return {'id': 'owner', 'name': 'Owner', 'x': 0., 'z': 0., 'angle': 0., 'hp': 100,
            'alliance_id': '', 'protected_until': 0}


def test_five_unique_slots_keep_actor_state_and_formation():
    game = Game(); player = owner(); player['owned_soldier_tiers'] = [f'soldier_s{i}' for i in range(1, 6)]; player['active_soldier_tiers'] = list(player['owned_soldier_tiers'])
    reconcile_soldier_roster(game, player)
    actors = list(game.soldiers.values())
    assert len({a['id'] for a in actors}) == 5
    assert [a['slot_index'] for a in actors] == [0, 1, 2, 3, 4]
    actors[2]['ammo'] = 4
    player['active_soldier_ids'] = [a['id'] for a in actors if a['tier_id'] != 'soldier_s2']
    reconcile_soldier_roster(game, player)
    kept = next(s for s in game.soldiers.values() if s['tier_id'] == 'soldier_s3')
    assert len(game.soldiers) == 4 and kept['ammo'] == 4
    player['active_soldier_ids'].append('invalid')
    reconcile_soldier_roster(game, player)
    assert 'invalid' not in player['active_soldier_ids']


def test_old_scalar_migrates_to_unique_owned_roster():
    game = EngineGame(None)
    progress = {'owned_soldier_tiers': ['soldier_s1', 'soldier_s2', 'soldier_s3', 'soldier_s4', 'soldier_s5'],
                'active_soldier_tier': 'soldier_s3'}
    player = game.add_player({'name': 'Migration', 'skin': 'soldier', 'progress': progress}, None)
    assert player['active_soldier_tiers'] == ['soldier_s3']
    assert len([s for s in game.soldiers.values() if s['owner_id'] == player['id']]) == 1


def test_real_engine_idle_owner_soldier_shoots_and_damages_target():
    game = EngineGame(None); game.zombie_factor = 0
    player = game.add_player({'name': 'LiveShot', 'skin': 'soldier', 'progress': {
        'owned_soldier_tiers': ['soldier_s1'], 'active_soldier_tiers': ['soldier_s1']}}, None)
    # This is deliberately outside the centre safe zone and uses the real world
    # collision/LOS functions, Game tick and enemy fixture.
    player.update(x=100., z=0., awaiting_input=False, protected_until=0, controls={'x': 0, 'z': 0, 'fire': False, 'sprint': False})
    soldier = next(iter(game.soldiers.values())); soldier.update(x=100., z=0.)
    game.zombies.clear(); target = make_enemy(1, 100., 10.); game.zombies[target['id']] = target
    before_hp, before_ammo = target['hp'], soldier['ammo']
    for index in range(20): game.update(.05, 100. + index * .05)
    shots = [event for event in game.events if event.get('type') == 'shot']
    assert shots and all(event.get('soldier_id') == soldier['id'] for event in shots)
    assert target['hp'] < before_hp and soldier['ammo'] < before_ammo


def test_individual_recruits_upgrade_and_rejections_preserve_other_runtime():
    player = owner(); player.update(gold=8000, level=40, owned_soldiers=[], owned_soldier_tiers=[])
    recruited = [recruit_soldier(player) for _ in range(5)]
    assert all(result[0] for result in recruited)
    ids = [result[2]['instance_id'] for result in recruited]
    assert len(set(ids)) == 5 and [record['tier_id'] for record in player['owned_soldiers']] == ['soldier_s1'] * 5
    gold_before_sixth = player['gold']; assert not recruit_soldier(player)[0] and player['gold'] == gold_before_sixth
    other = player['owned_soldiers'][1]; other['runtime'] = {'hp': 31, 'ammo': 2, 'reserve': 7}
    for expected in range(2, 6):
        ok, _msg, record = upgrade_soldier(player, ids[0]); assert ok and record['tier_id'] == f'soldier_s{expected}'
    assert other['tier_id'] == 'soldier_s1' and other['runtime'] == {'hp': 31, 'ammo': 2, 'reserve': 7}
    assert not upgrade_soldier(player, ids[0])[0]
    assert not upgrade_soldier(player, 'not-owned')[0]
    poor = owner(); poor.update(gold=499, level=40, owned_soldier_tiers=[]); assert not recruit_soldier(poor)[0]


def test_soldier_nickname_is_instance_owned_and_never_mutates_runtime():
    player = owner(); player.update(owned_soldiers=[{'instance_id': 'first', 'tier_id': 'soldier_s1', 'active': True, 'runtime': {'hp': 21, 'ammo': 2, 'reserve': 6, 'status': 'recovering', 'recovery_until_utc': 1200}}], active_soldier_ids=['first'])
    before = dict(player['owned_soldiers'][0]['runtime'])
    ok, _message, record = rename_soldier(player, 'first', '  \u00dcmit  ')
    assert ok and record['nickname'] == 'Ümit' and record['runtime'] == before
    assert not rename_soldier(player, 'other-owner-instance', 'Taken')[0]
    assert not rename_soldier(player, 'first', 'bad\nname')[0]
    assert not rename_soldier(player, 'first', 'x' * 25)[0]


def test_legacy_migration_is_stable_and_deactivation_keeps_runtime():
    player = owner(); player.update(owned_soldiers=[], owned_soldier_tiers=['soldier_s1', 'soldier_s3'], active_soldier_tiers=['soldier_s3'])
    first = ensure_owned_soldiers(player); first_ids = [record['instance_id'] for record in first]
    assert [record['tier_id'] for record in first] == ['soldier_s1', 'soldier_s3']
    assert [record['instance_id'] for record in ensure_owned_soldiers(player)] == first_ids
    game = Game(); player.update(x=100., z=0.); reconcile_soldier_roster(game, player)
    active_id = player['active_soldier_ids'][0]; actor = game.soldiers[active_id]; actor.update(hp=23, ammo=1, reserve=4)
    assert set_soldier_active(player, active_id, False)[0]; reconcile_soldier_roster(game, player)
    assert not game.soldiers and next(r for r in player['owned_soldiers'] if r['instance_id'] == active_id)['runtime']['ammo'] == 1
    assert set_soldier_active(player, active_id, True)[0]; reconcile_soldier_roster(game, player)
    restored = game.soldiers[active_id]; assert (restored['hp'], restored['ammo'], restored['reserve']) == (23, 1, 4)


def test_autonomous_nearest_approach_and_filters(monkeypatch):
    monkeypatch.setattr(soldier_module, 'free', lambda *_args: True)
    monkeypatch.setattr(soldier_module, 'safe_zone_at', lambda *_args: False)
    monkeypatch.setattr(soldier_module, 'wall_distance', lambda *_args: 1.0)
    game, p = Game(), owner(); p['x'] = 100.; game.players[p['id']] = p
    s = create_soldier_instance('soldier_s1', p['id'], p['name'], 100, 0)
    # Outside fire range but within acquisition range: companion advances.
    game.zombies['near'] = {'id': 'near', 'x': 100., 'z': 30., 'hp': 50, 'zombie': True}
    game.zombies['far'] = {'id': 'far', 'x': 100., 'z': 34., 'hp': 50, 'zombie': True}
    before = s['z']; update_soldier(s, p, game, .5, 10.)
    assert s['z'] > before
    # Same-alliance player at point-blank range remains ineligible even when
    # friendly fire is enabled; a nearby zombie remains the selected target.
    p['alliance_id'] = 'a'; game.alliances['a'] = {'friendly_fire': True}
    game.players['ally'] = {'id': 'ally', 'x': s['x'], 'z': s['z'] + 1., 'hp': 100, 'alliance_id': 'a', 'protected_until': 0}
    update_soldier(s, p, game, .1, 11.)
    assert s.get('target_aim_x') == 100.


def test_autonomous_rejects_safezone_and_wall(monkeypatch):
    game, p = Game(), owner(); p.update(x=100., z=0.); game.players[p['id']] = p
    s = create_soldier_instance('soldier_s1', p['id'], p['name'], 100, 0)
    game.zombies['z'] = {'id': 'z', 'x': 100., 'z': 8., 'hp': 50, 'zombie': True}
    monkeypatch.setattr(soldier_module, 'free', lambda *_: True)
    monkeypatch.setattr(soldier_module, 'safe_zone_at', lambda x, _z: x == 100.)
    update_soldier(s, p, game, .1, 2.)
    assert not game.events
    monkeypatch.setattr(soldier_module, 'safe_zone_at', lambda *_: False)
    monkeypatch.setattr(soldier_module, 'wall_distance', lambda *_: .5)
    update_soldier(s, p, game, .1, 3.)
    assert not game.events and s.get('target_aim_x') is None


def test_empty_companion_only_resupplies_after_safe_zone_dwell(monkeypatch):
    game, p = Game(), owner(); p.update(x=100., z=0.); game.players[p['id']] = p
    soldier = create_soldier_instance('soldier_s1', p['id'], p['name'], 100, 0); soldier.update(ammo=0, reserve=0)
    monkeypatch.setattr(soldier_module, 'safe_zone_at', lambda *_: False)
    update_soldier(soldier, p, game, .1, 10.); assert soldier['ammo'] == 0
    monkeypatch.setattr(soldier_module, 'safe_zone_at', lambda *_: True)
    update_soldier(soldier, p, game, .1, 14.9); assert soldier['ammo'] == 0
    update_soldier(soldier, p, game, .1, 15.1)
    assert soldier['ammo'] == soldier['mag'] and soldier['reserve'] == soldier['mag'] * 3


def test_soldier_hurt_recovers_120_seconds_and_energy_refresh_replay_cap(monkeypatch):
    game, p = Game(), owner(); p['x'] = 100.
    s = create_soldier_instance('soldier_s1', 'owner', 'Owner', 100, 0); s['is_soldier'] = True
    monkeypatch.setattr('enemy_damage.time.time', lambda: 1000.)
    assert damage_player(game, s, 999, 'Zombie', 10.)
    assert s['status'] == 'recovering' and s['recovery_until_utc'] == 1120.
    p.update(consumables={'energy_drink': ENERGY_DRINK_MAX_STACK}, energy_drink_expires_at=None)
    assert use_consumable(game, p, 'energy_drink', 'r1', now_utc=1000)[0]
    assert p['energy_drink_expires_at'] == 1000 + ENERGY_DRINK_DURATION
    assert use_consumable(game, p, 'energy_drink', 'r1', now_utc=1001)[0]
    assert p['consumables']['energy_drink'] == ENERGY_DRINK_MAX_STACK - 1
    assert use_consumable(game, p, 'energy_drink', 'r2', now_utc=1010)[0]
    assert p['energy_drink_expires_at'] == 1010 + ENERGY_DRINK_DURATION


def test_each_soldier_keeps_its_own_utc_deadline_across_toggle_upgrade_and_restore(monkeypatch):
    clock = {'utc': 1000.}
    monkeypatch.setattr(soldier_module.time, 'time', lambda: clock['utc'])
    monkeypatch.setattr('enemy_damage.time.time', lambda: clock['utc'])
    game, player = Game(), owner(); player.update(x=100., z=0.)
    player.update(gold=5000, level=40, owned_soldier_tiers=['soldier_s1'], active_soldier_tiers=['soldier_s1'])
    player['owned_soldiers'] = [
        {'instance_id': 'a', 'tier_id': 'soldier_s1', 'active': True, 'runtime': {}},
        {'instance_id': 'b', 'tier_id': 'soldier_s1', 'active': True, 'runtime': {}},
    ]; player['active_soldier_ids'] = ['a', 'b']
    reconcile_soldier_roster(game, player)
    first, second = game.soldiers['a'], game.soldiers['b']; first['is_soldier'] = second['is_soldier'] = True
    first.update(x=100., z=0.); second.update(x=100., z=1.)
    damage_player(game, first, 999, 'Zombie', 0.)
    clock['utc'] = 1010.; damage_player(game, second, 999, 'Zombie', 0.)
    assert first['recovery_until_utc'] == 1120 and second['recovery_until_utc'] == 1130
    set_soldier_active(player, 'a', False); reconcile_soldier_roster(game, player)
    assert player['owned_soldiers'][0]['runtime']['recovery_until_utc'] == 1120
    upgrade_soldier(player, 'a')
    set_soldier_active(player, 'a', True); reconcile_soldier_roster(game, player)
    clock['utc'] = 1119.; update_soldier(game.soldiers['a'], player, game, .1, 999999.)
    assert game.soldiers['a']['status'] == 'recovering'
    clock['utc'] = 1120.; update_soldier(game.soldiers['a'], player, game, .1, 0.)
    assert game.soldiers['a']['status'] == 'active' and game.soldiers['b']['status'] == 'recovering'


def test_progress_saves_freeze_actor_state_and_complete_in_account_order():
    saved = []

    async def save(snapshot):
        await asyncio.sleep(.01 if not saved else 0)
        saved.append(snapshot)

    async def flow():
        game = EngineGame(None, save_progress=save)
        player = game.add_player({'name': 'Persist', 'skin': 'soldier', 'account_id': 'same-account', 'progress': {
            'owned_soldiers': [{'instance_id': 'persist-soldier', 'tier_id': 'soldier_s1', 'active': True, 'runtime': {}}],
            'active_soldier_ids': ['persist-soldier']}}, None)
        actor = game.soldiers['persist-soldier']; actor.update(hp=0, status='recovering', recovery_until_utc=2120.)
        first = game.persist_progress(player)
        actor['recovery_until_utc'] = 2240.
        second = game.persist_progress(player)
        await game.wait_for_progress('same-account')
        assert first.done() and second.done()
    asyncio.run(flow())
    first_runtime = saved[0]['owned_soldiers'][0]['runtime']
    second_runtime = saved[1]['owned_soldiers'][0]['runtime']
    assert first_runtime['recovery_until_utc'] == 2120 and second_runtime['recovery_until_utc'] == 2240


def test_energy_engine_tick_expiry_cap_and_snapshot(monkeypatch):
    now = {'value': 1000.}
    monkeypatch.setattr(engine_module.time, 'time', lambda: now['value'])
    game = EngineGame(None); game.zombie_factor = 0
    p = game.add_player({'name': 'Energy', 'skin': 'soldier', 'progress': {'consumables': {'energy_drink': 1}, 'energy_drink_expires_at': 1060}}, None)
    p['awaiting_input'] = False; p['stamina'] = 50.; p['controls'] = {'x': 0, 'z': 0, 'fire': False, 'sprint': False}; p['input_time'] = 1000.
    game.update(.5, 1000.)
    assert p['stamina'] == 63.  # base 13/s, doubled then clamped by update
    state = game.snapshot(p, 1000.)['me']
    assert state['consumables']['energy_drink'] == 1 and state['energy_drink_remaining'] == 60
    now['value'] = 1061.; p['stamina'] = 50.; game.update(.5, 1061.)
    assert p['stamina'] == 56.5

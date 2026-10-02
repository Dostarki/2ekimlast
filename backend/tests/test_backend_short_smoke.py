"""Kısa odaklı DEADZONE backend smoke + birim testleri (uzun e2e yok)."""

import hashlib
import os
import sys
from pathlib import Path

import requests

sys.path.insert(0, "/app/backend")
import combat as combat_module

from combat import hurt, shoot, update_projectiles
from engine import Game
from world import WEAPONS, free, interior_at
from zombies import update_zombies


def _base_url() -> str:
    base = os.environ.get("REACT_APP_BACKEND_URL", "").strip()
    if not base:
        env_file = Path("/app/frontend/.env")
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.startswith("REACT_APP_BACKEND_URL="):
                    base = line.split("=", 1)[1].strip()
                    if base:
                        os.environ["REACT_APP_BACKEND_URL"] = base
                    break
    if not base:
        raise RuntimeError("REACT_APP_BACKEND_URL is required")
    return base.rstrip("/")


BASE_URL = _base_url()


async def _noop_save_score(_player):
    return None


def _player(pid: str, name: str, weapon: str, x: float, z: float):
    return {
        "id": pid,
        "name": name,
        "weapon": weapon,
        "x": x,
        "z": z,
        "angle": 0.0,
        "hp": 100,
        "ammo": WEAPONS[weapon]["mag"],
        "reserve": WEAPONS[weapon]["reserve"],
        "score": 0,
        "kills": 0,
        "pvp": 0,
        "protected_until": 0,
        "reload_until": 0,
        "last_shot": -999.0,
        "awaiting_input": False,
    }


# Module: Public API smoke checks (/api/world, /api/weapons) + static audio samples
def test_public_api_and_static_audio_smoke():
    s = requests.Session()

    weapons = s.get(f"{BASE_URL}/api/weapons", timeout=12)
    assert weapons.status_code == 200
    weapons_data = weapons.json()
    assert set(weapons_data) == set(WEAPONS)
    assert 'glock18' in weapons_data
    assert {"m4", "rocket", "minigun", "flamethrower", "lava"}.issubset(weapons_data.keys())

    world = s.get(f"{BASE_URL}/api/world", timeout=12)
    assert world.status_code == 200
    chunks = world.json().get("chunks", [])
    origin = next(c for c in chunks if c["id"] == "0,0")
    enterable = [h for h in origin["houses"] if h.get("enterable")]
    assert {"gas", "hotel", "home"}.issubset({h["kind"] for h in enterable})

    sample_1 = s.get(f"{BASE_URL}/audio/ak47.wav", timeout=12)
    sample_2 = s.get(f"{BASE_URL}/audio/reload.wav", timeout=12)
    assert sample_1.status_code == 200
    assert sample_2.status_code == 200


# Module: Current 15m acquisition and permanent pursuit until target disconnects.
def test_zombie_distance_modes_idle_attack_and_pursuit_end(monkeypatch):
    game = Game(_noop_save_score)
    now = 100.0

    monkeypatch.setattr('zombies.wall_distance', lambda *_args: 1.0)
    # 16m: an unseen target must not trigger normal enemy acquisition.
    z1 = {"id": "z1", "x": 0.0, "z": 0.0, "angle": 0.0, "hp": 100, "zombie": True, "variant": 0, "speed": 0.55, "last_attack": 0, "mode": "idle", "wander_until": now + 10}
    game.zombies = {"z1": z1}
    p_far = _player("p1", "Far", "ak47", 0.0, 16.0)
    update_zombies(game, [p_far], dt=1.0, now=now)
    assert z1["mode"] == "idle"

    # 14.9m + LOS clear: must switch to attack and remember the target.
    z2 = {"id": "z2", "x": 0.0, "z": 0.0, "angle": 0.0, "hp": 100, "zombie": True, "variant": 0, "speed": 0.55, "last_attack": 0, "mode": "wander", "wander_until": 0}
    game.zombies = {"z2": z2}
    p_near = _player("p2", "Near", "ak47", 0.0, 14.9)
    game.players[p_near['id']] = p_near
    update_zombies(game, [p_near], dt=0.2, now=now)
    assert z2["mode"] == "attack"

    # Leaving the acquisition radius does not end pursuit anymore.
    p_near['z'] = 40.0
    update_zombies(game, [p_near], dt=0.2, now=now + 0.2)
    assert z2['mode'] == 'attack' and z2['target_id'] == p_near['id']
    game.players.clear()
    # Empty regions sleep without moving; target cleanup resumes on activation.
    last_position = (z2['x'], z2['z'])
    update_zombies(game, [], dt=0.2, now=now + 0.4)
    assert (z2['x'], z2['z']) == last_position
    observer = _player('observer', 'Observer', 'ak47', 0.0, 70.0)
    game.players[observer['id']] = observer
    update_zombies(game, [observer], dt=0.2, now=now + 0.6)
    assert z2['target_id'] == ''
    assert z2["mode"] in {"idle", "wander"}


# Module: Enterable interiors and collision checks for gas/hotel/home at origin chunk
def test_world_enterable_points_and_interior_mapping():
    assert free(26.0, 16.5) is True  # gas station door
    assert free(26.0, 18.8) is True  # gas front corridor inside
    assert free(17.5, 25.0) is False  # gas side wall
    assert interior_at(26.0, 25.0) == "WESTFALL GAS STATION"

    assert free(56.0, 16.5) is True  # hotel door
    assert interior_at(56.0, 23.0) == "WESTFALL HOTEL"
    assert free(23.0, 52.5) is True  # home door
    assert interior_at(23.0, 59.0) == "ABANDONED HOUSE"


# Module: Interiors protect against enemies/environment, not player-originated PvP.
def test_interior_blocks_environment_damage_but_not_pvp():
    game = Game(_noop_save_score)
    target = _player("p_inside", "Inside", "ak47", 26.0, 25.0)
    target["protected_until"] = 0
    game.players[target["id"]] = target

    hurt(game, target, amount=20, owner=None, now=1.0)
    assert target["hp"] == 100
    attacker = _player('attacker', 'Attacker', 'ak47', 0.0, 70.0)
    hurt(game, target, amount=20, owner=attacker, now=1.0)
    assert target["hp"] == 80


# Module: Projectile + fire mechanics (rocket AoE, lava pool ttl/pulse, flamethrower cone, ammo usage)
def test_combat_projectiles_fire_and_ammo(monkeypatch):
    game = Game(_noop_save_score)
    game.persist = lambda _p: None
    monkeypatch.setattr(combat_module, 'wall_distance', lambda *_args, **_kwargs: 1.0)
    # Isolate weapon mechanics from separately tested sanctuary restrictions.
    monkeypatch.setattr(combat_module, 'safe_zone_at', lambda *_args: False)
    now = 200.0

    owner = _player("owner", "Owner", "rocket", 0.0, 0.0)
    victim = _player("victim", "Victim", "ak47", 0.0, 7.9)
    game.players[owner["id"]] = owner
    game.players[victim["id"]] = victim

    shoot(game, owner, now)
    assert any(p["kind"] == "rocket" for p in game.projectiles)
    game.projectiles[0]["remaining"] = 0.0
    update_projectiles(game, dt=0.05, now=now + 0.05)
    assert victim["hp"] < 100

    owner_lava = _player("owner_lava", "Lava", "lava", 10.0, 0.0)
    target_lava = _player("target_lava", "T2", "ak47", 11.0, 1.0)
    game.players[owner_lava["id"]] = owner_lava
    game.players[target_lava["id"]] = target_lava
    shoot(game, owner_lava, now + 1)
    lava_proj = next(p for p in game.projectiles if p["kind"] == "lava")
    lava_proj["remaining"] = 0.0
    update_projectiles(game, dt=0.05, now=now + 1.05)
    fire = game.fires[-1]
    assert round(fire["until"] - (now + 1.05), 1) == 8.0
    hp_before = target_lava["hp"]
    update_projectiles(game, dt=0.4, now=now + 1.5)
    assert target_lava["hp"] < hp_before

    flame_owner = _player("flame", "Flame", "flamethrower", -100.0, -100.0)
    front = _player("front", "Front", "ak47", -100.0, -92.0)
    side = _player("side", "Side", "ak47", -95.0, -100.0)
    far = _player("far", "Far", "ak47", -100.0, -90.0)
    for p in (flame_owner, front, side, far):
        game.players[p["id"]] = p
    shoot(game, flame_owner, now + 2)
    assert front["hp"] < 100 and side["hp"] == 100 and far["hp"] == 100

    m4_user = _player("m4u", "M4", "m4", 0.0, -10.0)
    mini_user = _player("miniu", "Mini", "minigun", 0.0, -20.0)
    game.players[m4_user["id"]] = m4_user
    game.players[mini_user["id"]] = mini_user
    m4_before, mini_before = m4_user["ammo"], mini_user["ammo"]
    shoot(game, m4_user, now + 3)
    shoot(game, mini_user, now + 3)
    assert m4_user["ammo"] == m4_before - 1 and mini_user["ammo"] == mini_before - 1


# Module: Real static audio files + credits consistency checks
def test_audio_assets_hashes_and_credits():
    audio_dir = Path("/app/frontend/public/audio")
    wavs = sorted(audio_dir.glob("*.wav"))
    assert len(wavs) == 11

    weapon_files = ["ak47", "ak117", "ak107", "m4", "shotgun", "rocket", "minigun", "flamethrower", "lava"]
    hashes = []
    for key in weapon_files:
        blob = (audio_dir / f"{key}.wav").read_bytes()
        hashes.append(hashlib.sha256(blob).hexdigest())
    assert len(set(hashes)) == 9

    credits = Path("/app/frontend/public/audio/CREDITS.txt").read_text(encoding="utf-8")
    assert "CC0 1.0" in credits and "Attribution-ShareAlike 3.0" in credits

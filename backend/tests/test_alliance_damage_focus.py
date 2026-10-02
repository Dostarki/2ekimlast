"""Focused alliance and damage-event contracts; uses only the standard library."""
import sys
import unittest

sys.path.insert(0, "backend")

import combat as combat_module
from combat import hurt, shoot, update_projectiles
from engine import Game
from world import WEAPONS


class AllianceDamageFocusTests(unittest.TestCase):
    def setUp(self):
        self.game = Game(lambda _player: None)
        # Origin is the permanent safe zone; preserve the same offsets in an
        # open combat area so this legacy combat fixture tests combat.
        self.alpha = self.player("alpha", 100, 0, "ak47")
        self.bravo = self.player("bravo", 100, 8, "ak47")
        self.game.players = {self.alpha["id"]: self.alpha, self.bravo["id"]: self.bravo}

    @staticmethod
    def player(pid, x, z, weapon):
        return {"id": pid, "name": pid, "x": x, "z": z, "weapon": weapon, "angle": 0,
                "hp": 100, "ammo": WEAPONS[weapon]["mag"], "reserve": WEAPONS[weapon]["reserve"],
                "reload_until": 0, "last_shot": -99, "protected_until": 0, "kills": 0,
                "pvp": 0, "score": 0, "awaiting_input": False}

    def test_named_alliance_blocks_hitscan_and_emits_owner_target_damage(self):
        alliance = self.game.create_alliance(self.alpha, "Night Watch")
        self.assertEqual(alliance["name"], "Night Watch")
        self.assertTrue(self.game.join_alliance(self.bravo, alliance["code"]))
        original = combat_module.wall_distance
        combat_module.wall_distance = lambda *_args: 1
        try:
            shoot(self.game, self.alpha, 1)
            self.assertEqual(self.bravo["hp"], 100)
            self.assertFalse(any(event.get("type") == "damage" for event in self.game.events))
            self.assertTrue(self.game.set_alliance_friendly_fire(self.alpha, True))
            self.alpha["last_shot"] = -99
            shoot(self.game, self.alpha, 2)
            damage = next(event for event in self.game.events if event.get("type") == "damage")
            self.assertEqual((damage["owner"], damage["target"]), ("alpha", "bravo"))
        finally:
            combat_module.wall_distance = original

    def test_rocket_does_not_impact_protected_ally_and_enemy_fire_has_no_owner(self):
        self.alpha["weapon"] = "rocket"; self.alpha["ammo"] = WEAPONS["rocket"]["mag"]
        self.bravo["z"] = 1
        alliance = self.game.create_alliance(self.alpha, "Rangers")
        self.game.join_alliance(self.bravo, alliance["code"])
        original = combat_module.wall_distance
        combat_module.wall_distance = lambda *_args: 1
        try:
            shoot(self.game, self.alpha, 1)
            rocket = self.game.projectiles[0]
            update_projectiles(self.game, .05, 1.05)
            self.assertGreater(rocket["remaining"], 0)
            self.assertEqual(self.bravo["hp"], 100)
            immolator = {"id": "im", "name": "Immolator", "x": 2, "z": 0, "hp": 1, "zombie": True, "enemy_type": "immolator"}
            self.game.zombies["im"] = immolator
            hurt(self.game, immolator, 5, self.alpha, 2)
            blast = next(event for event in self.game.events if event.get("kind") == "enemy_fire")
            self.assertEqual(blast["owner"], "")
        finally:
            combat_module.wall_distance = original

    def test_damage_events_are_private_to_owner_and_target(self):
        class Socket:
            async def send_json(self, _payload):
                pass

        game = Game(lambda _player: None)
        owner = game.add_player({"name": "Owner", "skin": "soldier"}, Socket())
        target = game.add_player({"name": "Target", "skin": "soldier"}, Socket())
        observer = game.add_player({"name": "Observer", "skin": "soldier"}, Socket())
        for player in (owner, target, observer):
            player.update(x=100, z=0, protected_until=0, awaiting_input=False)
        game.events = [{"type": "damage", "owner": owner["id"], "target": target["id"], "amount": 10, "x": 100, "z": 0, "zombie": True}]
        self.assertEqual(len(game.snapshot(owner, 10)["events"]), 1)
        self.assertEqual(len(game.snapshot(target, 10)["events"]), 1)
        self.assertEqual(game.snapshot(observer, 10)["events"], [])


if __name__ == "__main__":
    unittest.main()

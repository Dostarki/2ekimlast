"""Module: network.ClientChannel + engine tick isolation kısa odaklı testler."""

import asyncio
import json
import sys
import time

sys.path.insert(0, "/app/backend")

from engine import Game
from network import ClientChannel
from websockets.exceptions import ConnectionClosedOK
from websockets.frames import Close


class FakeSlowWebSocket:
    def __init__(self, delay=0.0, fail=False):
        self.delay = delay
        self.fail = fail
        self.sent = []
        self.closed = False

    async def send_text(self, payload):
        if self.fail:
            raise self.fail if isinstance(self.fail, Exception) else OSError("simulated send failure")
        if self.delay:
            await asyncio.sleep(self.delay)
        self.sent.append(json.loads(payload))

    async def close(self):
        self.closed = True


async def _noop_save_score(_player):
    return None


def test_client_channel_coalesces_latest_state_and_caps_events_in_order():
    async def _flow():
        ws = FakeSlowWebSocket(delay=0.0)
        channel = ClientChannel(ws)
        channel.start()

        # First state is expected to be coalesced away by the second offer.
        channel.offer({"type": "state", "seq": 1, "events": [{"n": 1}, {"n": 2}]})
        channel.offer({"type": "state", "seq": 2, "events": [{"n": 3}]})
        await asyncio.sleep(0.06)
        assert ws.sent, "No state was sent"
        first = ws.sent[0]
        assert first["seq"] == 2
        assert [e["n"] for e in first["events"]] == [1, 2, 3]
        assert channel.coalesced >= 1

        # Overflow beyond 256 must keep newest entries in original order.
        for i in range(300):
            channel.offer({"type": "state", "seq": 1000 + i, "events": [{"n": i}]})
        await asyncio.sleep(0.12)
        latest = ws.sent[-1]
        nums = [e["n"] for e in latest["events"]]
        assert len(nums) <= 256
        assert nums == list(range(44, 300))

        await channel.stop()
        assert channel.closed is True
        assert channel.pending is None
        assert list(channel.events) == []
        assert list(channel.controls) == []

    asyncio.run(_flow())


def test_client_channel_prioritizes_control_messages_and_closes_on_timeout_or_error():
    async def _priority_and_timeout():
        ws = FakeSlowWebSocket(delay=0.0)
        channel = ClientChannel(ws)
        channel.start()
        channel.offer({"type": "state", "seq": 10, "events": []})
        channel.control({"type": "pong", "time": 123})
        await asyncio.sleep(0.08)
        assert len(ws.sent) >= 2
        assert ws.sent[0]["type"] == "pong"
        assert ws.sent[1]["type"] == "state"
        await channel.stop()

        # Timeout path (send takes >0.5s) should close channel gracefully.
        slow_ws = FakeSlowWebSocket(delay=0.7)
        slow_channel = ClientChannel(slow_ws)
        slow_channel.start()
        slow_channel.offer({"type": "state", "seq": 99, "events": []})
        await asyncio.sleep(0.75)
        assert slow_channel.closed is True
        assert slow_ws.closed is True
        assert slow_channel.task.done() and slow_channel.task.exception() is None

        # Explicit send exception path.
        bad_ws = FakeSlowWebSocket(fail=True)
        bad_channel = ClientChannel(bad_ws)
        bad_channel.start()
        bad_channel.offer({"type": "state", "seq": 1, "events": []})
        await asyncio.sleep(0.08)
        assert bad_channel.closed is True
        assert bad_ws.closed is True
        assert bad_channel.task.done() and bad_channel.task.exception() is None

        # Uvicorn can surface the underlying websockets normal-close exception.
        closed_ws = FakeSlowWebSocket(fail=ConnectionClosedOK(Close(1000, ''), Close(1000, ''), True))
        closed_channel = ClientChannel(closed_ws)
        closed_channel.start()
        closed_channel.offer({'type': 'state', 'seq': 2, 'events': []})
        await asyncio.sleep(.08)
        await closed_channel.stop()
        assert closed_channel.task.done() and closed_channel.task.exception() is None

    asyncio.run(_priority_and_timeout())


def test_game_run_20hz_not_blocked_by_slow_socket_writer_and_respawn_contract():
    async def _flow():
        game = Game(_noop_save_score)
        slow = FakeSlowWebSocket(delay=0.35)
        fast = FakeSlowWebSocket(delay=0.0)

        p1 = game.add_player({"name": "TEST_SLOW", "weapon": "ak47", "skin": "soldier"}, slow)
        p2 = game.add_player({"name": "TEST_FAST", "weapon": "ak117", "skin": "fbi"}, fast)
        p1["channel"].start()
        p2["channel"].start()

        task = asyncio.create_task(game.run())
        start = time.monotonic()
        await asyncio.sleep(0.65)
        elapsed = time.monotonic() - start
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # 20Hz target; allow generous scheduler jitter.
        assert elapsed >= 0.6
        assert game.tick_seq >= 8

        # Unit-level death/respawn validation when hp <= 0.
        old_id = p2["id"]
        p2["hp"] = 0
        p2['died_at'] = time.monotonic()
        assert game.respawn(p2) is False
        p2['died_at'] -= 10.1
        assert game.respawn(p2) is True
        assert p2["id"] != old_id
        assert p2["hp"] == 100
        assert p2["skin"] == "fbi"
        assert p2["weapon"] == "glock18"

        await asyncio.gather(*(player["channel"].stop() for player in list(game.players.values())))

    asyncio.run(_flow())

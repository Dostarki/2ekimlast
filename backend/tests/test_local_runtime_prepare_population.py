"""Worker prepare_step population completion for requested zombie/bot counts."""

import json
import time
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from game_settings import GameSettings
from local_runtime import LocalRuntime


def _bootstrap(*, zombie_count: int, bot_count: int, density: str = 'normal'):
    settings = GameSettings(zombie_density=density, zombie_count=zombie_count, bot_count=bot_count).model_dump()
    return {
        'name': 'TEST_RUNTIME',
        'skin': 'soldier',
        'weapon': 'glock18',
        'account_id': 'test-runtime-account',
        'progress': {},
        'settings': settings,
    }


# Module: cooperative prepare loop must fully satisfy requested world population.
def test_prepare_step_completes_1500_zombies_and_64_bots_before_ready():
    runtime = LocalRuntime(_bootstrap(zombie_count=1500, bot_count=64, density='normal'))
    started = time.monotonic()
    ready = None
    for _ in range(3000):
        ready = json.loads(runtime.prepare_step())
        if ready['ready']:
            break
    assert ready is not None and ready['ready'] is True
    assert ready['zombies'] == 1500
    assert ready['bots'] == 64
    assert time.monotonic() - started < 30


def test_prepare_step_zero_population_ready_state():
    runtime = LocalRuntime(_bootstrap(zombie_count=0, bot_count=0, density='off'))
    ready = json.loads(runtime.prepare_step())
    assert ready['ready'] is True
    assert ready['zombies'] == 0
    assert ready['target'] == 0
    assert ready['bots'] == 0


def test_prepare_step_handles_4500_without_hidden_cap():
    runtime = LocalRuntime(_bootstrap(zombie_count=4500, bot_count=64, density='high'))
    ready = None
    for _ in range(12000):
        ready = json.loads(runtime.prepare_step())
        if ready['ready']:
            break
    assert ready is not None and ready['ready'] is True
    assert ready['zombies'] == 4500
    assert ready['target'] == 4500
    assert ready['bots'] == 64

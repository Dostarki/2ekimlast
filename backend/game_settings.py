from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from boss_catalog import create_boss


class BossSettings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    hansel: bool = True
    symbiote: bool = True
    xenomorph: bool = True
    ash_titan: bool = True


class GameSettings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    bosses: BossSettings = Field(default_factory=BossSettings)
    time_of_day: Literal['day', 'night'] = 'day'
    zombie_density: Literal['off', 'low', 'normal', 'high'] = 'normal'
    zombie_count: int = Field(default=250, ge=0, strict=True)
    bot_count: int = Field(default=0, ge=0, le=200, strict=True)


DENSITY = {'off': 0, 'low': .5, 'normal': 1, 'high': 2}
DENSITY_COUNTS = {'off': 0, 'low': 120, 'normal': 250, 'high': 450}


def zombie_target(settings):
    return 0 if settings['zombie_density'] == 'off' else settings.get('zombie_count', DENSITY_COUNTS[settings['zombie_density']])


def apply_settings(game, settings):
    old = game.settings
    game.settings = settings
    for kind, enabled in settings['bosses'].items():
        key = f'boss-{kind}'
        if not enabled:
            game.bosses.pop(key, None)
            game.boss_projectiles[:] = [e for e in game.boss_projectiles if e['owner'] != key]
            game.boss_zones[:] = [e for e in game.boss_zones if e['owner'] != key]
            game.events[:] = [e for e in game.events if e.get('owner') != key]
            for p in game.players.values():
                p['statuses'] = {k: v for k, v in p['statuses'].items() if v.get('source') != key}
        elif key not in game.bosses:
            game.bosses[key] = create_boss(kind)
    target = zombie_target(settings)
    game.zombie_target = target
    game.zombie_factor = DENSITY[settings['zombie_density']] if target else 0
    if not target:
        game.zombies.clear(); game.swarms.clear()
        for p in game.players.values():
            p['statuses'].pop('poison', None)
            p['statuses'].pop('bleeding', None)
    else:
        # Reductions are immediate; additions are filled by the world loop across all regions.
        from population import trim_population
        trim_population(game, target)
        game.next_population_at = 0
    # Reductions are immediate; additions are staggered by the game loop.
    bots = [p for p in game.players.values() if p.get('bot')]
    from bots import remove_bot
    for p in bots[settings['bot_count']:]:
        remove_bot(game, p)
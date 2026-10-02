"""Companion persistence primitives, independent of combat and companion AI."""
RECOVERY_SECONDS = 120
RUNTIME_KEYS = ('hp', 'ammo', 'reserve', 'status', 'recovery_until_utc')


def runtime_snapshot(soldier):
    """Only these values remain meaningful across process restarts."""
    return {key: soldier[key] for key in RUNTIME_KEYS if key in soldier}
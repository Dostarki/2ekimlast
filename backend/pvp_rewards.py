import math
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple


PVP_POLICY_VERSION = "1.0.0"
PVP_DAILY_XP_CAP = 900
PVP_ROLLING_WINDOW_SECONDS = 1800  # 30 minutes


# In-memory anti-farm stores (also serialized to db if available)
# killer_account_id -> {victim_account_id: [timestamps]}
_PAIR_KILL_HISTORY: Dict[str, Dict[str, list]] = {}

# killer_account_id -> {utc_date_str: granted_xp_total}
_DAILY_XP_TRACKER: Dict[str, Dict[str, int]] = {}


def calculate_raw_pvp_xp(victim_level: int) -> int:
    """Calculate raw PvP XP based on victim level.
    Formula: floor(30 * (1 + 4 * (clamp(victim_level, 1, 50) - 1) / 49))
    """
    clamped_level = max(1, min(50, int(victim_level)))
    ratio = (clamped_level - 1) / 49.0
    return math.floor(30.0 * (1.0 + 4.0 * ratio))


def get_pair_multiplier(killer_id: str, victim_id: str, now: Optional[float] = None) -> Tuple[float, int]:
    """Calculate anti-farm multiplier for killer -> victim pair in rolling 30m window.
    Returns (multiplier, kill_count_in_window)
    1st kill: 1.0 (100%)
    2nd kill: 0.25 (25%)
    3rd+ kill: 0.0
    """
    if now is None:
        now = time.time()

    killer_hist = _PAIR_KILL_HISTORY.setdefault(killer_id, {})
    victim_times = killer_hist.setdefault(victim_id, [])

    # Filter out entries older than rolling window
    cutoff = now - PVP_ROLLING_WINDOW_SECONDS
    valid_times = [t for t in victim_times if t >= cutoff]
    killer_hist[victim_id] = valid_times

    kill_count = len(valid_times) + 1  # This kill will be the Nth
    valid_times.append(now)

    if kill_count == 1:
        return 1.0, kill_count
    elif kill_count == 2:
        return 0.25, kill_count
    else:
        return 0.0, kill_count


def get_daily_remaining_cap(killer_id: str, now_dt: Optional[datetime] = None) -> int:
    """Returns remaining PvP XP cap for today (UTC)."""
    if now_dt is None:
        now_dt = datetime.now(timezone.utc)
    date_key = now_dt.strftime("%Y-%m-%d")

    account_daily = _DAILY_XP_TRACKER.setdefault(killer_id, {})
    current_today = account_daily.get(date_key, 0)
    return max(0, PVP_DAILY_XP_CAP - current_today)


def record_daily_xp(killer_id: str, xp_amount: int, now_dt: Optional[datetime] = None) -> int:
    """Records granted PvP XP towards the daily cap."""
    if xp_amount <= 0:
        return 0
    if now_dt is None:
        now_dt = datetime.now(timezone.utc)
    date_key = now_dt.strftime("%Y-%m-%d")

    account_daily = _DAILY_XP_TRACKER.setdefault(killer_id, {})
    account_daily[date_key] = account_daily.get(date_key, 0) + xp_amount
    return account_daily[date_key]


def evaluate_pvp_kill(
    killer_player: Dict[str, Any],
    victim_player: Dict[str, Any],
    now: Optional[float] = None
) -> Dict[str, Any]:
    """Authoritative PvP kill XP evaluation adhering to plan Section 15.
    Returns evaluation dict with granted_xp, reason, multiplier, etc.
    """
    if now is None:
        now = time.time()
    now_dt = datetime.now(timezone.utc)

    killer_acc = killer_player.get('account_id') or killer_player.get('id') or ''
    victim_acc = victim_player.get('account_id') or victim_player.get('id') or ''
    victim_level = victim_player.get('level', 1)

    result = {
        'killer_account_id': killer_acc,
        'victim_account_id': victim_acc,
        'victim_level': victim_level,
        'policy_version': PVP_POLICY_VERSION,
        'raw_xp': calculate_raw_pvp_xp(victim_level),
        'pair_count': 0,
        'multiplier': 0.0,
        'granted_xp': 0,
        'reason': 'valid',
        'utc': now_dt.isoformat(),
    }

    # 1. Self kill / suicide check
    if killer_acc and victim_acc and killer_acc == victim_acc:
        result['reason'] = 'suicide'
        return result

    # 2. Alliance / friendly fire check
    killer_alliance = killer_player.get('alliance_id')
    victim_alliance = victim_player.get('alliance_id')
    if killer_alliance and victim_alliance and killer_alliance == victim_alliance:
        result['reason'] = 'same_alliance'
        return result

    # 3. Bot / synthetic target check
    if victim_player.get('is_bot') or victim_player.get('synthetic'):
        result['reason'] = 'bot_target'
        return result

    # 4. Spawn / recovery invulnerability check
    if victim_player.get('invulnerable') or victim_player.get('safe_zone'):
        result['reason'] = 'protected_target'
        return result

    # 5. Anti-farm pair multiplier
    multiplier, pair_count = get_pair_multiplier(killer_acc, victim_acc, now)
    result['multiplier'] = multiplier
    result['pair_count'] = pair_count

    if multiplier <= 0.0:
        result['reason'] = 'repeat_kill_limit'
        return result

    raw_xp = result['raw_xp']
    after_pair_xp = math.floor(raw_xp * multiplier)

    # 6. Daily cap check
    remaining_cap = get_daily_remaining_cap(killer_acc, now_dt)
    final_grant = min(remaining_cap, after_pair_xp)

    if final_grant <= 0:
        result['reason'] = 'daily_cap_reached'
        return result

    # Apply grant
    record_daily_xp(killer_acc, final_grant, now_dt)
    result['granted_xp'] = final_grant
    if final_grant < after_pair_xp:
        result['reason'] = 'daily_cap_clipped'
    elif multiplier < 1.0:
        result['reason'] = 'repeat_kill_reduced'

    return result

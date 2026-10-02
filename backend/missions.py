"""Durable, account-scoped 24-hour soldier missions."""
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

log = logging.getLogger(__name__)
MISSION_DURATION_HOURS = 24
MISSION_POLICY_VERSION = '1.0.0'
SOLDIER_MISSION_GOLD = {f'soldier_s{i}': v for i, v in enumerate((80, 160, 280, 440, 650), 1)}


async def get_account_missions(db, account_id: str) -> List[Dict[str, Any]]:
    if db is None or not hasattr(db, 'soldier_missions'):
        raise RuntimeError('mission_storage_unavailable')
    return await db.soldier_missions.find({'account_id': account_id.lower()}, {'_id': 0}).to_list(100)


def _recovery_deadline(soldier):
    runtime = soldier.get('runtime') or {}
    raw = runtime.get('recovery_until_utc', soldier.get('recovery_until_utc'))
    if raw in (None, '', 0, 0.0):
        return None
    if isinstance(raw, (int, float)):
        return datetime.fromtimestamp(float(raw), timezone.utc)
    parsed = datetime.fromisoformat(str(raw).replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


async def start_soldier_mission(db, account_id: str, soldier_instance_id: str,
                               request_id: Optional[str] = None, recall_active: bool = False) -> Dict[str, Any]:
    acc_id = account_id.lower()
    if db is None or not hasattr(db, 'soldier_missions'):
        raise RuntimeError('mission_storage_unavailable')
    from player_accounts import get_player_progress, save_player_progress
    from soldier import ensure_owned_soldiers

    rid = request_id or str(uuid.uuid4())
    prior = await db.soldier_missions.find_one({'account_id': acc_id, 'request_id': rid}, {'_id': 0})
    if prior:
        if prior.get('soldier_instance_id') != soldier_instance_id:
            return {'success': False, 'code': 'request_id_conflict'}
        # Repair the account-side pointer if a process stopped after inserting
        # the durable mission record.
        if prior.get('status') not in ('active', 'rewarded'):
            return {'success': True, 'mission': prior}
        prog = await get_player_progress(db, acc_id)
        soldier = next((s for s in ensure_owned_soldiers(prog) if s['instance_id'] == soldier_instance_id), None)
        if soldier and soldier.get('current_mission_id') != prior['mission_id']:
            soldier['current_mission_id'] = prior['mission_id']
            await save_player_progress(db, acc_id, prog)
        return {'success': True, 'mission': prior}

    prog = await get_player_progress(db, acc_id)
    soldier = next((s for s in ensure_owned_soldiers(prog) if s['instance_id'] == soldier_instance_id), None)
    if not soldier:
        return {'success': False, 'code': 'soldier_not_found'}
    try:
        recovery = _recovery_deadline(soldier)
    except (ValueError, TypeError, OverflowError):
        return {'success': False, 'code': 'recovery_state_invalid'}
    now = datetime.now(timezone.utc)
    if recovery and recovery > now:
        return {'success': False, 'code': 'soldier_recovering', 'recovery_until_utc': recovery.isoformat()}
    is_active = soldier_instance_id in (prog.get('active_soldier_ids') or [])
    if is_active and not recall_active:
        return {'success': False, 'code': 'soldier_in_combat'}
    if soldier.get('current_mission_id'):
        return {'success': False, 'code': 'soldier_on_mission'}
    active = await db.soldier_missions.find_one(
        {'account_id': acc_id, 'soldier_instance_id': soldier_instance_id, 'status': {'$in': ['active', 'rewarded']}},
        {'_id': 0})
    if active:
        return {'success': False, 'code': 'soldier_on_mission'}

    tier = soldier.get('tier_id')
    if tier not in SOLDIER_MISSION_GOLD:
        return {'success': False, 'code': 'soldier_tier_invalid'}
    mission_id = str(uuid.uuid4())
    end = now + timedelta(hours=MISSION_DURATION_HOURS)
    mission = {
        'mission_id': mission_id, 'account_id': acc_id,
        'soldier_instance_id': soldier_instance_id,
        'soldier_name': soldier.get('nickname') or soldier.get('name') or 'Soldier',
        'tier_at_start': tier, 'start_utc': now.isoformat(), 'end_utc': end.isoformat(),
        'duration_seconds': MISSION_DURATION_HOURS * 3600,
        'reward_gold': SOLDIER_MISSION_GOLD[tier], 'reward_policy_version': MISSION_POLICY_VERSION,
        'status': 'active', 'claim_transaction_id': None, 'request_id': rid,
    }
    try:
        await db.soldier_missions.insert_one(mission)
        mission.pop('_id', None)
    except Exception:
        # A concurrent retry with the same idempotency key returns its record.
        prior = await db.soldier_missions.find_one({'account_id': acc_id, 'request_id': rid}, {'_id': 0})
        if prior:
            return {'success': True, 'mission': prior}
        active = await db.soldier_missions.find_one(
            {'account_id': acc_id, 'soldier_instance_id': soldier_instance_id, 'status': 'active'}, {'_id': 0})
        if active:
            return {'success': False, 'code': 'soldier_on_mission'}
        raise
    soldier['current_mission_id'] = mission_id
    if is_active:
        prog['active_soldier_ids'] = [sid for sid in (prog.get('active_soldier_ids') or []) if sid != soldier_instance_id]
    await save_player_progress(db, acc_id, prog)
    return {'success': True, 'mission': mission}


async def claim_soldier_mission(db, account_id: str, mission_id: str,
                               request_id: Optional[str] = None) -> Dict[str, Any]:
    acc_id = account_id.lower()
    if db is None or not hasattr(db, 'soldier_missions'):
        raise RuntimeError('mission_storage_unavailable')
    mission = await db.soldier_missions.find_one({'mission_id': mission_id, 'account_id': acc_id}, {'_id': 0})
    if not mission:
        return {'success': False, 'code': 'mission_not_found'}
    from player_accounts import get_player_progress, save_player_progress

    # Parse errors fail closed: malformed persisted timestamps never pay out.
    try:
        end = datetime.fromisoformat(str(mission['end_utc']).replace('Z', '+00:00'))
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        end = end.astimezone(timezone.utc)
    except (KeyError, ValueError, TypeError):
        return {'success': False, 'code': 'mission_state_invalid'}
    now = datetime.now(timezone.utc)
    if now < end:
        return {'success': False, 'code': 'mission_not_ready',
                'remaining_seconds': max(0, int((end - now).total_seconds()))}
    if mission.get('status') not in ('active', 'rewarded', 'claimed'):
        return {'success': False, 'code': 'mission_state_invalid'}

    prog = await get_player_progress(db, acc_id)
    applied = prog.setdefault('applied_mission_claims', {})
    receipt = applied.get(mission_id)
    newly_applied = False
    if mission.get('status') == 'claimed' and not receipt:
        return {'success': True, 'mission': mission, 'reward_gold': int(mission.get('reward_gold', 0)),
                'already_claimed': True}
    if not receipt:
        reward = int(mission.get('reward_gold', 0))
        if reward < 0:
            return {'success': False, 'code': 'mission_state_invalid'}
        prog['gold'] = int(prog.get('gold', 0)) + reward
        soldier = next((s for s in prog.get('owned_soldiers') or []
                        if s.get('instance_id') == mission.get('soldier_instance_id')), None)
        if soldier and soldier.get('current_mission_id') == mission_id:
            soldier.pop('current_mission_id', None)
        applied[mission_id] = {'reward_gold': reward, 'request_id': request_id or mission_id}
        try:
            prog = await save_player_progress(db, acc_id, prog)
            newly_applied = True
        except RuntimeError as exc:
            if str(exc) == 'progress_revision_conflict':
                # Re-read once; another claim may already have committed.
                prog = await get_player_progress(db, acc_id)
                receipt = (prog.get('applied_mission_claims') or {}).get(mission_id)
                if not receipt:
                    raise
            else:
                raise
    reward = int(receipt.get('reward_gold', mission.get('reward_gold', 0))) if receipt else int(mission.get('reward_gold', 0))
    from economy import EconomyTransaction, record_economy_ledger
    await record_economy_ledger(db, EconomyTransaction(
        account_id=acc_id, gold_delta=reward, action='mission_claim', source_type='mission', source_id=mission_id,
        reason=f'24-hour soldier mission reward ({mission.get("soldier_name", "Soldier")})',
        request_id=f'mission:{mission_id}', account_revision=prog.get('revision', 1)))
    claimed_at = mission.get('claimed_at') or datetime.now(timezone.utc).isoformat()
    await db.soldier_missions.update_one(
        {'mission_id': mission_id, 'account_id': acc_id, 'status': {'$in': ['active', 'rewarded', 'claimed']}},
        {'$set': {'status': 'claimed', 'claim_transaction_id': mission_id,
                  'claim_request_id': request_id or mission_id, 'claimed_at': claimed_at}},
    )
    mission.update(status='claimed', claim_transaction_id=mission_id,
                   claim_request_id=request_id or mission_id, claimed_at=claimed_at)
    return {'success': True, 'reward_gold': reward, 'new_gold_balance': prog.get('gold'), 'mission': mission,
            'newly_applied': newly_applied}

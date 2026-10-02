import uuid
import logging
from datetime import datetime, timezone
from dataclasses import dataclass, replace
from typing import Dict, Any, Optional, Tuple

log = logging.getLogger(__name__)

# In-memory ledger buffer for fast access and fallback
_ECONOMY_LEDGER: list = []


@dataclass(frozen=True, kw_only=True)
class EconomyTransaction:
    account_id: str
    gold_delta: int
    action: str
    source_type: str
    source_id: Optional[str] = None
    reason: str = ''
    request_id: Optional[str] = None
    account_revision: int = 1


def compute_vip_gold_bonus(base_gold: int, is_vip: bool, remainder: int = 0) -> Tuple[int, int]:
    """Computes +10% PvE gold bonus using integer math and remainder preservation (Section 4).
    Returns (bonus_gold, new_remainder).
    """
    if not is_vip or base_gold <= 0:
        return 0, remainder

    # +10% bonus: multiply by 10, divide by 100
    total_numerator = remainder + (base_gold * 10)
    bonus_gold = total_numerator // 100
    new_remainder = total_numerator % 100
    return bonus_gold, new_remainder


async def record_economy_ledger(db, transaction: EconomyTransaction) -> Dict[str, Any]:
    """Records an immutable audit entry in economy_ledger adhering to Section 9."""
    tx_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()

    entry = {
        'transaction_id': tx_id,
        'account_id': transaction.account_id.lower(),
        'request_id': transaction.request_id or tx_id,
        'action': transaction.action,
        'gold_delta': int(transaction.gold_delta),
        'source_type': transaction.source_type,
        'source_id': transaction.source_id or '',
        'account_revision': transaction.account_revision,
        'reason': transaction.reason,
        'created_at': now_iso,
    }

    if db is not None:
        if not hasattr(db, 'economy_ledger'):
            raise RuntimeError('economy_ledger_unavailable')
        await db.economy_ledger.update_one(
            {'request_id': entry['request_id']}, {'$setOnInsert': entry}, upsert=True)
        persisted = await db.economy_ledger.find_one({'request_id': entry['request_id']}, {'_id': 0})
        if not persisted:
            raise RuntimeError('economy_ledger_persist_failed')
        entry = persisted
    if not any(row.get('request_id') == entry['request_id'] for row in _ECONOMY_LEDGER):
        _ECONOMY_LEDGER.append(entry)

    return entry


async def mutate_gold_atomic(db, transaction: EconomyTransaction) -> Tuple[bool, int, Dict[str, Any]]:
    """Mutates gold atomically with CAS revision increment and audit entry.
    Prevents negative balance. Returns (success, new_gold, ledger_entry).
    """
    acc_id = transaction.account_id.lower()
    gold_delta = transaction.gold_delta
    from player_accounts import get_player_progress, save_player_progress

    prog = await get_player_progress(db, acc_id)
    request_key = transaction.request_id or str(uuid.uuid4())
    transaction = replace(transaction, account_id=acc_id, request_id=request_key)
    applied = prog.setdefault('applied_economy_requests', {})
    previous = applied.get(request_key)
    if previous:
        ledger_entry = await record_economy_ledger(db, replace(transaction,
            gold_delta=int(previous['gold_delta']), account_revision=previous['account_revision']))
        return True, int(previous['gold_balance']), ledger_entry
    current_gold = int(prog.get('gold', 0))

    if gold_delta < 0 and current_gold + gold_delta < 0:
        return False, current_gold, {}

    new_gold = current_gold + gold_delta
    prog['gold'] = new_gold
    applied[request_key] = {'gold_delta': int(gold_delta), 'gold_balance': new_gold,
                            'account_revision': int(prog.get('revision', 1)) + 1}
    prog = await save_player_progress(db, acc_id, prog)

    ledger_entry = await record_economy_ledger(db, replace(transaction, account_revision=prog['revision']))

    return True, new_gold, ledger_entry

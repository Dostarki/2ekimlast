const API = `${process.env.REACT_APP_BACKEND_URL}/api/access`;
export const accessStorageKey = owner => `lastzhood-access:${owner}`;
export const validTransactionHash = value => /^0x[0-9a-fA-F]{64}$/.test(value || '');

export const readAccessPending = owner => {
  try { return JSON.parse(localStorage.getItem(accessStorageKey(owner)) || 'null'); }
  catch { return null; }
};
export const saveAccessPending = (owner, pending) => localStorage.setItem(accessStorageKey(owner), JSON.stringify(pending));
export const clearAccessPending = owner => localStorage.removeItem(accessStorageKey(owner));

export async function accessRequest(path = '', body, timeout = 12000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  const token = localStorage.getItem('dz_auth_token');
  try {
    const response = await fetch(`${API}${path}`, {
      method: body === undefined ? 'GET' : 'POST', credentials: 'include', signal: controller.signal,
      headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Payment request failed.');
    return data;
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('PAYMENT_VERIFICATION_UNAVAILABLE');
    throw error;
  } finally { clearTimeout(timer); }
}

export const accessErrorText = error => ({
  PAYMENT_QUOTE_UNAVAILABLE: 'The ETH price is unavailable. Please try again.',
  PAYMENT_VERIFICATION_UNAVAILABLE: 'Connection timed out. Check the existing payment; do not pay again.',
  PAYMENT_UNRESOLVED: 'Check your wallet activity and enter the transaction hash below. Do not send another payment.',
  PAYMENT_RECOVERY_CONFLICT: 'The saved payment needs review. Do not send another payment.',
  quote_expired: 'The payment needs review. Keep the transaction hash; do not pay again.',
  payment_failed: 'The transaction reverted. No access payment was transferred. You can try again.',
}[error.message] || error.shortMessage || error.message || 'Could not complete payment.');

export const definitelyNotSent = error => {
  for (let cause = error, depth = 0; cause && depth < 6; cause = cause.cause, depth += 1) {
    if (cause.code === 4001 || cause.code === 'ACTION_REJECTED' || cause.name === 'UserRejectedRequestError') return true;
  }
  return /insufficient ETH|quote expired|refresh this quote|switch to Robinhood|connect the signed-in wallet|invalid payment quote/i.test(error.message || '');
};
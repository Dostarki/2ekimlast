import { useEffect, useRef, useState } from 'react';
import { useAccount } from 'wagmi';
import { useNativePayment } from './useNativePayment';
import { useAuth } from '../lib/authContext';
import { robinhoodMainnet } from '../lib/walletConfig';
import { accessRequest, accessErrorText, readAccessPending, saveAccessPending,
  clearAccessPending, validTransactionHash, definitelyNotSent } from '../lib/accessCheckoutApi';

// Mounted once by AccessCheckoutProvider; header and lobby share the same lock.
export const useAccessCheckout = () => {
  const { user, status, checkAuth } = useAuth();
  const { address, chainId } = useAccount();
  const { sendNativePayment } = useNativePayment();
  const owner = status === 'authenticated' && address?.toLowerCase() === user?.address?.toLowerCase()
    && chainId === robinhoodMainnet.id ? user.address.toLowerCase() : '';
  const currentOwner = useRef(owner), inFlight = useRef(false), executeRef = useRef(null);
  currentOwner.current = owner;
  const [busy, setBusy] = useState('');
  const [view, setView] = useState({ owner: '', error: '', txHash: '', needsHash: false });
  const update = patch => { if (currentOwner.current === owner) setView(previous => ({ ...previous, owner, ...patch })); };

  const execute = async (allowSend = false, recoveredHash = '') => {
    if (!owner || inFlight.current) return;
    inFlight.current = true;
    setBusy('preparing');
    update({ error: '' });
    const run = async () => {
      let result = await accessRequest();
      const finishPaid = async () => {
        clearAccessPending(owner);
        update({ error: '', txHash: '', needsHash: false });
        if (currentOwner.current === owner) await checkAuth();
      };
      if (result.paid || result.fee_exempt) { await finishPaid(); return; }
      if (currentOwner.current !== owner) return;
      const pending = readAccessPending(owner);
      let order = result.order;
      if (pending && pending.order_id !== order?.order_id) throw new Error('PAYMENT_RECOVERY_CONFLICT');
      let hash = order?.tx_hash || pending?.tx_hash;
      if (!hash && pending?.wallet_pending) {
        update({ needsHash: true });
        if (!validTransactionHash(recoveredHash)) throw new Error('PAYMENT_UNRESOLVED');
        hash = recoveredHash;
      }
      if (!hash && !allowSend) return;
      if (!hash) {
        result = await accessRequest('/quote', {});
        if (result.paid || result.fee_exempt) { await finishPaid(); return; }
        order = result.order;
        hash = order?.tx_hash;
        if (!hash) {
          if (currentOwner.current !== owner) return;
          // Persist BEFORE the wallet request. An interrupted request is not
          // permission to send twice, even across refreshes or other tabs.
          saveAccessPending(owner, { order_id: order.order_id, wallet_pending: true });
          setBusy('approving');
          try {
            hash = await sendNativePayment(order.quote, address);
            if (!validTransactionHash(hash)) throw new Error('PAYMENT_UNRESOLVED');
          } catch (error) {
            if (definitelyNotSent(error)) clearAccessPending(owner);
            else update({ needsHash: true });
            throw error;
          }
        }
      }
      saveAccessPending(owner, { order_id: order.order_id, tx_hash: hash });
      update({ txHash: hash, needsHash: false });
      if (currentOwner.current !== owner) return;
      setBusy('confirming');
      const deadline = Date.now() + 45000;
      for (let attempt = 0; attempt < 20 && Date.now() < deadline; attempt += 1) {
        if (currentOwner.current !== owner) return;
        result = await accessRequest('/submit', { order_id: order.order_id, tx_hash: hash }, Math.min(12000, deadline - Date.now()));
        if (currentOwner.current !== owner) return;
        if (result.paid || result.fee_exempt) { await finishPaid(); return; }
        if (result.order?.payment_verified) throw new Error('Payment recorded; access is not available yet. Check payment again; do not pay again.');
        await new Promise(resolve => setTimeout(resolve, 1500));
      }
      throw new Error('Your transfer is pending. Check payment again; no new transfer is needed.');
    };
    try {
      // Web Locks also prevent two tabs from opening concurrent approvals.
      if (navigator.locks?.request) {
        await navigator.locks.request(`lastzhood-access:${owner}`, { ifAvailable: true }, async lock => {
          if (!lock) throw new Error('Payment is already open in another tab.');
          await run();
        });
      } else await run();
    } catch (error) {
      if (error.message === 'payment_failed') { clearAccessPending(owner); update({ txHash: '', needsHash: false }); }
      update({ error: accessErrorText(error) });
    } finally { inFlight.current = false; setBusy(''); }
  };
  executeRef.current = execute;
  useEffect(() => {
    setView({ owner, error: '', txHash: '', needsHash: false });
    // Recovery can verify an existing transfer; it must NEVER open the wallet.
    if (owner && !user?.game_access) executeRef.current(false);
  }, [owner, user?.game_access]);

  const visible = view.owner === owner ? view : { error: '', txHash: '', needsHash: false };
  return { busy, ...visible, unlock: hash => execute(true, hash) };
};
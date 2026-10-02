import React, { useState } from 'react';
import { ConnectButton } from '@rainbow-me/rainbowkit';
import { useDisconnect, useSwitchChain } from 'wagmi';
import { Wallet, LogOut, UserCheck, AlertCircle, KeyRound, LoaderCircle, Pencil } from 'lucide-react';
import { useAuth } from '../lib/authContext';
import { useAccessPayment } from '../lib/accessCheckoutContext';
import { validTransactionHash } from '../lib/accessCheckoutApi';
import { robinhoodMainnet } from '../lib/walletConfig';
import { Button } from './ui/button';
import './WalletGate.css';

export const WalletGate = ({ onProfileLoaded, testIdPrefix = 'wallet' }) => {
  const { switchChainAsync, isPending: switching } = useSwitchChain();
  const { disconnect } = useDisconnect();
  const { user, status, loginWithWallet, logout, updateProfile } = useAuth();
  const checkout = useAccessPayment();
  const [recoveryHash, setRecoveryHash] = useState('');
  const [signing, setSigning] = useState(false);
  const [showNickModal, setShowNickModal] = useState(false);
  const [newNick, setNewNick] = useState('');
  const [errorMsg, setErrorMsg] = useState('');

  const handleSignIn = async () => {
    setErrorMsg('');
    setSigning(true);
    try {
      const acct = await loginWithWallet();
      if (acct?.new_account) {
        setNewNick('');
        setShowNickModal(true);
      }
      if (onProfileLoaded && acct) onProfileLoaded(acct);
    } catch (err) {
      console.error('Sign-in error:', err);
      setErrorMsg(err.message || 'Signature failed or was rejected');
    } finally {
      setSigning(false);
    }
  };

  const handleSaveNickname = async (e) => {
    e.preventDefault();
    if (!newNick.trim()) return;
    setErrorMsg('');
    try {
      const updated = await updateProfile(newNick.trim());
      setShowNickModal(false);
      if (onProfileLoaded) onProfileLoaded(updated);
    } catch (err) {
      setErrorMsg(err.message || 'Could not update nickname');
    }
  };

  return (
    <div className="wallet-gate" data-testid={`${testIdPrefix}-gate`}>
      <ConnectButton.Custom>
        {({
          account,
          chain: currentChain,
          openAccountModal,
          openConnectModal,
          mounted,
        }) => {
          const ready = mounted;
          const connected = ready && account && currentChain;

          if (!connected) {
            return (
              <div className="wallet-connect-group">
                <button
                  type="button"
                  className="wallet-btn connect-btn"
                  onClick={() => {
                    setErrorMsg('');
                    openConnectModal();
                  }}
                  disabled={!ready || !openConnectModal}
                  data-testid={`${testIdPrefix}-connect-btn`}
                >
                  <Wallet size={15} />
                  <span data-testid={`${testIdPrefix}-connect-label`}>CONNECT WALLET</span>
                </button>
              </div>
            );
          }

          if (currentChain.unsupported || currentChain.id !== robinhoodMainnet.id) {
            return (
              <button
                type="button"
                className="wallet-btn wrong-net-btn"
                onClick={async () => {
                  setErrorMsg('');
                  try { await switchChainAsync({ chainId: robinhoodMainnet.id }); }
                  catch (error) { setErrorMsg(error.shortMessage || 'Network switch was cancelled or failed. Try again.'); }
                }}
                disabled={switching}
                title="Switch to Robinhood Chain Mainnet (4663)"
                data-testid={`${testIdPrefix}-chain-btn`}
              >
                <AlertCircle size={15} />
                <span data-testid={`${testIdPrefix}-chain-label`}>{switching ? 'SWITCHING...' : 'SWITCH NETWORK'}</span>
              </button>
            );
          }

          // Wallet is connected, check SIWE state
          if (status !== 'authenticated' || !user || !user.game_access) {
            return (
              <div className="wallet-siwe-wrapper">
                <button
                  type="button"
                  className="wallet-btn siwe-btn"
                  onClick={() => status === 'authenticated' && user ? checkout.unlock(recoveryHash.trim()) : handleSignIn()}
                  disabled={signing || !!checkout.busy || status === 'loading' || (checkout.needsHash && !validTransactionHash(recoveryHash.trim()))}
                  data-testid={`${testIdPrefix}-siwe-btn`}
                >
                  {signing || checkout.busy ? <LoaderCircle size={15} className="spin" /> : <KeyRound size={15} />}
                  <span data-testid={`${testIdPrefix}-siwe-label`}>{signing ? 'SIGNING...' : checkout.busy === 'approving' ? 'APPROVE IN WALLET…' : checkout.busy === 'confirming' ? 'CONFIRMING…' : checkout.busy ? 'CHECKING…' : user && status === 'authenticated' ? (checkout.txHash || checkout.needsHash ? 'CHECK PAYMENT' : 'UNLOCK PLAY · $1') : 'SIGN TO PLAY'}</span>
                </button>
                <button
                  type="button"
                  className="wallet-btn-mini"
                  onClick={openAccountModal}
                  title={account.address}
                  data-testid={`${testIdPrefix}-account-button`}
                >
                  {account.displayName}
                </button>
              </div>
            );
          }

          // Fully authenticated
          return (
            <div className="wallet-badge" data-testid={`${testIdPrefix}-user-badge`}>
              <button type="button" className="wallet-badge-info" onClick={openAccountModal} data-testid={`${testIdPrefix}-profile-button`}>
                <span className="wallet-badge-status"><i className="status-dot" /></span>
                <span className="wallet-badge-nick" data-testid={`${testIdPrefix}-nickname`}>{user.nickname || account.displayName}</span>
                <span className="wallet-badge-addr" data-testid={`${testIdPrefix}-address`}>{account.address.slice(0, 6)}...{account.address.slice(-4)}</span>
              </button>
              <button
                type="button"
                className="wallet-logout-btn"
                onClick={() => { setErrorMsg(''); setNewNick(user.nickname && !user.nickname.startsWith('Survivor_') ? user.nickname : ''); setShowNickModal(true); }}
                title="Change call sign"
                data-testid={`${testIdPrefix}-edit-nick-btn`}
              >
                <Pencil size={13} />
              </button>
              <button
                type="button"
                className="wallet-logout-btn"
                onClick={async () => { await logout(); disconnect(); }}
                title="Disconnect & Sign Out"
                data-testid={`${testIdPrefix}-logout-btn`}
              >
                <LogOut size={13} />
              </button>
            </div>
          );
        }}
      </ConnectButton.Custom>

      {user && !user.game_access && <>
        {checkout.needsHash && <input className="wallet-recovery-input" aria-label="Payment transaction hash" placeholder="Transaction hash (0x…)" value={recoveryHash} onChange={event => setRecoveryHash(event.target.value)} data-testid={`${testIdPrefix}-recovery-hash`} />}
        {checkout.txHash && <a className="wallet-payment-link" href={`${robinhoodMainnet.blockExplorers.default.url}/tx/${checkout.txHash}`} target="_blank" rel="noopener noreferrer" data-testid={`${testIdPrefix}-payment-transaction`}>View transaction ↗</a>}
        {checkout.error && <p className="wallet-error-msg" role="alert" data-testid={`${testIdPrefix}-payment-error`}>{checkout.error}</p>}
      </>}

      {errorMsg && (
        <div className="wallet-error-msg" role="alert" data-testid={`${testIdPrefix}-error`}>
          <AlertCircle size={12} /> {errorMsg}
        </div>
      )}

      {showNickModal && (
        <div className="wallet-nick-backdrop">
          <div className="wallet-nick-modal" role="dialog" aria-label="Register call sign" data-testid={`${testIdPrefix}-nickname-modal`}>
            <h3><UserCheck size={18} /> {user && user.nickname && !user.nickname.startsWith('Survivor_') ? 'CHANGE CALL SIGN' : 'REGISTER CALL SIGN'}</h3>
            <p>Welcome, survivor! Choose a call sign for this Robinhood wallet — you can change it anytime from your profile.</p>
            <form onSubmit={handleSaveNickname}>
              <input
                type="text"
                data-testid={`${testIdPrefix}-nickname-input`}
                value={newNick}
                onChange={(e) => setNewNick(e.target.value)}
                minLength={2}
                maxLength={18}
                placeholder="Enter call sign"
                autoFocus
                required
              />
              {errorMsg && <p className="wallet-error-msg" role="alert" data-testid={`${testIdPrefix}-nickname-error`}><AlertCircle size={12} /> {errorMsg}</p>}
              <div className="wallet-modal-actions">
                <Button type="button" variant="outline" onClick={() => { setErrorMsg(''); setShowNickModal(false); }} data-testid={`${testIdPrefix}-nickname-skip`}>
                  {user && user.nickname && !user.nickname.startsWith('Survivor_') ? 'Cancel' : 'Skip for Now'}
                </Button>
                <Button type="submit" className="save-btn" data-testid={`${testIdPrefix}-nickname-save`}>
                  Confirm Call Sign
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

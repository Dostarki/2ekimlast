import { useState } from 'react';
import { Check, LockKeyhole, Pencil, ArrowRight } from 'lucide-react';
import { Button } from './ui/button';

export const WalletForm = ({ draft, update, unlocked }) => {
  const [error, setError] = useState('');
  const bind = (event) => {
    event.preventDefault();
    const value = draft.wallet.trim();
    if (!/^0x[a-fA-F0-9]{40}$/.test(value) || /^0x0{40}$/.test(value)) { setError('Enter a valid EVM address: 0x + 40 hex characters (not the zero address).'); return; }
    update({ wallet: value, bound: true }); setError('');
  };
  return <section className={`wallet-section ${unlocked ? '' : 'section-locked'}`} data-testid="wallet-section"><div className="console-section-heading"><h2 data-testid="wallet-heading"><span>03</span> WALLET</h2>{!unlocked ? <LockKeyhole size={13} /> : draft.bound ? <span className="bound-label" data-testid="wallet-bound-status"><Check size={13} /> BOUND</span> : null}</div><form onSubmit={bind} className="wallet-form" noValidate><label htmlFor="wallet-address" className="sr-only">EVM wallet address</label><input id="wallet-address" value={draft.wallet} onChange={event => { update({ wallet: event.target.value, bound: false }); setError(''); }} placeholder="0x… EVM wallet address" spellCheck="false" autoComplete="off" disabled={!unlocked || draft.bound || !!draft.result} aria-invalid={!!error} data-testid="wallet-address-input" />{draft.bound ? <Button key="edit-wallet" type="button" variant="ghost" disabled={!!draft.result} onClick={event => { event.preventDefault(); update({ bound: false, consent: false }); }} title="Edit wallet address" aria-label="Edit wallet address" data-testid="edit-wallet-button"><Pencil size={15} /></Button> : <Button key="bind-wallet" type="submit" variant="outline" disabled={!unlocked} data-testid="bind-wallet-button">BIND <ArrowRight size={13} /></Button>}</form>{error && <p className="form-error" role="alert" data-testid="wallet-error">{error}</p>}<p className="wallet-note" data-testid="wallet-privacy-note">{unlocked ? 'Address only. No connection, signature or private key.' : 'Complete all four tasks to unlock.'}</p></section>;
};
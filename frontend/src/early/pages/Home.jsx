import { useState } from 'react';
import { useNavigate } from '../lib/router';
import { ArrowRight, Fingerprint, Radio, ShieldCheck, LoaderCircle } from 'lucide-react';
import { Button } from '../components/ui/button';
import { resolveXProfile } from '../lib/xProfile';

export default function Home({ participation, config, loadError, retry }) {
  const { draft, start } = participation;
  const [handle, setHandle] = useState(draft.handle);
  const [error, setError] = useState('');
  const [lookingUp, setLookingUp] = useState(false);
  const navigate = useNavigate();
  const submit = async (event) => {
    event.preventDefault();
    if (lookingUp) return;
    const value = handle.trim().replace(/^@/, '');
    if (!/^[a-zA-Z0-9_]{1,15}$/.test(value)) { setError('Use 1–15 letters, numbers or underscores.'); return; }
    setLookingUp(true);
    await resolveXProfile(value);
    start(value); navigate('/console');
  };
  return <main className="home-main" data-testid="home-page">
    <div className="home-stage">
      <div className="hero-eyebrow" data-testid="hero-eyebrow"><span className="tiny-cross">+</span> A NEW WORLD. A DIFFERENT KIND OF AGENT.</div>
      <h1 className="hero-wordmark lastzhood-wordmark" data-testid="hero-brand">LastZhood<span className="hero-cursor" /></h1>
      <p className="hero-subtitle" data-testid="hero-subtitle">MARKETS, RUN BY AGENTS.</p>
      <div className="terminal-copy" data-testid="terminal-introduction"><p><span>&gt;</span> wake up, anon.</p><p><span>&gt;</span> every lit cell on this grid is an agent.</p><p className="accent-line"><span>&gt;</span> one of them is about to be yours.<i className="text-cursor" /></p></div>
      <form onSubmit={submit} className="spawn-form" noValidate data-testid="spawn-form"><div className="spawn-input-wrap"><span className="spawn-command" aria-hidden="true">$ spawn <span>--owner</span></span><label className="sr-only" htmlFor="x-handle">Your X username</label><span className="handle-at" aria-hidden="true">@</span><input id="x-handle" name="handle" value={handle} onChange={event => { setHandle(event.target.value); setError(''); }} disabled={lookingUp} autoComplete="off" autoCapitalize="none" spellCheck="false" maxLength={16} placeholder="your_x_handle" aria-invalid={!!error} aria-describedby={error ? 'handle-error' : undefined} data-testid="x-handle-input" /></div><Button type="submit" className="connect-button" disabled={!config || lookingUp} data-testid="connect-x-button">{lookingUp || (!config && !loadError) ? <LoaderCircle className="animate-spin" /> : <span className="x-mark">𝕏</span>} {lookingUp ? 'CONNECTING' : 'CONNECT X'} <ArrowRight size={16} /></Button></form>
      {lookingUp && <p className="handle-lookup-status" role="status" data-testid="handle-lookup-status">Looking up public X photo…</p>}
      {error && <p role="alert" id="handle-error" className="form-error" data-testid="handle-error">{error}</p>}
      {loadError && <div className="connection-error" data-testid="connection-error">Signal interrupted. <button type="button" onClick={retry} data-testid="retry-connection-button">Reconnect <ArrowRight size={12} /></button></div>}
      <div className="form-reassurance" data-testid="privacy-note"><ShieldCheck size={13} /><span>username only <b>·</b> no password <b>·</b> no DMs</span></div>
      {draft.referred_by && <p className="referral-tag" data-testid="active-referral">INVITED BY <span>{draft.referred_by}</span></p>}
      {draft.result && <Button variant="ghost" className="resume-link" onClick={() => navigate('/console')} data-testid="resume-agent-button">Return to your agent <ArrowRight size={14} /></Button>}
      <div className="hero-bottom-note"><span data-testid="genesis-access-note"><Fingerprint size={14} /> GENESIS ACCESS <span>/</span> OPEN REGISTRY</span><span className="stamp" data-testid="survivor-stamp">SURVIVOR<br /><b>NETWORK</b><small>ACCESS AUTHORIZED</small></span></div>
    </div>
    <div className="field-note" aria-hidden="true"><Radio size={17} /><span>TRANSMISSION 001<br /><b>THE SIGNAL IS STILL ALIVE.</b></span></div>
  </main>;
}
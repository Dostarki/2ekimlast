import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, ShieldCheck, LockKeyhole, LogOut, Radio, LoaderCircle } from 'lucide-react';
import { adminApi } from '../lib/adminApi';
import { AdminWorldSettings } from './AdminWorldSettings';
import { AdminBots } from './AdminBots';
import { AdminWallets } from './AdminWallets';
import './AdminPage.css';

export default function AdminPage() {
  const [auth, setAuth] = useState(null), [password, setPassword] = useState('');
  const [settings, setSettings] = useState(null), [status, setStatus] = useState(null);
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [saved, setSaved] = useState('');
  const failure = useCallback(e => { setError(e.message || 'The server could not be reached.'); if (e.status === 401) setAuth(false); }, []);
  useEffect(() => { document.title = 'LastZHood — Admin'; adminApi('/me').then(() => setAuth(true)).catch(e => { setAuth(false); if (e.status !== 401) setError(e.message); }); }, []);
  useEffect(() => {
    if (!auth) return;
    let active = true;
    adminApi('/settings').then(data => { if (active) setSettings(data); }).catch(e => { if (active) failure(e); });
    const refresh = () => adminApi('/status').then(data => { if (active) setStatus(data); }).catch(e => { if (active) failure(e); });
    refresh(); const timer = setInterval(refresh, 3000);
    return () => { active = false; clearInterval(timer); };
  }, [auth, failure]);
  const login = async e => {
    e.preventDefault(); setBusy(true); setError('');
    try { await adminApi('/login', { method: 'POST', body: JSON.stringify({ password }) }); setPassword(''); setAuth(true); }
    catch (e) { failure(e); } finally { setBusy(false); }
  };
  const logout = async () => {
    setBusy(true);
    try { await adminApi('/logout', { method: 'POST' }); setAuth(false); setSettings(null); setStatus(null); setSaved(''); setError(''); }
    catch (e) { failure(e); } finally { setBusy(false); }
  };
  const save = async values => {
    setBusy(true); setError(''); setSaved('');
    try { const result = await adminApi('/settings', { method: 'PUT', body: JSON.stringify(values) }); setSettings(result); setSaved('CHANGES LIVE'); setStatus(await adminApi('/status')); }
    catch (e) { failure(e); } finally { setBusy(false); }
  };
  return <main className="admin-page" data-testid="admin-page">
    <header className="admin-header"><Link to="/loadout" data-testid="admin-back-to-game"><ArrowLeft size={17} /> LastZHood</Link><span data-testid="admin-server-name"><Radio size={14} /> WESTFALL–01</span>{auth && <button onClick={logout} disabled={busy} data-testid="admin-logout-button"><LogOut size={16} /><span>LOG OUT</span></button>}</header>
    <div className="admin-content">
      <div className="admin-page-heading"><span className="admin-eyebrow" data-testid="admin-eyebrow"><ShieldCheck size={15} /> AUTHORIZED ACCESS</span><h1 data-testid="admin-title">SERVER CONTROL<span>.</span></h1></div>
      {error && <p className="admin-error" role="alert" data-testid="admin-error">{error}</p>}
      {auth === null && <p className="admin-loading" data-testid="admin-auth-loading"><LoaderCircle className="spin" size={18} /> CHECKING SESSION</p>}
      {auth === false && <form onSubmit={login} className="admin-login" data-testid="admin-login-form"><LockKeyhole size={32} strokeWidth={1.2} /><label htmlFor="admin-password" data-testid="admin-password-label">ADMIN PASSWORD</label><input id="admin-password" type="password" autoComplete="current-password" required maxLength={72} value={password} onChange={e => setPassword(e.target.value)} data-testid="admin-password-input" autoFocus /><button type="submit" disabled={busy} data-testid="admin-login-submit">{busy ? 'SIGNING IN…' : 'SIGN IN'} <ShieldCheck size={18} /></button></form>}
      {auth && !settings && <p className="admin-loading" data-testid="admin-settings-loading">LOADING SETTINGS…</p>}
      {auth && settings && <>
        <div className="admin-summary" data-testid="admin-summary">{[['humans', 'HUMAN PLAYERS', status?.humans ?? 0], ['bots', 'BOTS / WORLD', status?.bots ?? 0], ['zombies', 'ZOMBIES / WORLD', status?.zombies ?? 0], ['tick', 'SHARED SIM / ms', status?.tick_ms ?? 0]].map(([id, label, value]) => <div key={id}><span data-testid={`admin-metric-label-${id}`}>{label}</span><strong data-testid={`admin-metric-${id}`}>{value}</strong></div>)}</div>
        <div className="admin-save-status" role="status" data-testid="admin-save-status">{busy ? 'APPLYING…' : saved || 'LIVE CONNECTION'}</div>
        <AdminWallets onError={failure} />
        <AdminWorldSettings settings={settings} save={save} busy={busy} />
        <AdminBots settings={settings} status={status} save={save} busy={busy} />
      </>}
    </div>
    <footer className="admin-footer" data-testid="admin-footer">LastZHood / WESTFALL <span>SERVER ADMINISTRATION</span></footer>
  </main>;
}

import { useCallback, useEffect, useState } from 'react';
import { Link } from '../lib/router';
import { ArrowLeft, Loader2, LogOut, RotateCcw, ShieldCheck } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Toaster } from '../components/ui/sonner';
import { MapAtmosphere } from '../components/MapAtmosphere';
import { AdminLogin } from '../components/admin/AdminLogin';
import { CampaignForm } from '../components/admin/CampaignForm';
import { WalletExport } from '../components/admin/WalletExport';
import { adminApi, adminError, adminRequest, isAdminAuthError, setAdminProof } from '../lib/adminApi';

export default function Admin() {
  const [state, setState] = useState('checking');
  const [initial, setInitial] = useState(null);
  const [error, setError] = useState('');
  const [pending, setPending] = useState(false);
  const [dirty, setDirty] = useState(false);
  const load = useCallback(async () => {
    setState('checking'); setError('');
    try {
      const { data } = await adminRequest('get', '/settings');
      setInitial(data); setState('authenticated');
    } catch (failure) {
      if (isAdminAuthError(failure)) setState('login');
      else { setError(adminError(failure)); setState('error'); }
    }
  }, []);
  useEffect(() => { load(); }, [load]);
  const login = async password => {
    setPending(true); setError('');
    try {
      const { data } = await adminApi.post('/login', { password });
      setAdminProof(data.csrf_token); await load();
    }
    catch (failure) { setError(adminError(failure)); }
    finally { setPending(false); }
  };
  const canLeave = () => !dirty || window.confirm('Kaydedilmemiş değişiklikler var. Kaydetmeden çıkmak istiyor musunuz?');
  const logout = async () => {
    if (!canLeave()) return;
    setPending(true); setError('');
    try { await adminApi.post('/logout'); setAdminProof(''); setInitial(null); setDirty(false); setState('login'); }
    catch (failure) {
      if (isAdminAuthError(failure)) { setAdminProof(''); setInitial(null); setDirty(false); setState('login'); }
      else setError(adminError(failure));
    }
    finally { setPending(false); }
  };
  return <div className="board-shell admin-shell" lang="tr" data-testid="admin-page">
    <MapAtmosphere />
    <header className="admin-header">
      <Link to="/" className="site-logo" onClick={event => { if (!canLeave()) event.preventDefault(); }} data-testid="admin-brand-link">LastZhood<span className="logo-square" /></Link>
      <nav aria-label="Yönetici menüsü">
        <Link to="/" onClick={event => { if (!canLeave()) event.preventDefault(); }} data-testid="admin-back-to-site-link"><ArrowLeft size={14} /> Siteye dön</Link>
        {state === 'authenticated' && <Button type="button" variant="ghost" onClick={logout} disabled={pending} data-testid="admin-logout-button"><LogOut size={15} /> Çıkış</Button>}
      </nav>
    </header>
    <main className={`admin-main ${state === 'login' ? 'admin-login-main' : ''}`}>
      {state === 'checking' && <div className="admin-loading" role="status" data-testid="admin-loading"><Loader2 size={20} className="animate-spin" /> Oturum kontrol ediliyor…</div>}
      {state === 'error' && <div className="admin-loading"><p className="admin-error" role="alert" data-testid="admin-load-error">{error}</p><Button type="button" variant="outline" onClick={load} data-testid="admin-retry-button"><RotateCcw size={16} /> Tekrar dene</Button></div>}
      {state === 'login' && <AdminLogin onLogin={login} pending={pending} error={error} />}
      {state === 'authenticated' && <>
        <div className="admin-heading"><div><p className="admin-eyebrow">LASTZHOOD / YÖNETİM</p><h1 data-testid="admin-settings-heading">Kampanya ayarları<span>.</span></h1></div><span className="admin-auth-status" data-testid="admin-session-status"><ShieldCheck size={14} /> Yetkili oturum</span></div>
        {error && <p role="alert" className="admin-error" data-testid="admin-session-error">{error}</p>}
        <WalletExport onSessionExpired={() => { setState('login'); setError('Oturum sona erdi. Lütfen tekrar giriş yapın.'); }} />
        <CampaignForm initial={initial} onDirtyChange={setDirty} onSessionExpired={() => { setState('login'); setError('Oturum sona erdi. Lütfen tekrar giriş yapın.'); }} />
      </>}
    </main>
    <footer className="admin-footer" data-testid="admin-footer">LASTZHOOD <span>YÖNETİCİ PANELİ</span></footer>
    <Toaster position="bottom-right" theme="dark" />
  </div>;
}
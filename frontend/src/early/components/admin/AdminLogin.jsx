import { useState } from 'react';
import { ArrowRight, Eye, EyeOff, Loader2, LockKeyhole } from 'lucide-react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';

export const AdminLogin = ({ onLogin, pending, error }) => {
  const [password, setPassword] = useState('');
  const [visible, setVisible] = useState(false);
  return <section className="admin-login" data-testid="admin-login-panel">
    <LockKeyhole size={26} className="admin-lock" aria-hidden="true" />
    <p className="admin-eyebrow">YETKİLİ ERİŞİM</p>
    <h1 data-testid="admin-login-heading">Yönetici girişi<span>.</span></h1>
    <form onSubmit={event => { event.preventDefault(); onLogin(password); }} data-testid="admin-login-form">
      <label htmlFor="admin-password">Yönetici şifresi</label>
      <div className="admin-password-wrap">
        <Input id="admin-password" type={visible ? 'text' : 'password'} autoComplete="current-password" autoFocus required maxLength={72} value={password} onChange={event => setPassword(event.target.value)} disabled={pending} data-testid="admin-password-input" />
        <Button type="button" variant="ghost" size="icon" onClick={() => setVisible(!visible)} title={visible ? 'Şifreyi gizle' : 'Şifreyi göster'} aria-label={visible ? 'Şifreyi gizle' : 'Şifreyi göster'} aria-pressed={visible} data-testid="admin-password-visibility-button">{visible ? <EyeOff size={17} /> : <Eye size={17} />}</Button>
      </div>
      {error && <p className="admin-error" role="alert" data-testid="admin-login-error">{error}</p>}
      <Button type="submit" className="primary-action admin-login-submit" disabled={pending || !password} data-testid="admin-login-button">{pending ? <><Loader2 size={16} className="animate-spin" /> Giriş yapılıyor…</> : <>Giriş yap <ArrowRight size={16} /></>}</Button>
    </form>
    <span className="admin-access-note" data-testid="admin-access-note"><LockKeyhole size={12} /> LASTZHOOD / ADMIN</span>
  </section>;
};
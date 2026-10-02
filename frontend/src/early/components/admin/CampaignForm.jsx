import { useEffect, useState } from 'react';
import { Check, Circle, Loader2, RotateCcw, Save } from 'lucide-react';
import { Button } from '../ui/button';
import { CampaignFields } from './CampaignFields';
import { adminError, adminRequest, isAdminAuthError } from '../../lib/adminApi';
import { toast } from '../ui/sonner';

export const CampaignForm = ({ initial, onSessionExpired, onDirtyChange }) => {
  const [saved, setSaved] = useState(initial);
  const [values, setValues] = useState(initial.settings);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const [conflict, setConflict] = useState(false);
  const dirty = JSON.stringify(values) !== JSON.stringify(saved.settings);
  useEffect(() => {
    onDirtyChange(dirty);
    const protect = event => { if (dirty) { event.preventDefault(); event.returnValue = ''; } };
    window.addEventListener('beforeunload', protect);
    return () => { window.removeEventListener('beforeunload', protect); onDirtyChange(false); };
  }, [dirty, onDirtyChange]);
  const handleError = failure => {
    setError(adminError(failure));
    if (isAdminAuthError(failure)) onSessionExpired();
    setConflict(failure.response?.status === 409);
  };
  const save = async event => {
    event.preventDefault(); setPending(true); setError('');
    try {
      const { data } = await adminRequest('put', '/settings', { ...values, revision: saved.revision });
      setSaved(data); setValues(data.settings); setConflict(false);
      toast.success(<span data-testid="admin-save-success-toast">Ayarlar kaydedildi.</span>);
    } catch (failure) { handleError(failure); }
    finally { setPending(false); }
  };
  const reload = async () => {
    if (!window.confirm('Kaydedilmemiş değişiklikler silinecek. Güncel ayarlar yüklensin mi?')) return;
    setPending(true);
    try {
      const { data } = await adminRequest('get', '/settings');
      setSaved(data); setValues(data.settings); setError(''); setConflict(false);
    } catch (failure) { handleError(failure); }
    finally { setPending(false); }
  };
  return <form onSubmit={save} className="admin-campaign-form" data-testid="admin-settings-form">
    <CampaignFields values={values} disabled={pending} onChange={(name, value) => { setValues(current => ({ ...current, [name]: value })); if (!conflict) setError(''); }} />
    {error && <div className="admin-error" role="alert" data-testid="admin-settings-error">{error}{conflict && <Button variant="ghost" type="button" onClick={reload} disabled={pending} data-testid="admin-reload-settings-button"><RotateCcw size={14} /> Güncel ayarları yükle</Button>}</div>}
    <div className="admin-save-bar">
      <div className="admin-save-status" aria-live="polite">
        <span className={dirty ? 'is-dirty' : ''} data-testid="admin-save-status">{pending ? <><Loader2 size={14} className="animate-spin" /> Kaydediliyor…</> : dirty ? <><Circle size={11} /> Kaydedilmemiş değişiklikler</> : <><Check size={15} /> Tüm değişiklikler kaydedildi</>}</span>
        <time dateTime={saved.updated_at} data-testid="admin-last-saved">Son kayıt: {new Date(saved.updated_at).toLocaleString('tr-TR')}</time>
      </div>
      <Button type="submit" className="primary-action" disabled={pending || !dirty || conflict} data-testid="admin-save-button"><Save size={16} /> {pending ? 'Kaydediliyor…' : 'Kaydet'}</Button>
    </div>
  </form>;
};
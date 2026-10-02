import { useState } from 'react';
import { Download } from 'lucide-react';
import { Button } from '../ui/button';
import { adminError, adminRequest, isAdminAuthError } from '../../lib/adminApi';
import { downloadWalletText } from '../../../lib/downloadWalletText';

export const WalletExport = ({ onSessionExpired }) => {
  const [busy, setBusy] = useState(false), [message, setMessage] = useState(''), [error, setError] = useState('');
  const download = async () => {
    setBusy(true); setMessage(''); setError('');
    try {
      const { data } = await adminRequest('get', '/wallets.txt');
      const count = downloadWalletText(data, 'lastzhood-early-wallets.txt');
      setMessage(count ? `${count} benzersiz cüzdan TXT olarak indirildi.` : 'Henüz katılan cüzdan yok.');
    } catch (failure) {
      if (isAdminAuthError(failure)) onSessionExpired();
      else setError(adminError(failure));
    } finally { setBusy(false); }
  };
  return <section className="admin-setting-section" data-testid="early-admin-wallet-export">
    <div className="admin-section-heading"><h2 data-testid="early-admin-wallet-export-title">Katılımcı cüzdanları</h2></div>
    <p className="early-wallet-export-note" data-testid="early-admin-wallet-export-help">Early kayıtlarındaki benzersiz cüzdanlar. TXT dosyasında her satırda bir adres bulunur.</p>
    <Button type="button" variant="outline" disabled={busy} onClick={download} data-testid="early-admin-export-wallets-button"><Download size={16} />{busy ? 'Hazırlanıyor…' : 'Cüzdanları indir (.txt)'}</Button>
    {message && <p role="status" className="early-wallet-export-note" data-testid="early-admin-wallet-export-result">{message}</p>}
    {error && <p role="alert" className="admin-error" data-testid="early-admin-wallet-export-error">{error}</p>}
  </section>;
};

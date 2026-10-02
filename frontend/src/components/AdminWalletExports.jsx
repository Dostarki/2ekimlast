import { useState } from 'react';
import { Download } from 'lucide-react';
import { Button } from './ui/button';
import { adminApi } from '../lib/adminApi';
import { downloadWalletText } from '../lib/downloadWalletText';

export const AdminWalletExports = ({ onError }) => {
  const [busy, setBusy] = useState(''), [message, setMessage] = useState('');
  const download = async source => {
    setBusy(source); setMessage('');
    try {
      const text = await adminApi(`/wallets/${source}.txt`, { responseType: 'text' });
      const count = downloadWalletText(text, `lastzhood-${source}-wallets.txt`);
      setMessage(count ? `${count} benzersiz cüzdan TXT olarak indirildi.` : 'Henüz kayıtlı cüzdan yok.');
    } catch (error) { onError(error); } finally { setBusy(''); }
  };
  return <section className="admin-section admin-wallet-tools" data-testid="admin-wallet-exports">
    <div className="admin-section-heading"><h2 data-testid="admin-wallet-export-title">CÜZDAN LİSTELERİ</h2><span>TXT / HER SATIRDA BİR ADRES</span></div>
    <p className="admin-wallet-hint" data-testid="admin-wallet-export-help">Oyunda kayıtlı oyuncular ve Early katılımcıları ayrı indirilir. Adresler küçük harfe çevrilir; tekrarlar kaldırılır.</p>
    <div className="admin-wallet-actions">{[['game', 'Oyun cüzdanlarını indir'], ['early', 'Early cüzdanlarını indir']].map(([source, label]) => <Button key={source} type="button" variant="outline" disabled={!!busy} onClick={() => download(source)} data-testid={`admin-export-${source}-wallets`}><Download size={16} />{busy === source ? 'Hazırlanıyor…' : `${label} (.txt)`}</Button>)}</div>
    {message && <p role="status" className="admin-wallet-success" data-testid="admin-wallet-export-result">{message}</p>}
  </section>;
};

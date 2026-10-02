import { useRef, useState } from 'react';
import { Coins, Search, ShieldCheck } from 'lucide-react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { adminApi } from '../lib/adminApi';
import { AdminWalletExports } from './AdminWalletExports';

export const AdminWallets = ({ onError }) => {
  const [wallet, setWallet] = useState(''), [amount, setAmount] = useState('');
  const [account, setAccount] = useState(null), [busy, setBusy] = useState(''), [message, setMessage] = useState('');
  const pendingGrant = useRef(null);
  const lookup = async event => {
    event.preventDefault(); setBusy('lookup'); setMessage(''); setAccount(null);
    try { setAccount(await adminApi(`/wallets/${encodeURIComponent(wallet.trim())}`)); }
    catch (error) { onError(error); } finally { setBusy(''); }
  };
  const grantGold = async event => {
    event.preventDefault(); setBusy('gold'); setMessage('');
    const value = Number(amount), owner = account.wallet;
    if (!pendingGrant.current) pendingGrant.current = { wallet: owner, amount: value, request_id: crypto.randomUUID() };
    try {
      const result = await adminApi('/wallets/gold', { method: 'POST', body: JSON.stringify(pendingGrant.current) });
      pendingGrant.current = null; setAmount(''); setAccount(previous => ({ ...previous, gold: result.gold }));
      setMessage(`${result.amount.toLocaleString('tr-TR')} gold eklendi. Bakiye: ${result.gold.toLocaleString('tr-TR')} gold.`);
    } catch (error) {
      if ([400, 404, 422].includes(error.status)) pendingGrant.current = null;
      onError(error);
    } finally { setBusy(''); }
  };
  const setExemption = async () => {
    setBusy('exemption'); setMessage('');
    try {
      const result = await adminApi('/wallets/fee-exemption', { method: 'PUT', body: JSON.stringify({ wallet: account.wallet, enabled: !account.fee_exempt }) });
      setAccount(result); setMessage(result.fee_exempt ? 'Ücretsiz giriş izni tanımlandı. Cüzdan imzası gerekmeye devam eder.' : 'Ücretsiz giriş izni kaldırıldı. Önceden satın alınan giriş hakkı korunur.');
    } catch (error) { onError(error); } finally { setBusy(''); }
  };
  return <div className="admin-wallet-tools" lang="tr" data-testid="admin-wallet-tools">
    <AdminWalletExports onError={onError} />
    <section className="admin-section" data-testid="admin-wallet-management">
      <div className="admin-section-heading"><h2 data-testid="admin-wallet-management-title">OYUNCU CÜZDANI</h2><span>GOLD / ÜCRETSİZ GİRİŞ</span></div>
      <form onSubmit={lookup} className="admin-wallet-lookup" data-testid="admin-wallet-lookup-form">
        <label htmlFor="admin-player-wallet">Cüzdan adresi</label><div className="admin-wallet-input-row"><Input id="admin-player-wallet" value={wallet} onChange={event => { setWallet(event.target.value); setAccount(null); setMessage(''); pendingGrant.current = null; }} placeholder="0x…" required pattern="\s*0x[0-9a-fA-F]{40}\s*" autoComplete="off" spellCheck={false} disabled={!!busy} data-testid="admin-player-wallet-input" /><Button type="submit" variant="outline" disabled={!!busy || !wallet.trim()} data-testid="admin-wallet-lookup-button"><Search size={16} />{busy === 'lookup' ? 'Aranıyor…' : 'Cüzdanı getir'}</Button></div>
      </form>
      {account && <div className="admin-wallet-detail" data-testid="admin-wallet-detail">
        <p className="admin-wallet-address" data-testid="admin-selected-wallet">{account.wallet}</p>
        <p data-testid="admin-wallet-profile">{account.registered ? `Oyuncu: ${account.nickname}` : 'Henüz kayıtlı değil. Şimdiden ücretsiz giriş izni tanımlayabilirsiniz.'}</p>
        <p className="admin-wallet-balance" data-testid="admin-wallet-gold-balance">{account.gold === null ? 'Gold için önce oyuna cüzdanla giriş yapılmalı.' : `${account.gold.toLocaleString('tr-TR')} GOLD`}</p>
        <form onSubmit={grantGold} className="admin-wallet-gold-form" data-testid="admin-wallet-gold-form"><label htmlFor="admin-gold-amount">Eklenecek gold miktarı</label><div className="admin-wallet-input-row"><Input id="admin-gold-amount" type="number" min="1" max="1000000000" step="1" required value={amount} onChange={event => { setAmount(event.target.value); pendingGrant.current = null; }} disabled={!!busy || !account.registered} data-testid="admin-gold-amount-input" /><Button type="submit" disabled={!!busy || !account.registered || !Number.isInteger(Number(amount)) || Number(amount) <= 0 || Number(amount) > 1000000000} data-testid="admin-add-gold-button"><Coins size={16} />{busy === 'gold' ? 'Ekleniyor…' : 'Gold ekle'}</Button></div></form>
        <p className="admin-wallet-hint" data-testid="admin-gold-help">Mevcut bakiyeye eklenir, bakiye sıfırlanmaz. Oyundaki oyuncu eklenen goldu bir sonraki oyun girişinde görür.</p>
        <div className="admin-wallet-exemption"><p data-testid="admin-fee-exemption-status">{account.fee_exempt ? 'Ücretsiz giriş izni: AÇIK' : 'Ücretsiz giriş izni: KAPALI'}{account.paid_access ? ' · Ücretli giriş hakkı mevcut' : ''}</p><Button type="button" variant="outline" onClick={setExemption} disabled={!!busy} data-testid="admin-toggle-fee-exemption"><ShieldCheck size={16} />{busy === 'exemption' ? 'Kaydediliyor…' : account.fee_exempt ? 'Ücretsiz giriş iznini kaldır' : 'Ücretsiz giriş izni ver'}</Button><p className="admin-wallet-hint" data-testid="admin-exemption-help">Yalnızca 1 dolarlık giriş ücreti kaldırılır. Kayıt öncesinde de tanımlanabilir. Sonraki cüzdan girişinde aktiftir.</p></div>
      </div>}
      {message && <p role="status" className="admin-wallet-success" data-testid="admin-wallet-action-result">{message}</p>}
    </section>
  </div>;
};

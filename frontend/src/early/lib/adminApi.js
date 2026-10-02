import axios from 'axios';

const PROOF_KEY = 'lastzhood-early-admin-csrf';
let proof = '';
try { proof = sessionStorage.getItem(PROOF_KEY) || ''; } catch (_) { /* Memory-only when browser storage is unavailable. */ }

export const setAdminProof = value => {
  proof = value;
  try { if (value) sessionStorage.setItem(PROOF_KEY, value); else sessionStorage.removeItem(PROOF_KEY); }
  catch (_) { /* The current tab can still use the in-memory proof. */ }
};
export const isAdminAuthError = error => [401, 403].includes(error.response?.status);

export const adminApi = axios.create({
  baseURL: `${process.env.REACT_APP_BACKEND_URL}/api/early/admin`,
  timeout: 15000,
  withCredentials: true,
  headers: { 'X-Admin-Client': 'lastzhood-admin' },
});

adminApi.interceptors.request.use(config => {
  if (proof) config.headers['X-CSRF-Token'] = proof;
  return config;
});

// Access/refresh tokens stay in HttpOnly cookies. Only the CSRF proof is kept
// in origin- and tab-scoped sessionStorage; cookies alone cannot read settings.
export const adminRequest = async (method, url, data) => {
  try { return await adminApi.request({ method, url, data }); }
  catch (error) {
    if (error.response?.status !== 401) {
      if (isAdminAuthError(error)) setAdminProof('');
      throw error;
    }
    try { await adminApi.post('/refresh'); }
    catch (failure) { if (isAdminAuthError(failure)) setAdminProof(''); throw failure; }
    return adminApi.request({ method, url, data });
  }
};

export const adminError = (error) => {
  const detail = error.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    if (detail.some(item => item.type === 'string_too_short')) return 'Tüm alanları doldurun; yalnızca boşluk kullanılamaz.';
    return detail[0]?.msg?.replace('Value error, ', '') || 'Lütfen girdiğiniz bilgileri kontrol edin.';
  }
  return 'Sunucuya ulaşılamadı. Değişiklikler kaydedilmedi; lütfen tekrar deneyin.';
};
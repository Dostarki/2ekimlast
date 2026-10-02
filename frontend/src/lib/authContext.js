import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { useAccount, useSignMessage } from 'wagmi';
import { robinhoodMainnet } from './walletConfig';

const backend = process.env.REACT_APP_BACKEND_URL;
if (!backend) throw new Error('Missing REACT_APP_BACKEND_URL');
const API = `${backend}/api`;
const TOKEN_KEY = 'dz_auth_token';
const AuthContext = createContext(null);
const accountFrom = data => ({ ...data.account, progress: data.progress, paid_access: data.paid_access === true,
  fee_exempt: data.fee_exempt === true, game_access: data.paid_access === true || data.fee_exempt === true,
  new_account: data.new_account === true });

async function request(path, body) {
  const token = localStorage.getItem(TOKEN_KEY);
  const response = await fetch(`${API}${path}`, {
    method: body === undefined ? 'GET' : 'POST', credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Account request failed. Please retry.');
  return data;
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY));
  const [status, setStatus] = useState('loading');
  const { address, chainId, status: walletStatus } = useAccount();
  const { signMessageAsync } = useSignMessage();

  const checkAuth = useCallback(async () => {
    try {
      const data = await request('/auth/me');
      if (data.authenticated && data.account) {
        const account = accountFrom(data);
        setUser(account); setStatus('authenticated');
        return account;
      }
    } catch (_) { /* An expired or absent session is not a connected identity. */ }
    setUser(null); setStatus('unauthenticated');
    return null;
  }, []);
  useEffect(() => { checkAuth(); }, [checkAuth]);
  useEffect(() => {
    if (status !== 'authenticated') return;
    const refresh = () => { checkAuth(); };
    window.addEventListener('focus', refresh);
    return () => window.removeEventListener('focus', refresh);
  }, [status, checkAuth]);

  const logout = useCallback(async () => {
    // Remove access immediately, even if the logout request needs a retry.
    setUser(null); setStatus('unauthenticated');
    try { await request('/auth/logout', {}); }
    finally { localStorage.removeItem(TOKEN_KEY); setToken(null); }
  }, []);

  useEffect(() => {
    if (!user || walletStatus === 'connecting' || walletStatus === 'reconnecting') return;
    if (walletStatus === 'disconnected' || chainId !== robinhoodMainnet.id || address?.toLowerCase() !== user.address?.toLowerCase()) {
      logout().catch(() => {});
    }
  }, [address, chainId, walletStatus, user, logout]);

  const loginWithWallet = useCallback(async () => {
    if (!address) throw new Error('Connect your wallet first.');
    if (chainId !== robinhoodMainnet.id) throw new Error('Switch to Robinhood Chain Mainnet (4663) before signing in.');
    const challenge = await request('/auth/challenge', {
      address, chain_id: robinhoodMainnet.id, domain: window.location.host, uri: window.location.origin,
    });
    if (!challenge.message) throw new Error('The server did not provide a sign-in message.');
    const signature = await signMessageAsync({ message: challenge.message, account: address });
    const data = await request('/auth/verify', { message: challenge.message, signature });
    const newToken = data.token || data.sessionToken;
    if (!newToken || !data.account) throw new Error('Wallet sign-in could not be verified.');
    localStorage.setItem(TOKEN_KEY, newToken); setToken(newToken);
    const account = accountFrom(data);
    setUser(account); setStatus('authenticated');
    return account;
  }, [address, chainId, signMessageAsync]);

  const updateProfile = useCallback(async (nickname, skin = 'soldier') => {
    const data = await request('/auth/profile', { nickname, skin });
    const account = accountFrom(data);
    setUser(account);
    return account;
  }, []);

  const value = useMemo(() => ({ user, token, status, loading: status === 'loading', checkAuth,
    loginWithWallet, logout, updateProfile }),
  [user, token, status, checkAuth, loginWithWallet, logout, updateProfile]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() { return useContext(AuthContext); }
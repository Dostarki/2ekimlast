import axios from 'axios';

const backend = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';
export const apiClient = axios.create({
  baseURL: `${backend.replace(/\/$/, '')}/api`,
  withCredentials: true,
  timeout: 12000,
});

apiClient.interceptors.request.use((config) => {
  const token = typeof localStorage !== 'undefined' && localStorage.getItem('dz_auth_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

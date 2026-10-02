const ROOT = process.env.REACT_APP_BACKEND_URL + '/api/admin';

export async function adminApi(path, options = {}, retry = true) {
  const { responseType, ...fetchOptions } = options;
  const response = await fetch(ROOT + path, { ...fetchOptions, credentials: 'include', headers: { 'Content-Type': 'application/json', ...options.headers } });
  if (response.status === 401 && retry && !['/login', '/refresh', '/logout'].includes(path)) {
    const refreshed = await fetch(ROOT + '/refresh', { method: 'POST', credentials: 'include' });
    if (refreshed.ok) return adminApi(path, options, false);
  }
  if (response.ok && responseType === 'text') return response.text();
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(typeof data.detail === 'string' ? data.detail : 'Check the values and try again.');
    error.status = response.status; throw error;
  }
  return data;
}

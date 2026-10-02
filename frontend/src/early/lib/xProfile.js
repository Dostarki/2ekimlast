import { api } from './api';

const profiles = new Map();
const images = new Map();
export const cleanXHandle = (handle) => (handle || '').trim().replace(/^@/, '').toLowerCase();
const unavailable = (handle) => ({ handle, status: 'unavailable', avatar_path: null, ownership_verified: false });

export function resolveXProfile(rawHandle) {
  const handle = cleanXHandle(rawHandle);
  if (!/^[a-z0-9_]{1,15}$/.test(handle)) return Promise.resolve(unavailable(handle));
  const cached = profiles.get(handle);
  if (cached && cached.expires > Date.now()) return cached.promise;
  const promise = api.get(`/x/profile/${encodeURIComponent(handle)}`, { timeout: 6500 })
    .then(({ data }) => data)
    .catch(() => unavailable(handle));
  profiles.set(handle, { expires: Date.now() + 60000, promise });
  while (profiles.size > 64) profiles.delete(profiles.keys().next().value);
  return promise;
}

export function loadXAvatar(rawHandle) {
  const handle = cleanXHandle(rawHandle);
  const cached = images.get(handle);
  if (cached && cached.expires > Date.now()) return cached.promise;
  const promise = resolveXProfile(handle).then(profile => {
    if (profile.status !== 'available') return null;
    return new Promise(resolve => {
      const image = new Image();
      image.crossOrigin = 'anonymous';
      image.referrerPolicy = 'no-referrer';
      let settled = false;
      const finish = (value) => {
        if (settled) return;
        settled = true; clearTimeout(timeout); image.onload = null; image.onerror = null;
        resolve(value);
      };
      const timeout = setTimeout(() => { finish(null); image.src = ''; }, 6500);
      image.onload = () => finish(image.naturalWidth && image.naturalHeight ? image : null);
      image.onerror = () => finish(null);
      // Never draw a provider-supplied URL. The only source is our bounded image proxy.
      image.src = `${process.env.REACT_APP_BACKEND_URL}/api/early/x/avatar/${encodeURIComponent(handle)}`;
    });
  });
  images.set(handle, { expires: Date.now() + 60000, promise });
  while (images.size > 64) images.delete(images.keys().next().value);
  return promise;
}
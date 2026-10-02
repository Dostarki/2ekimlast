import { useEffect, useState } from 'react';
import { cleanXHandle, loadXAvatar } from '../lib/xProfile';

export function useXAvatar(rawHandle) {
  const handle = cleanXHandle(rawHandle);
  const [state, setState] = useState({ handle, image: null, status: 'loading' });
  useEffect(() => {
    let active = true;
    setState({ handle, image: null, status: 'loading' });
    loadXAvatar(handle).then(image => {
      if (active) setState({ handle, image, status: image ? 'available' : 'unavailable' });
    }).catch(() => { if (active) setState({ handle, image: null, status: 'unavailable' }); });
    return () => { active = false; };
  }, [handle]);
  // Hide the previous handle's photo immediately, even before the effect runs.
  return state.handle === handle ? state : { handle, image: null, status: 'loading' };
}
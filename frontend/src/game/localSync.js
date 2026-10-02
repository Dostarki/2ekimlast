import { toast } from 'sonner';
const PREFIX = 'dz-local-checkpoint-';
const endpoint = `${process.env.REACT_APP_BACKEND_URL}/api/local/report`;

export function checkpoint(runId, token, report) {
  try { localStorage.setItem(PREFIX + runId, JSON.stringify({ token, report })); }
  catch { toast.error('Local recovery storage is full. Keep the game open until progress is saved.', { id: 'local-storage-full' }); }
}

export function acknowledge(runId, sequence) {
  const key = PREFIX + runId;
  try {
    const pending = JSON.parse(localStorage.getItem(key) || 'null');
    if (pending?.report.sequence <= sequence) localStorage.removeItem(key);
  } catch { /* Keep any unreadable checkpoint for diagnosis. */ }
}

export async function recoverCheckpoints() {
  const keys = Object.keys(localStorage).filter(key => key.startsWith(PREFIX));
  for (const key of keys) {
    const body = localStorage.getItem(key);
    const response = await fetch(endpoint, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body });
    if (response.ok) localStorage.removeItem(key);
    else if ([401, 410].includes(response.status)) {
      localStorage.removeItem(key);
      toast.error('An expired game recovery record could not be saved.', { id: 'expired-recovery' });
    } else throw new Error('Your previous progress is still waiting to be saved. Please retry shortly.');
  }
}

export function flushOnExit() {
  for (const key of Object.keys(localStorage).filter(key => key.startsWith(PREFIX))) {
    navigator.sendBeacon(endpoint, new Blob([localStorage.getItem(key)], { type: 'application/json' }));
  }
}
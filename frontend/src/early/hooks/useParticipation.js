import { useEffect, useState } from 'react';

const STORAGE_KEY = 'lastzhood-survivor-v1';
const emptyDraft = () => ({ handle: '', tasks: {}, opened: {}, wallet: '', bound: false, consent: false, result: null, referred_by: null, request_id: crypto.randomUUID() });
function load() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || localStorage.getItem('agnt-survivor-v1'));
    if (saved && typeof saved.handle === 'string' && typeof saved.tasks === 'object' && saved.request_id) return { ...emptyDraft(), ...saved };
  } catch (_) { /* A blocked or expired browser store must not break the form. */ }
  return emptyDraft();
}
export function useParticipation() {
  const [draft, setDraft] = useState(load);
  useEffect(() => {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(draft)); } catch (_) { /* The current in-memory session remains usable. */ }
  }, [draft]);
  const update = (patch) => setDraft(current => ({ ...current, ...(typeof patch === 'function' ? patch(current) : patch) }));
  const start = (handle) => {
    if (handle.toLowerCase() !== draft.handle.toLowerCase()) setDraft({ ...emptyDraft(), handle, referred_by: draft.referred_by });
    else update({ handle });
  };
  const reset = () => setDraft(emptyDraft());
  return { draft, update, start, reset };
}
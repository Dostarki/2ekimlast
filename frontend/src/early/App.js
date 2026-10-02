import { useCallback, useEffect, useState } from 'react';
import { Route, Routes, useSearchParams } from 'react-router-dom';
import { Toaster, toast } from './components/ui/sonner';
import { BoardLayout } from './components/BoardLayout';
import { useParticipation } from './hooks/useParticipation';
import { api } from './lib/api';
import Home from './pages/Home';
import Console from './pages/Console';
import PublicAgent from './pages/PublicAgent';
import Admin from './pages/Admin';
import './scoped.css';

function Experience() {
  const [config, setConfig] = useState(null);
  const [stats, setStats] = useState(null);
  const [recent, setRecent] = useState([]);
  const [loadError, setLoadError] = useState(false);
  const participation = useParticipation();
  const [params] = useSearchParams();
  const incomingRef = params.get('ref');
  const load = useCallback(async () => {
    try {
      const [settings, counts, latest] = await Promise.all([api.get('/config'), api.get('/agents/stats'), api.get('/agents/recent')]);
      setConfig(settings.data); setStats(counts.data); setRecent(latest.data); setLoadError(false);
    } catch (_) { setLoadError(true); }
  }, []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    const refresh = () => { if (document.visibilityState === 'visible') load(); };
    window.addEventListener('focus', refresh);
    document.addEventListener('visibilitychange', refresh);
    return () => { window.removeEventListener('focus', refresh); document.removeEventListener('visibilitychange', refresh); };
  }, [load]);
  useEffect(() => {
    if (!incomingRef) return;
    let active = true;
    api.get(`/agents/${encodeURIComponent(incomingRef)}`).then(({ data }) => {
      if (active && data.ref_code !== participation.draft.result?.ref_code) participation.update({ referred_by: data.ref_code });
    }).catch(() => { if (active) toast.error('That invitation code could not be found. You can still join.'); });
    return () => { active = false; };
    // A referral is applied once when the incoming URL changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [incomingRef]);
  return <><BoardLayout stats={stats} recent={recent} online={!!stats && !loadError} config={config}><Routes><Route index element={<Home participation={participation} config={config} loadError={loadError} retry={load} />} /><Route path="console" element={<Console participation={participation} config={config} refresh={load} loadError={loadError} retry={load} />} /><Route path="agent/:refCode" element={<PublicAgent config={config} />} /><Route path="*" element={<PublicAgent notFound config={config} />} /></Routes></BoardLayout><Toaster position="bottom-right" theme="dark" /></>;
}

export default function EarlyApp() {
  useEffect(() => { document.title = 'LastZHood — Early Access'; }, []);
  return <div className="early-app" data-testid="early-app"><Routes><Route path="/early/admin" element={<Admin />} /><Route path="/early/*" element={<Experience />} /></Routes></div>;
}
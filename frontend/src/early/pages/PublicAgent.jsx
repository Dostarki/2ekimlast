import { useEffect, useState } from 'react';
import { Link, useParams } from '../lib/router';
import { ArrowLeft, LoaderCircle, Radio } from 'lucide-react';
import { ClaimResult } from '../components/ClaimResult';
import { Button } from '../components/ui/button';
import { api } from '../lib/api';

export default function PublicAgent({ config, notFound = false }) {
  const { refCode } = useParams();
  const [agent, setAgent] = useState(null);
  const [error, setError] = useState(notFound ? 'This signal does not exist.' : '');
  useEffect(() => {
    if (notFound) return;
    let active = true; setAgent(null); setError('');
    api.get(`/agents/${encodeURIComponent(refCode)}`).then(({ data }) => { if (active) setAgent(data); }).catch(error => { if (active) setError(error.response?.status === 404 ? 'This signal does not exist.' : 'The signal was interrupted. Please try again.'); });
    return () => { active = false; };
  }, [refCode, notFound]);
  return <main className="public-agent-main" data-testid="public-agent-page">{agent ? <ClaimResult agent={agent} config={config} publicView /> : <div className="missing-signal">{error ? <><Radio size={30} /><h1 data-testid="agent-not-found">SIGNAL LOST</h1><p data-testid="public-agent-error">{error}</p><Button asChild className="primary-action"><Link to="/" data-testid="not-found-home-link"><ArrowLeft size={16} /> BACK TO THE GRID</Link></Button></> : <><LoaderCircle className="animate-spin" size={25} /><p data-testid="public-agent-loading">Locating agent…</p></>}</div>}</main>;
}
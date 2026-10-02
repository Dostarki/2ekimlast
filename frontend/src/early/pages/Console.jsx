import { useState } from 'react';
import { Link } from '../lib/router';
import { ArrowLeft, ArrowRight, Check, LoaderCircle, ShieldCheck } from 'lucide-react';
import { AgentLicense } from '../components/AgentLicense';
import { ClaimResult } from '../components/ClaimResult';
import { MissionTasks } from '../components/MissionTasks';
import { WalletForm } from '../components/WalletForm';
import { OperatorIdentity } from '../components/OperatorIdentity';
import { Button } from '../components/ui/button';
import { Checkbox } from '../components/ui/checkbox';
import { api, errorMessage } from '../lib/api';

export default function Console({ participation, config, refresh, loadError, retry }) {
  const { draft, update } = participation;
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [showResult, setShowResult] = useState(true);
  if (!draft.handle) return <main className="console-main" data-testid="console-page"><div className="missing-signal" data-testid="console-empty-state"><ShieldCheck size={30} /><h1 data-testid="console-empty-heading">START YOUR REGISTRATION</h1><p data-testid="console-empty-message">Enter your X handle first to open your mission console.</p><Button asChild className="primary-action"><Link to="/" data-testid="console-start-registration"><ArrowLeft size={16} /> BACK TO EARLY ACCESS</Link></Button></div></main>;
  const done = config?.tasks.filter(task => draft.tasks[task.id]).length || 0;
  const allDone = done === 4;
  const active = draft.result ? 4 : draft.bound && allDone ? 3 : allDone ? 2 : 1;
  const claim = async () => {
    if (!allDone || !draft.bound || !draft.consent || busy) return;
    setBusy(true); setError('');
    try {
      const { data } = await api.post('/participations', { request_id: draft.request_id, handle: draft.handle, wallet: draft.wallet, completed_tasks: config.tasks.filter(task => draft.tasks[task.id]).map(task => task.id), consent: draft.consent, referred_by: draft.referred_by });
      update({ result: data }); setShowResult(true); refresh(); window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch (err) { setError(errorMessage(err)); } finally { setBusy(false); }
  };
  return <main className="console-main" data-testid="console-page"><div className="console-topline"><Link to="/" data-testid="console-home-link"><ArrowLeft size={14} /> BACK TO THE GRID</Link><span data-testid="mission-console-label">FIELD OPERATIONS / ACCESS REGISTRY</span></div>
    {draft.result && showResult ? <ClaimResult agent={draft.result} config={config} onBack={() => setShowResult(false)} /> : <><div className="console-heading"><div><p className="small-eyebrow" data-testid="operation-code">OPERATION: GENESIS</p><h1 data-testid="console-heading">Mission console<span>_</span></h1></div><span className="console-connection" data-testid="console-connection"><i className="signal-dot" /> {draft.result ? 'REGISTERED' : 'AWAITING ORDERS'}</span></div><nav className="mission-stepper" aria-label="Registration progress" data-testid="mission-progress">{['LINK', 'TASKS', 'WALLET', 'CLAIM'].map((step, index) => <div key={step} className={active > index ? 'step-complete' : active === index ? 'step-active' : ''} aria-current={active === index ? 'step' : undefined} data-testid={`step-${step.toLowerCase()}`}><span>{active > index ? <Check size={13} /> : `0${index + 1}`}</span>{step}{step === 'TASKS' && <small>{done}/4</small>}</div>)}</nav>
    <div className="console-layout"><AgentLicense agent={draft.result} handle={draft.handle} /><div className="console-controls"><OperatorIdentity handle={draft.handle} />
    {!config ? <div className="console-loading" data-testid="console-config-loading">{loadError ? <>Mission settings unavailable. <Button variant="outline" onClick={retry} data-testid="console-retry-button">Reconnect</Button></> : <><LoaderCircle className="animate-spin" size={18} /> Receiving mission briefing…</>}</div> : <><MissionTasks config={config} draft={draft} update={update} /><WalletForm draft={draft} update={update} unlocked={allDone} /><section className="claim-section"><div className="console-section-heading"><h2 data-testid="claim-heading"><span>04</span> CLAIM</h2><ShieldCheck size={14} /></div>{draft.result ? <Button className="primary-action" onClick={() => setShowResult(true)} data-testid="view-agent-button">VIEW YOUR AGENT <ArrowRight size={16} /></Button> : <><label className="consent-label" data-testid="consent-label"><Checkbox checked={draft.consent} onCheckedChange={checked => update({ consent: !!checked })} disabled={!allDone || !draft.bound || busy} data-testid="participation-consent-checkbox" /><span>I confirm these are my details and my X tasks are complete.</span></label><Button className="primary-action claim-button" onClick={claim} disabled={!allDone || !draft.bound || !draft.consent || busy} data-testid="claim-early-access-button">{busy ? <LoaderCircle className="animate-spin" size={16} /> : null}{busy ? 'REGISTERING AGENT…' : 'CLAIM EARLY ACCESS'}<ArrowRight size={16} /></Button><p className="claim-note" data-testid="claim-privacy-note">Your handle is public. Your wallet address stays private.</p>{error && <p className="form-error" role="alert" data-testid="claim-error">{error}</p>}</>}</section></>}
    </div></div></>}
  </main>;
}
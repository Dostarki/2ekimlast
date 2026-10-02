import { Link } from '../lib/router';
import { ArrowLeft, ArrowRight, ArrowUpRight, Check, Copy, Radio } from 'lucide-react';
import { AgentLicense } from './AgentLicense';
import { Button } from './ui/button';
import { toast } from './ui/sonner';
import { shareUrl } from '../lib/api';

export const ClaimResult = ({ agent, config, onBack, publicView = false }) => {
  const copy = async (text, label) => {
    try { await navigator.clipboard.writeText(text); toast.success(<span data-testid="clipboard-success">{label} copied.</span>); }
    catch (_) { toast.error(<span data-testid="clipboard-error">Clipboard unavailable. Select and copy the displayed code.</span>); }
  };
  return <div className="result-layout" data-testid="agent-success"><AgentLicense agent={agent} handle={agent.handle} /><section className="result-content"><span className="result-overline" data-testid="access-granted"><Radio size={15} /> {publicView ? 'SIGNAL IDENTIFIED' : 'ACCESS GRANTED'}</span><h1 data-testid="agent-live-heading">AGENT<br /><span>LIVE.</span></h1><p className="result-handle" data-testid="registered-handle">@{agent.handle}<Check size={15} /></p><p className="result-copy" data-testid="registration-confirmation">{publicView ? 'Another signal on the grid. Your agent could be next.' : 'Your place on the grid is secured.\nThe next chapter starts here.'}</p><div className="result-facts"><div><span>CELL</span><strong data-testid="agent-cell">{agent.cell}</strong></div><div><span>CLASS</span><strong data-testid="agent-class">{agent.agent_class}</strong></div><div><span>TIER</span><strong data-testid="agent-tier">{agent.tier}</strong></div></div>
    {publicView ? <Button asChild className="primary-action"><Link to={`/?ref=${agent.ref_code}`} data-testid="join-with-referral-button">SPAWN YOUR AGENT <ArrowRight size={16} /></Link></Button> : <><div className="referral-box"><span data-testid="referral-label">YOUR REF CODE</span><div><code data-testid="referral-code">{agent.ref_code}</code><Button variant="ghost" size="icon" onClick={() => copy(agent.ref_code, 'Referral code')} title="Copy referral code" aria-label="Copy referral code" data-testid="copy-ref-code-button"><Copy size={16} /></Button></div></div><div className="result-actions">{config && <Button asChild className="primary-action"><a href={shareUrl(config, agent)} target="_blank" rel="noopener noreferrer" data-testid="post-on-x-button"><span>𝕏</span> POST ON X <ArrowUpRight size={16} /></a></Button>}<Button variant="outline" disabled={!config} onClick={() => copy(`${config.public_url}/?ref=${agent.ref_code}`, 'Invite link')} data-testid="copy-invite-link-button"><Copy size={14} /> Copy invite link</Button></div><p className="sharing-note" data-testid="sharing-note">Registration saved. Posting on X is optional and not verified.</p></>}
    {onBack ? <Button variant="ghost" className="back-to-console" onClick={onBack} data-testid="back-to-console-button"><ArrowLeft size={14} /> back to console</Button> : <Link to="/" className="back-to-console" data-testid="public-agent-home-link"><ArrowLeft size={14} /> back to the grid</Link>}
  </section></div>;
};
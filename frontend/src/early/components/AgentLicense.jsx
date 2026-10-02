import { useEffect, useRef } from 'react';
import { Copy, Download, Fingerprint, LoaderCircle } from 'lucide-react';
import { Button } from './ui/button';
import { toast } from './ui/sonner';
import { drawLicense, saveLicense, copyLicense } from '../lib/license';
import { numberLabel } from '../lib/api';
import { useXAvatar } from '../hooks/useXAvatar';

export const AgentLicense = ({ agent, handle }) => {
  const canvas = useRef(null);
  const avatar = useXAvatar(agent?.handle || handle);
  useEffect(() => {
    let active = true;
    drawLicense(canvas.current, agent, handle, avatar.image);
    document.fonts.ready.then(() => { if (active && canvas.current) drawLicense(canvas.current, agent, handle, avatar.image); });
    return () => { active = false; };
  }, [agent, handle, avatar.image]);
  return <section className="license-section" aria-label="Your agent license" data-testid="agent-license-section">
    <div className="section-label"><Fingerprint size={14} /><span data-testid="license-heading">PERSONNEL FILE</span><span className="license-state" data-testid="license-state">{agent ? numberLabel(agent.number) : 'UNREGISTERED'}</span></div>
    <div className="license-paper"><span className="license-tape" aria-hidden="true" /><canvas ref={canvas} className="license-canvas" role="img" aria-label={`Agent license for @${agent?.handle || handle}. ${avatar.image ? 'Public X profile photo; handle ownership not verified.' : 'Pixel character portrait.'} ${agent ? `Number ${agent.number}, class ${agent.agent_class}, cell ${agent.cell}, tier ${agent.tier}.` : 'Awaiting registration.'}`} data-testid="agent-license-canvas" data-avatar-status={avatar.status} /></div>
    <p className="profile-photo-status" aria-live="polite" data-testid="profile-photo-status">{avatar.status === 'loading' ? <><LoaderCircle className="animate-spin" size={11} /> Loading public X photo…</> : avatar.image ? 'PUBLIC X PHOTO · HANDLE NOT VERIFIED' : 'PHOTO UNAVAILABLE · CHARACTER SHOWN'}</p>
    <div className="license-actions"><Button variant="ghost" disabled={avatar.status === 'loading'} onClick={() => copyLicense(canvas.current, agent?.handle || handle)} data-testid="copy-card-button"><Copy size={14} /> Copy image</Button><Button variant="ghost" disabled={avatar.status === 'loading'} onClick={() => saveLicense(canvas.current, agent?.handle || handle).catch(() => toast.error('Could not export your card.'))} data-testid="save-card-button"><Download size={14} /> Save card</Button></div>
  </section>;
};
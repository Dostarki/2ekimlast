import { useState } from 'react';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from './ui/dialog';
import { Copy, Crown, Shield, Users } from 'lucide-react';
import './AlliancePanel.css';

export function AlliancePanel({ open, onOpenChange, alliance, me, create, join, leave, setFriendlyFire }) {
  const [code, setCode] = useState(''), [name, setName] = useState('');
  const leader = alliance?.leader_id === me?.id;
  const copy = () => navigator.clipboard?.writeText(alliance.code);
  return <Dialog open={open} onOpenChange={onOpenChange}>
    <DialogContent className="game-dialog alliance-panel" aria-describedby="alliance-description">
      <DialogHeader><div className="dialog-eyebrow"><Users size={13}/><span>02 / SOCIAL</span></div><DialogTitle>ALLIANCE</DialogTitle><DialogDescription id="alliance-description">Create a temporary squad or join one with its six-character code.</DialogDescription></DialogHeader>
      {!alliance ? <div className="alliance-empty">
        <input className="alliance-name" value={name} maxLength={18} placeholder="ALLIANCE NAME" onChange={e => setName(e.target.value)} />
        <button className="alliance-create" disabled={name.trim().length < 2} onClick={() => create(name)}><Shield size={17}/> CREATE ALLIANCE</button>
        <div className="alliance-or">OR JOIN A SQUAD</div>
        <div className="alliance-join"><input value={code} maxLength={6} placeholder="CODE" onChange={e => setCode(e.target.value.toUpperCase())}/><button disabled={code.trim().length !== 6} onClick={() => join(code)}>JOIN</button></div>
      </div> : <div className="alliance-active">
        <div className="alliance-name-display">{alliance.name}</div><div className="alliance-code"><span>JOIN CODE</span><strong>{alliance.code}</strong><button onClick={copy} title="Copy join code"><Copy size={14}/></button></div>
        <div className="alliance-members"><span>MEMBERS · {alliance.members.length}/12</span>{alliance.members.map(member => <div key={member.id}><i className="status-dot"/>{member.name}{member.id === alliance.leader_id && <Crown size={13}/>}</div>)}</div>
        <div className="alliance-toggle"><div><b>FRIENDLY FIRE</b><span>{alliance.friendly_fire ? 'ENABLED' : 'DISABLED'}</span></div><button className={`toggle ${alliance.friendly_fire ? 'on' : ''}`} disabled={!leader} aria-label="Toggle friendly fire" onClick={() => setFriendlyFire(!alliance.friendly_fire)}><i/></button></div>
        {!leader && <p className="alliance-note">Only the alliance leader can change friendly fire.</p>}
        <button className="alliance-leave" onClick={leave}>LEAVE ALLIANCE</button>
      </div>}
    </DialogContent>
  </Dialog>;
}

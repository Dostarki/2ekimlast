import { Droplets, Bug, Network } from 'lucide-react';
import './StatusEffects.css';

export const StatusEffects = ({ statuses = {}, alive }) => {
  if (!alive) return null;
  return <div className="status-effects" data-testid="status-effects" aria-live="polite">
    {statuses.bleeding > 0 && <div className="status-effect bleeding" data-testid="status-bleeding"><Droplets size={15} /><span>BLEEDING</span><b data-testid="status-bleeding-time">{Math.ceil(statuses.bleeding)}s</b></div>}
    {statuses.poison > 0 && <div className="status-effect poison" data-testid="status-poison"><Bug size={15} /><span>POISON</span><b data-testid="status-poison-time">{Math.ceil(statuses.poison)}s</b></div>}
    {statuses.webbed > 0 && <div className="status-effect webbed" data-testid="status-webbed"><Network size={15} /><span>BURNING WEB</span><b data-testid="status-webbed-time">{Math.ceil(statuses.webbed)}s</b></div>}
  </div>;
};
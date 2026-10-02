import { Zap, ArrowUp, Heart, Shield, Timer, Footprints } from 'lucide-react';
import { Dialog, DialogContent, DialogTitle, DialogDescription } from './ui/dialog';
import './StatsPanel.css';

const STATS = [
  { id: 'reload_speed',   label: 'Reload Speed',   icon: Timer,      max: 10, desc: '−5% reload time per point' },
  { id: 'move_speed',     label: 'Movement Speed',  icon: Footprints, max: 8,  desc: '+3% movement speed per point' },
  { id: 'heal_multiplier',label: 'Heal Power',      icon: Heart,      max: 8,  desc: '+10% heal effectiveness per point' },
  { id: 'durability',     label: 'Durability',      icon: Shield,     max: 10, desc: '+5 max HP per point' },
  { id: 'stamina_regen',  label: 'Stamina Regen',   icon: Zap,        max: 8,  desc: '+8% stamina regeneration per point' },
];

export const StatsPanel = ({ open, onOpenChange, state, allocateStat }) => {
  const me = state?.me;
  if (!me) return null;
  const stats = me.player_stats || {};
  const points = me.stat_points || 0;
  const xpPct = me.xp_needed > 0 ? Math.min(100, (me.xp_progress / me.xp_needed) * 100) : 100;

  return <Dialog open={open} onOpenChange={onOpenChange}><DialogContent className="stats-dialog" data-testid="stats-dialog">
    <header className="stats-heading">
      <span data-testid="stats-eyebrow">LastZHood / CHARACTER</span>
      <DialogTitle data-testid="stats-title">STATS</DialogTitle>
      <DialogDescription className="sr-only">Allocate stat points to improve your character</DialogDescription>
    </header>

    <div className="stats-level-row" data-testid="stats-level">
      <span className="stats-level-label">LEVEL {me.level}</span>
      <div className="stats-xp-bar"><i style={{ width: `${xpPct}%` }} /></div>
      <span className="stats-xp-text">{me.xp_progress?.toLocaleString('en-US')} / {me.xp_needed?.toLocaleString('en-US')} XP</span>
    </div>

    {points > 0 && <div className="stats-points-banner" data-testid="stats-points">
      <ArrowUp size={14} /> <strong>{points}</strong> STAT POINT{points > 1 ? 'S' : ''} AVAILABLE
    </div>}

    <div className="stats-grid" data-testid="stats-grid">
      {STATS.map(s => {
        const value = stats[s.id] || 0;
        const canAllocate = points > 0 && value < s.max;
        const pct = (value / s.max) * 100;
        return <div className="stat-card" key={s.id} data-testid={`stat-${s.id}`}>
          <div className="stat-header">
            <s.icon size={16} />
            <strong>{s.label}</strong>
            <span className="stat-value">{value}/{s.max}</span>
          </div>
          <div className="stat-bar"><i style={{ width: `${pct}%` }} /></div>
          <p className="stat-desc">{s.desc}</p>
          <button
            className="stat-allocate"
            disabled={!canAllocate}
            data-testid={`allocate-${s.id}`}
            onClick={() => allocateStat?.(s.id)}
          >+ ALLOCATE</button>
        </div>;
      })}
    </div>
  </DialogContent></Dialog>;
};

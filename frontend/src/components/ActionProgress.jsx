import React, { useEffect, useState, useRef } from 'react';
import { Crosshair, PlusCircle, HeartPulse, RefreshCw } from 'lucide-react';
import './ActionProgress.css';

export const ActionProgress = ({ me }) => {
  const [activeAction, setActiveAction] = useState(null);


  useEffect(() => {
    if (!me) {
      setActiveAction(null);
      return;
    }

    const isReloading = Boolean(me.reloading && me.reload_time > 0);
    const isHealing = Boolean(me.healing && me.heal_time > 0);

    if (isHealing) {
      const isMedkit = me.heal_item === 'medkit';
      const total = me.heal_duration || (isMedkit ? 4.0 : 2.0);
      const remaining = Math.max(0, me.heal_time);
      const label = isMedkit ? 'USING MEDKIT' : 'APPLYING FIRST AID';
      const icon = isMedkit ? 'medkit' : 'faid';
      
      setActiveAction({
        type: 'heal',
        label,
        icon,
        total,
        remaining,
        percent: Math.min(100, Math.max(0, ((total - remaining) / total) * 100)),
      });
    } else if (isReloading) {
      const total = me.reload_duration || 2.0;
      const remaining = Math.max(0, me.reload_time);
      
      setActiveAction({
        type: 'reload',
        label: 'RELOADING...',
        icon: 'reload',
        total,
        remaining,
        percent: Math.min(100, Math.max(0, ((total - remaining) / total) * 100)),
      });
    } else {
      setActiveAction(null);
    }
  }, [me, me?.reloading, me?.reload_time, me?.reload_duration, me?.healing, me?.heal_time, me?.heal_duration, me?.heal_item]);


  if (!activeAction) return null;

  return (
    <div className="action-progress-container" data-testid="action-progress-bar">
      <div className="action-progress-card">
        <div className="action-progress-header">
          <div className="action-progress-label">
            {activeAction.icon === 'medkit' && <PlusCircle size={15} className="action-icon heal-pulse" />}
            {activeAction.icon === 'faid' && <HeartPulse size={15} className="action-icon heal-pulse" />}
            {activeAction.icon === 'reload' && <RefreshCw size={15} className="action-icon reload-spin" />}
            <span>{activeAction.label}</span>
          </div>
          <div className="action-progress-time">
            <span>{activeAction.remaining.toFixed(1)}s</span>
            <small>({Math.round(activeAction.percent)}%)</small>
          </div>
        </div>
        
        <div className="action-progress-track">
          <div
            className={`action-progress-fill ${activeAction.type === 'heal' ? 'is-heal' : 'is-reload'}`}
            style={{ width: `${activeAction.percent}%` }}
          />
        </div>
      </div>
    </div>
  );
};

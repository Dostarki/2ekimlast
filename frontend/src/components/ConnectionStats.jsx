import { useEffect, useState } from 'react';
import './ConnectionStats.css';

export const ConnectionStats = ({ state, ping, engine }) => {
  const [stats, setStats] = useState({ fps: null, stale: false });
  useEffect(() => {
    const update = () => {
      const game = engine.current;
      setStats({ fps: game?.metrics.fps || null, stale: !!game?.lastReceivedAt && performance.timeOrigin + performance.now() - game.lastReceivedAt > 1500 });
    };
    update(); const timer = setInterval(update, 1000); return () => clearInterval(timer);
  }, [engine]);
  const delayed = ping !== null && ping >= 200;
  return <div className="connection-stats" data-testid="hud-connection">
    <div className="connection-values">
      <i className={`status-dot ${stats.stale ? 'offline' : ''}`} />
      <span data-testid="hud-online-count" title="Connected human players; bots are not counted">{state.online ?? '—'} / 200</span>
      <span data-testid="hud-ping" className={delayed ? 'connection-warn' : ''} title="Measured local input round-trip time">{ping === null ? '—' : ping} ms INPUT</span>
      <span data-testid="hud-fps" title="Frames per second">{stats.fps ?? '—'} FPS</span>
    </div>
    {stats.stale ? <span role="status" className="connection-warn" data-testid="hud-stale-connection">GAME ENGINE DELAYED</span> : <span className="connection-detail" data-testid="hud-network-details" title="Online service latency and local simulation duration">NET {state.network?.service_rtt ?? '—'} ms · SIM {Math.round(state.tick_ms || 0)} ms</span>}
    {!state.network?.sync_online && <span role="status" className="connection-warn" data-testid="hud-sync-pending">SCORES WAITING TO SYNC</span>}
  </div>;
};
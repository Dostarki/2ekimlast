import { useEffect, useState } from 'react';
import { Link } from '../lib/router';
import { ArrowUpRight, Radio, Crosshair, Gamepad2 } from 'lucide-react';
import { MapAtmosphere } from './MapAtmosphere';
import { numberLabel } from '../lib/api';

export const BoardLayout = ({ children, stats, recent, online, config }) => {
  const [clock, setClock] = useState(new Date());
  useEffect(() => { const id = setInterval(() => setClock(new Date()), 1000); return () => clearInterval(id); }, []);
  return <div className="board-shell">
    <MapAtmosphere count={stats?.count} />
    <header className="site-header">
      <Link to="/" className="site-logo" data-testid="home-logo-link" aria-label="LastZhood home">LastZhood<span className="logo-square" /></Link>
      <div className="nav-play-wrap">
        <span className="nav-play-status" data-testid="game-active-label"><i className="signal-dot" />GAME ACTIVE</span>
        <a href="/loadout" className="nav-play-button" data-testid="nav-play-button"><Gamepad2 size={18} /><span>PLAY</span></a>
      </div>
      <span className="header-center" data-testid="network-name">INDEPENDENT AGENT NETWORK <span>// EST. 2026</span></span>
      <div className="header-status"><span className="agent-count" data-testid="agent-count"><i className={online ? 'signal-dot' : 'signal-dot offline'} />{stats ? stats.count.toLocaleString('en-US') : '—'} <span>AGENTS ON THE GRID</span></span><span className="access-badge" data-testid="early-access-badge">EARLY ACCESS</span></div>
    </header>
    {children}
    <div className="board-bottom">
      <div className="ticker" data-testid="recent-participants"><div className="ticker-label"><Radio size={13} /><span>JUST SPAWNED</span></div><div className="ticker-window">{recent.length ? <div className="ticker-track">{recent.map(agent => <Link key={agent.ref_code} to={`/agent/${agent.ref_code}`} className="ticker-agent" data-testid={`recent-agent-${agent.ref_code}`}><i /><span>@{agent.handle}</span><b>{numberLabel(agent.number)}</b><ArrowUpRight size={12} /></Link>)}</div> : <span className="ticker-empty" data-testid="empty-grid-message">{online ? 'The grid is quiet. Be the first to leave a signal.' : 'Establishing a connection to the grid…'}</span>}</div><Crosshair className="ticker-cross" size={16} /></div>
      <footer className="site-footer"><span data-testid="footer-disclaimer">LastZhood <span className="footer-separator">/</span> nothing here is financial advice</span><span className="footer-network" data-testid="network-status"><i className={online ? 'signal-dot' : 'signal-dot offline'} />{online ? 'NETWORK OPERATIONAL' : 'SIGNAL UNAVAILABLE'}</span><div className="footer-right"><time data-testid="utc-clock">{clock.toLocaleTimeString('en-GB', { timeZone: 'UTC' })} UTC</time>{config && <a href={config.x_profile_url} target="_blank" rel="noopener noreferrer" aria-label="LastZhood on X" title="LastZhood on X" data-testid="footer-x-link">𝕏 <ArrowUpRight size={12} /></a>}</div></footer>
    </div>
  </div>;
};
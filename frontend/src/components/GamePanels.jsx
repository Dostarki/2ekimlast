import { useEffect, useState } from 'react';
import { Trophy, Radio, Volume2, Monitor, LogOut, RefreshCw, Crosshair } from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from './ui/dialog';
import { Button } from './ui/button';
import { API } from '../hooks/useSession';

export const GamePanels = ({ panel, close, state, inGame, leave, muted, setMuted, volume, setVolume, quality, setQuality, zoom, setZoom }) => {
  const [leaders, setLeaders] = useState([]), [tab, setTab] = useState('all'), [loading, setLoading] = useState(false), [error, setError] = useState('');
  const load = () => { setLoading(true); setError(''); fetch(API+'/leaderboard').then(r => { if (!r.ok) throw new Error(); return r.json(); }).then(setLeaders).catch(() => setError('Failed to load leaderboard.')).finally(() => setLoading(false)); };
  useEffect(() => { if (panel === 'leaderboard') load(); }, [panel]);
  const rows = tab === 'live' ? state?.leaders || [] : leaders;
  return <Dialog open={!!panel} onOpenChange={open => { if (!open) close(); }}><DialogContent className="game-dialog" data-testid={`${panel || 'game'}-modal`}>
    <DialogHeader><div className="dialog-eyebrow" data-testid="panel-eyebrow">LastZHood <span>/</span> {panel === 'leaderboard' ? 'SURVIVORS' : 'PREFERENCES'}</div><DialogTitle className="dialog-title" data-testid="panel-title">{panel === 'leaderboard' ? 'LEADERBOARD' : 'SETTINGS'}</DialogTitle><DialogDescription data-testid="panel-description">{panel === 'leaderboard' ? 'Westfall records' : inGame ? 'Online world in progress.' : 'Prepare for operation.'}</DialogDescription></DialogHeader>
    {panel === 'leaderboard' ? <div className="leaderboard-content">
      <div className="panel-tabs"><button data-testid="leaderboard-all-tab" className={tab === 'all' ? 'active' : ''} onClick={() => setTab('all')}><Trophy size={14} /> TOP ROUNDS</button><button data-testid="leaderboard-live-tab" className={tab === 'live' ? 'active' : ''} onClick={() => setTab('live')}><Radio size={14} /> LIVE</button><button onClick={load} data-testid="refresh-leaderboard" aria-label="Refresh leaderboard" title="Refresh"><RefreshCw size={14} /></button></div>
      {loading ? <p className="empty-state" data-testid="leaderboard-loading">Loading records…</p> : error ? <p className="form-error" data-testid="leaderboard-error">{error}</p> : rows.length ? <div className="leaderboard-table" data-testid="leaderboard-table"><div className="table-head"><span>#</span><span>SURVIVOR</span><span>INFECTED</span><span>SCORE</span></div>{rows.map((p, i) => <div className="leaderboard-row" data-testid={`leaderboard-row-${i}`} key={p.id}><span className={i === 0 ? 'first-place' : ''}>{String(i+1).padStart(2, '0')}</span><strong>{p.name}</strong><span>{p.kills}</span><b>{p.score.toLocaleString('en-US')}</b></div>)}</div> : <div className="empty-state" data-testid="leaderboard-empty"><Trophy size={36} strokeWidth={1} /><h3>{tab === 'live' ? 'You are not on the field yet.' : 'Claim the first record.'}</h3><p>{tab === 'live' ? 'Live standings appear when you join the game.' : 'Scores of completed rounds will be displayed here.'}</p></div>}
      <div className="panel-note" data-testid="score-rules"><span>INFECTED <b>+100</b></span><span>PLAYER <b>+25</b></span></div>
    </div> : <div className="settings-content">
      <div className="settings-group-title"><Volume2 size={16} /><span>AUDIO</span></div>
      <div className="setting-row"><label htmlFor="sound-enabled">Sound effects</label><button id="sound-enabled" className={`toggle ${!muted ? 'on' : ''}`} role="switch" aria-checked={!muted} data-testid="settings-sound-toggle" onClick={() => setMuted(!muted)}><i /></button></div>
      <div className="setting-row"><label htmlFor="sound-volume">Effect volume</label><div className="range-field"><input data-testid="settings-volume" id="sound-volume" type="range" min="0" max="1" step="0.05" value={volume} onChange={e => setVolume(Number(e.target.value))} /><span data-testid="volume-value">{Math.round(volume*100)}%</span></div></div>
      <div className="settings-group-title"><Monitor size={16} /><span>DISPLAY</span></div>
      <div className="setting-row"><label>Graphics quality</label><div className="segmented"><button data-testid="quality-auto" className={quality === 'auto' ? 'active' : ''} onClick={() => setQuality('auto')}>Auto</button><button data-testid="quality-performance" className={quality === 'low' ? 'active' : ''} onClick={() => setQuality('low')}>Smooth</button><button data-testid="quality-high" className={quality === 'high' ? 'active' : ''} onClick={() => setQuality('high')}>High</button></div></div>
      <div className="setting-row"><label htmlFor="map-zoom">Camera zoom</label><div className="range-field"><input data-testid="settings-zoom" id="map-zoom" type="range" min="4" max="40" step="1" value={zoom} onChange={e => setZoom(Number(e.target.value))} /><span>{Math.round(zoom)}</span></div></div>
      <div className="settings-group-title"><Crosshair size={16} /><span>CONTROLS</span></div><div className="control-list" data-testid="settings-controls"><span>Move <b><kbd>W</kbd><kbd>A</kbd><kbd>S</kbd><kbd>D</kbd></b></span><span>Fire <kbd>LEFT CLICK</kbd></span><span>Sprint <kbd>SHIFT</kbd></span><span>Reload <kbd>R</kbd></span><span>Leaderboard <kbd>TAB</kbd></span><span>Menu <kbd>ESC</kbd></span><span data-testid="zoom-control-hint">Zoom <kbd>WHEEL</kbd></span></div>
      <div className="settings-actions"><Button className="panel-primary" data-testid="settings-done" onClick={close}>{inGame ? 'RESUME GAME' : 'DONE'}</Button>{inGame && <Button variant="ghost" className="leave-button" data-testid="leave-game-button" onClick={leave}><LogOut size={15} /> RETURN TO LOBBY</Button>}</div>
      <a href="/audio/CREDITS.txt" target="_blank" rel="noreferrer" className="audio-credits" data-testid="audio-credits-link">Audio credits and licenses ↗</a>
    </div>}
  </DialogContent></Dialog>;
};

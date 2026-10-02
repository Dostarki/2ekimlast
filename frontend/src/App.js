import { useState, useRef, useEffect, lazy, Suspense } from 'react';
import { BrowserRouter, useLocation, useNavigate } from 'react-router-dom';
import { useConnectModal, useAccountModal, useChainModal } from '@rainbow-me/rainbowkit';
import { Biohazard, BookOpen, Settings2, Trophy, Volume2, VolumeX, Crosshair, ArrowUpRight, Radio, Maximize2 } from 'lucide-react';
import { Toaster } from './components/ui/sonner';
import { Button } from './components/ui/button';
import { Lobby } from './components/Lobby';
import { HUD, Minimap } from './components/HUD';
import { BossMap } from './components/BossMap';
import { BossHUD } from './components/BossHUD';
import { GamePanels } from './components/GamePanels';
import { StartScreen } from './components/StartScreen';
import DocsPage from './components/DocsPage';
import AdminPage from './components/AdminPage';
import { Inventory } from './components/Inventory';
import { StatsPanel } from './components/StatsPanel';
import { CraftPanel } from './components/CraftPanel';
import { RadialMenu } from './components/RadialMenu';
import { AlliancePanel } from './components/AlliancePanel';
import { MarketPanel } from './components/MarketPanel';
import { WalletGate } from './components/WalletGate';
import { getSkin } from './game/skins';
import { WEAPONS } from './game/config';
import { GameRenderer } from './game/renderer';
import { audio } from './game/audio';
import { loadPreferences, savePreferences } from './game/preferences';
import { useSession, API } from './hooks/useSession';
import './App.css';
const EarlyApp = lazy(() => import('./early/App'));

const SLOT_KEYS = new Set(['1','2','3','4','5','6','7','8','9','0']);
const DEFAULT_WEAPON_SLOTS = { glock18: '1', ak47: '2' };
const loadWeaponSlots = () => loadPreferences().weaponSlots;

export function GameApp() {
  const { connectModalOpen } = useConnectModal();
  const { accountModalOpen } = useAccountModal();
  const { chainModalOpen } = useChainModal();
  const container = useRef(null), engine = useRef(null);
  const preferences = useRef(loadPreferences());
  const [ready, setReady] = useState(false), [worldError, setWorldError] = useState(''), [status, setStatus] = useState(null);
  const weapon = 'glock18';
  const [muted, setMuted] = useState(() => preferences.current.muted);
  const [inventoryOpen, setInventoryOpen] = useState(false);
  const [statsOpen, setStatsOpen] = useState(false);
  const [craftOpen, setCraftOpen] = useState(false);
  const [radialOpen, setRadialOpen] = useState(false);
  const [allianceOpen, setAllianceOpen] = useState(false);
  const [marketOpen, setMarketOpen] = useState(false);
  const [weaponSlots, setWeaponSlots] = useState(loadWeaponSlots);
  const [volume, setVolume] = useState(() => preferences.current.volume);
  const [quality, setQuality] = useState(() => preferences.current.quality);
  const [zoom, setZoom] = useState(() => preferences.current.zoom);
  const [skin, setSkin] = useState(() => getSkin(preferences.current.skin).id);
  const [bossMapOpen,setBossMapOpen]=useState(false),[trackedBoss,setTrackedBoss]=useState('boss-hansel');
  const location = useLocation(), navigate = useNavigate(), session = useSession(engine);
  const panel = location.pathname === '/leaderboard' ? 'leaderboard' : location.pathname === '/settings' ? 'settings' : null;
  const inGame = session.mode === 'playing';
  const returnPath = inGame ? '/play' : '/loadout';
  useEffect(() => {
    document.title = 'LastZHood — Westfall'; document.documentElement.lang = 'en';
    audio.preload().catch(()=>{});
    let active = true;
    fetch(API+'/world').then(r => { if (!r.ok) throw new Error(); return r.json(); }).then(world => {
      if (active && container.current) { engine.current = new GameRenderer(container.current, world, setWorldError, setZoom); engine.current.setQuality(preferences.current.quality); engine.current.setZoom(preferences.current.zoom); setReady(true); }
    }).catch(() => { if (active) setWorldError('The world could not be loaded. Check your connection and try again.'); });
    const refresh = () => fetch(API+'/status').then(r => r.json()).then(s => { if (active) setStatus(s); }).catch(() => { if (active) setStatus(null); });
    refresh(); const timer = setInterval(refresh, 5000);
    return () => { active = false; clearInterval(timer); engine.current?.dispose(); };
  }, []);
  useEffect(() => { audio.enabled = !muted; audio.volume = volume; audio.sync(); }, [muted, volume]);
  useEffect(() => { if (ready && !inGame) engine.current?.setMode('lobby', weapon, skin); }, [weapon, skin, ready, inGame]);
  useEffect(() => { savePreferences({ muted, volume, quality, skin, weaponSlots, zoom }); }, [muted, volume, quality, skin, weaponSlots, zoom]);
  useEffect(() => { engine.current?.setBlocked(!!panel || bossMapOpen || inventoryOpen || statsOpen || craftOpen || radialOpen || allianceOpen || marketOpen || session.state?.me.hp === 0); }, [panel, bossMapOpen, inventoryOpen, statsOpen, craftOpen, radialOpen, allianceOpen, marketOpen, session.state?.me.hp]);
  useEffect(() => { if (!inGame || panel || session.state?.me.hp === 0) { setInventoryOpen(false); setStatsOpen(false); setCraftOpen(false); setRadialOpen(false); setMarketOpen(false); } }, [inGame, panel, session.state?.me.hp]);
  useEffect(()=>{if(!inGame||panel)setBossMapOpen(false);},[inGame,panel]);
  useEffect(() => {
    if (inGame && location.pathname === '/loadout') navigate('/play', { replace: true });
    if (!inGame && session.mode === 'lobby' && location.pathname === '/play') navigate('/loadout', { replace: true });
  }, [inGame, session.mode, location.pathname, navigate]);
  useEffect(() => {
    const keyDownHandler = e => {
      if (connectModalOpen || accountModalOpen || chainModalOpen) return;
      if (/INPUT|TEXTAREA|SELECT/.test(e.target.tagName) || e.target.isContentEditable) return;
      const isAlive = session.state?.me.hp > 0;

      if (inGame && isAlive && !panel && !inventoryOpen && !bossMapOpen && !statsOpen && !craftOpen && !radialOpen && !allianceOpen && !marketOpen && !e.repeat && /^Digit[0-9]$/.test(e.code)) {
        const key = e.code.slice(-1);
        const target = Object.entries(weaponSlots).find(([, slot]) => slot === key)?.[0];
        if (target && session.state?.me.inventory?.[target] && target !== session.state.me.weapon) { e.preventDefault(); session.equip(target); }
      }

      // Radial menu toggle on I key
      if (e.code === 'KeyI' && inGame && !panel && isAlive && !e.repeat) {
        e.preventDefault();
        if (inventoryOpen || bossMapOpen || statsOpen || craftOpen || marketOpen) {
          setInventoryOpen(false); setBossMapOpen(false); setStatsOpen(false); setCraftOpen(false); setMarketOpen(false);
          setRadialOpen(false);
          return;
        }
        setRadialOpen(open => !open);
      }

      if (e.code === 'KeyM' && inGame && !panel && !bossMapOpen && isAlive && !e.repeat) { e.preventDefault(); setMarketOpen(open => !open); }
      if (e.code === 'KeyP' && inGame && !panel && !bossMapOpen && isAlive && !e.repeat) { e.preventDefault(); setStatsOpen(open => !open); }
      if (e.code === 'KeyC' && inGame && !panel && !bossMapOpen && isAlive && !e.repeat) { e.preventDefault(); setCraftOpen(open => !open); }
      if (e.code === 'KeyG' && inGame && !panel && isAlive && !e.repeat) { e.preventDefault(); setAllianceOpen(open => !open); }
      if (e.code === 'KeyQ' && inGame && !panel && !bossMapOpen && !inventoryOpen && !statsOpen && !craftOpen && !radialOpen && !marketOpen && isAlive && !e.repeat) {
        e.preventDefault(); session.onUseHeal?.('medkit');
      }
      if (e.code === 'KeyF' && inGame && !panel && !bossMapOpen && !inventoryOpen && !statsOpen && !craftOpen && !radialOpen && !marketOpen && isAlive && !e.repeat) {
        e.preventDefault(); session.onUseHeal?.('faid');
      }
      if (e.code === 'Escape') {
        if (radialOpen || inventoryOpen || bossMapOpen || statsOpen || craftOpen || allianceOpen || marketOpen) {
          e.preventDefault(); e.stopPropagation();
          setRadialOpen(false);
          setInventoryOpen(false); setBossMapOpen(false); setStatsOpen(false); setCraftOpen(false);
          setAllianceOpen(false); setMarketOpen(false);
          return;
        }
        if (!panel) { e.preventDefault(); navigate('/settings'); }
      }
      if (e.code === 'Tab' && inGame && !panel && !bossMapOpen && !inventoryOpen && !statsOpen && !craftOpen && !radialOpen && !marketOpen) { e.preventDefault(); navigate('/leaderboard'); }
    };

    window.addEventListener('keydown', keyDownHandler, true);
    return () => {
      window.removeEventListener('keydown', keyDownHandler, true);
    };
  }, [navigate, panel, inGame, bossMapOpen, inventoryOpen, statsOpen, craftOpen, radialOpen, allianceOpen, marketOpen, weaponSlots, session.state?.me.hp, session, connectModalOpen, accountModalOpen, chainModalOpen]);

  const setWeaponSlot = (weaponId, key) => setWeaponSlots(current => {
    const next = Object.fromEntries(Object.entries(current).filter(([id, slot]) => id !== weaponId && slot !== key));
    if (SLOT_KEYS.has(key)) next[weaponId] = key;
    return next;
  });

  const handleRadialSelect = target => {
    setRadialOpen(false);
    if (target === 'inventory') setInventoryOpen(true);
    else if (target === 'craft') setCraftOpen(true);
    else if (target === 'stats') setStatsOpen(true);
    else if (target === 'map') setBossMapOpen(true);
    else if (target === 'market') setMarketOpen(true);
  };

  const setGraphics = value => {
    preferences.current = { ...preferences.current, quality: value }; setQuality(value); engine.current?.setQuality(value);
  };
  const setCameraZoom = value => { preferences.current = { ...preferences.current, zoom: value }; setZoom(value); engine.current?.setZoom(value); };
  const fullScreen = async () => { try { if (document.fullscreenElement) await document.exitFullscreen(); else await document.documentElement.requestFullscreen(); } catch { setWorldError('Fullscreen is unavailable in this browser.'); } };
  return <main className={`deadzone-app ${inGame ? 'is-playing' : 'is-lobby'}`} data-testid="deadzone-app">
    <div ref={container} className="world-canvas" data-testid="world-container" />
    <div className="world-grade" /><div className="edge-vignette" />
    {!inGame && <>
      <div className="lobby-shade" />
      <header className="topbar">
        <button className="brand" onClick={() => navigate('/')} data-testid="brand-home" aria-label="LastZHood home"><span className="brand-icon"><Biohazard size={24} /></span><span>LastZHood<span className="brand-period">®</span></span></button>
        <nav className="main-nav" aria-label="Main navigation">
          <button className={!panel ? 'active' : ''} onClick={() => navigate('/loadout')} data-testid="nav-play"><Crosshair size={14} /> CHARACTER</button>
          <button className={panel === 'leaderboard' ? 'active' : ''} onClick={() => navigate('/leaderboard')} data-testid="nav-leaderboard"><Trophy size={14} /> LEADERBOARD</button>
          <button className={panel === 'settings' ? 'active' : ''} onClick={() => navigate('/settings')} data-testid="nav-settings"><Settings2 size={14} /> SETTINGS</button>
          <button className="nav-docs" onClick={() => navigate('/docs')} data-testid="nav-docs" title="Field Guide" aria-label="Docs — Field Guide"><BookOpen size={14} aria-hidden="true" /> Docs</button>
          <button onClick={() => navigate('/early')} data-testid="nav-early"><ArrowUpRight size={14} /> Early</button>
        </nav>
        <div className="topbar-right">
          <WalletGate testIdPrefix="header-wallet" />
          <div className="server-status" data-testid="server-status"><i className={status ? 'status-dot' : 'status-dot offline'} /><span>{status ? 'SERVER ONLINE' : 'CONNECTING'}<small>WESTFALL–01</small></span><Radio size={17} /></div>
        </div>
      </header>

      <Lobby skin={skin} setSkin={setSkin} start={session.start} mode={session.mode} ready={ready} error={session.error || worldError} loadingMessage={session.loadingMessage} cancel={session.leave} />
      <div className="world-bottom" data-testid="world-bottom"><span className="live-world-label"><i className="status-dot" /> WESTFALL–01</span><div className="population"><strong data-testid="online-count">{String(status?.online ?? 0).padStart(2, '0')}</strong><span>/ 200<small>SURVIVORS</small></span></div><span className="online-separator" /><div className="world-detail"><Crosshair size={18} /><span>FRIENDLY FIRE<small>ON</small></span></div><ArrowUpRight className="world-arrow" size={26} /></div>
      <footer className="lobby-footer"><span data-testid="version-label">EARLY ACCESS <b>ALPHA 0.1</b></span><span className="footer-message" data-testid="footer-message">EVERY LIFE IS A STORY. EVERY BULLET IS A CHOICE.</span><div><button data-testid="sound-toggle" aria-label={muted ? 'Enable sound' : 'Mute sound'} title={muted ? 'Enable sound' : 'Mute sound'} onClick={() => setMuted(!muted)}>{muted ? <VolumeX size={17} /> : <Volume2 size={17} />}</button><button data-testid="fullscreen-button" aria-label="Fullscreen" title="Fullscreen" onClick={fullScreen}><Maximize2 size={16} /></button></div></footer>
    </>}
    {inGame && <>
      <HUD
        state={session.state}
        ping={session.ping}
        engine={engine}
        onInventory={() => setInventoryOpen(true)}
        onMarket={() => setMarketOpen(true)}
        onStats={() => setStatsOpen(true)}
        onCraft={() => setCraftOpen(true)}
        onAlliance={() => setAllianceOpen(true)}
        onBossMap={() => setBossMapOpen(true)}
        onSettings={() => navigate('/settings')}
        onLeaderboard={() => navigate('/leaderboard')}
        onRespawn={session.respawn}
        onLeave={() => { session.leave(); navigate('/loadout'); }}
        muted={muted}
        toggleMuted={() => setMuted(!muted)}
        onUseHeal={session.onUseHeal}
        bossHud={<BossHUD state={session.state} selected={trackedBoss} openMap={() => setBossMapOpen(true)} />}
      />
      <Inventory open={inventoryOpen} onOpenChange={setInventoryOpen} state={session.state} equip={session.equip} weaponSlots={weaponSlots} setWeaponSlot={setWeaponSlot} equipmentEquip={session.equipmentEquip} consumeEnergy={session.useConsumable} />
      <StatsPanel open={statsOpen} onOpenChange={setStatsOpen} state={session.state} allocateStat={session.allocateStat} />
      <CraftPanel open={craftOpen} onOpenChange={setCraftOpen} state={session.state} craft={session.craft} equipmentCraft={session.equipmentCraft} equipmentUpgrade={session.equipmentUpgrade} convertMaterial={session.convertMaterial} />
      <MarketPanel open={marketOpen} onOpenChange={setMarketOpen} state={session.state} soldierBuy={session.soldierBuy} soldierActivate={session.soldierActivate} soldierDeactivate={session.soldierDeactivate} soldierUpgrade={session.soldierUpgrade} soldierRename={session.soldierRename} sellItem={session.sellItem} />
      <AlliancePanel open={allianceOpen} onOpenChange={setAllianceOpen} alliance={session.state?.me?.alliance} me={session.state?.me} create={session.allianceCreate} join={session.allianceJoin} leave={session.allianceLeave} setFriendlyFire={session.allianceFriendlyFire} />
      <RadialMenu visible={radialOpen} onSelect={handleRadialSelect} onClose={() => setRadialOpen(false)} />
      <BossMap state={session.state} open={bossMapOpen} onOpenChange={setBossMapOpen} selected={trackedBoss} select={setTrackedBoss} />
    </>}
    {!ready && !worldError && <div className="world-loading" data-testid="world-loading"><span className="loading-ring" /><span>LOADING WESTFALL</span></div>}
    {worldError && !ready && <Button className="retry-world" data-testid="retry-world" onClick={() => window.location.reload()}>Try again</Button>}
    <GamePanels panel={panel} close={() => navigate(returnPath)} state={session.state} inGame={inGame} leave={() => { session.leave(); navigate('/loadout'); }} muted={muted} setMuted={setMuted} volume={volume} setVolume={setVolume} quality={quality} setQuality={setGraphics} zoom={zoom} setZoom={setCameraZoom} />
    <Toaster theme="dark" position="top-center" richColors />
  </main>;
}
function AppRoutes() {
  const location = useLocation(), navigate = useNavigate();
  const isDocs = location.pathname === '/docs' || location.pathname === '/docs/';
  useEffect(() => { document.title = isDocs ? 'Westfall Field Guide — LastZHood' : 'LastZHood — Westfall'; document.documentElement.lang = 'en'; }, [isDocs]);
  if (location.pathname.startsWith('/admin')) return <AdminPage />;
  if (location.pathname === '/early' || location.pathname.startsWith('/early/')) return <Suspense fallback={<div className="world-loading" data-testid="early-loading">LOADING EARLY ACCESS</div>}><EarlyApp /></Suspense>;
  if (isDocs) return <DocsPage />;
  if (process.env.NODE_ENV === 'development' && location.pathname === '/__dev/craft-fixture') return <DevCraftFixture />;
  if (process.env.NODE_ENV === 'development' && location.pathname === '/__dev/minimap-fixture') return <DevMinimapFixture />;
  if (location.pathname === '/') return <StartScreen onStart={() => navigate('/loadout')} />;
  return <GameApp />;
}
function DevCraftFixture() {
  const [open, setOpen] = useState(true);
  const allParts = ['fabric','plate','binding','mechanism'].flatMap(family => [1,2,3].map(tier => [`${family}_t${tier}`, 99]));
  const me = { hp: 100, gold: 99999, level: 50, weapon: 'glock18', inventory: { glock18: true, ak47: true }, weapon_parts: [
    'barrel_common','stock_common','grip_common','spring_common','receiver_uncommon','barrel_uncommon','grip_uncommon','stock_uncommon','barrel_rare','receiver_rare','optic_rare','suppressor_rare'
  ].flatMap(id => [{ id }, { id }, { id }]), owned_equipment: ['helm_t1', 'vest_t2'], equipment_levels: { helm_t1: 1, vest_t2: 0 }, equipment_parts: Object.fromEntries(allParts), calibration: { calibration_t1: 9, calibration_t2: 9, calibration_t3: 9 } };
  return <main className="deadzone-app is-lobby" data-testid="craft-fixture"><CraftPanel open={open} onOpenChange={setOpen} state={{ me }} craft={() => {}} equipmentCraft={() => {}} equipmentUpgrade={() => {}} convertMaterial={() => {}} /></main>;
}
function DevMinimapFixture() {
  const pose = useRef({ x: 0, z: 0, heading: 0, valid: true });
  const [paused, setPaused] = useState(false);
  const [, tick] = useState(0);
  const engine = useRef({ minimapPose: pose.current, nearby: [{ houses: [{ x: 18, z: 8, w: 18, d: 10, enterable: true, door: { x: 18, z: 3 } }, { x: -22, z: -12, w: 12, d: 20, enterable: true, door: { x: -16, z: -12 } }] }] });
  useEffect(() => { let step = 0; const timer = setInterval(() => { if (paused) return; step += 1; pose.current.x = Math.cos(step / 8) * 8; pose.current.z = Math.sin(step / 8) * 8; pose.current.heading = [0, Math.PI / 2, Math.PI, -Math.PI / 2, Math.PI - .08, -Math.PI + .08][Math.floor(step / 12) % 6]; tick(step); }, 50); return () => clearInterval(timer); }, [paused]);
  const state = { me: pose.current, zombies: [{ x: 13, z: 11 }, { x: -18, z: 7 }], players: [{ x: -8, z: -15 }], bosses: [{ id: 'boss-hansel', alive: true, x: 35, z: 0, color: '#f3ae52' }, { id: 'boss-symbiote', alive: true, x: -35, z: 0, color: '#eb6c80' }, { id: 'boss-xenomorph', alive: true, x: 0, z: 35, color: '#94d6bf' }, { id: 'boss-ash_titan', alive: true, x: 0, z: -35, color: '#f88b5c' }] };
  const nudge = (x, z) => { pose.current.x += x * 4; pose.current.z += z * 4; pose.current.heading = Math.atan2(x, z); tick(value => value + 1); };
  return <main className="deadzone-app is-lobby" data-testid="minimap-fixture"><div style={{ width: 'min(360px, calc(100vw - 32px))', padding: 24 }}><Minimap state={state} engine={engine} /><div data-testid="minimap-fixture-controls" style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 6, marginTop: 12 }}><button data-testid="minimap-move-up" onClick={() => nudge(0, -1)}>↑</button><button data-testid="minimap-turn-wrap" onClick={() => { pose.current.heading = pose.current.heading > 0 ? -Math.PI + .02 : Math.PI - .02; tick(value => value + 1); }}>TURN</button><button data-testid="minimap-move-right" onClick={() => nudge(1, 0)}>→</button><button data-testid="minimap-move-left" onClick={() => nudge(-1, 0)}>←</button><button data-testid="minimap-pause" onClick={() => setPaused(value => !value)}>{paused ? 'PLAY' : 'PAUSE'}</button><button data-testid="minimap-move-down" onClick={() => nudge(0, 1)}>↓</button></div></div></main>;
}
export default function App() { return <BrowserRouter><AppRoutes /></BrowserRouter>; }

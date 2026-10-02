import { useEffect, useState, useRef } from 'react';
import { Backpack, Hammer, Star, Map, Crosshair, X } from 'lucide-react';
import './RadialMenu.css';

const SECTORS = [
  {
    id: 'inventory',
    label: 'INVENTORY',
    sub: 'GEAR & AMMUNITION',
    direction: 'TOP',
    arrow: '▲',
    color: '#c8d6a0',
    icon: Backpack,
    hint: 'TOP'
  },
  {
    id: 'craft',
    label: 'CRAFTING',
    sub: 'WEAPONS & WORKSHOP',
    direction: 'BOTTOM',
    arrow: '▼',
    color: '#f09838',
    icon: Hammer,
    hint: 'BOTTOM'
  },
  {
    id: 'map',
    label: 'ZONE MAP',
    sub: 'BOSSES & SURVEILLANCE',
    direction: 'LEFT',
    arrow: '◄',
    color: '#62bed2',
    icon: Map,
    hint: 'LEFT'
  },
  {
    id: 'stats',
    label: 'STATISTICS',
    sub: 'LEVEL & ATTRIBUTES',
    direction: 'RIGHT',
    arrow: '►',
    color: '#e5c158',
    icon: Star,
    hint: 'RIGHT'
  },
];

export const RadialMenu = ({ visible, onSelect, onClose }) => {
  const [selected, setSelected] = useState('inventory');
  const [angle, setAngle] = useState(-Math.PI / 2);
  const [distance, setDistance] = useState(0);
  const centerRef = useRef({ x: window.innerWidth / 2, y: window.innerHeight / 2 });

  useEffect(() => {
    if (!visible) return;

    centerRef.current = { x: window.innerWidth / 2, y: window.innerHeight / 2 };
    setSelected('inventory');
    setAngle(-Math.PI / 2);
    setDistance(0);

    const handleMouseMove = (e) => {
      const dx = e.clientX - centerRef.current.x;
      const dy = e.clientY - centerRef.current.y;
      const dist = Math.hypot(dx, dy);
      setDistance(dist);

      const rad = Math.atan2(dy, dx);
      setAngle(rad);

      // Distinct 4-way quadrant separation with 30px deadzone
      if (dist >= 30) {
        if (Math.abs(dy) >= Math.abs(dx)) {
          setSelected(dy < 0 ? 'inventory' : 'craft');
        } else {
          setSelected(dx < 0 ? 'map' : 'stats');
        }
      }
    };

    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, [visible]);

  if (!visible) return null;

  const currentSector = SECTORS.find(s => s.id === selected) || SECTORS[0];

  return (
    <div className="radial-overlay" data-testid="radial-menu">
      <div className="radial-backdrop" onClick={onClose} />

      <button className="radial-close-btn" onClick={onClose} title="Close (ESC / I)" aria-label="Close radial menu">
        <X size={20} />
      </button>

      <div className="radial-container">
        {/* Tactical background grid & axis lines */}
        <div className="radial-radar-rings" />
        <div className="radial-axis-h" />
        <div className="radial-axis-v" />
        <div className="radial-quadrant-dividers" />

        {/* Dynamic Pointer Needle */}
        <div
          className="radial-needle"
          style={{
            transform: `rotate(${angle + Math.PI / 2}rad)`,
            opacity: distance > 25 ? 1 : 0.25
          }}
        >
          <div className="needle-head" style={{ borderBottomColor: currentSector.color, filter: `drop-shadow(0 0 8px ${currentSector.color})` }} />
        </div>

        {/* 4 Dedicated Quadrant Cards */}
        <div className="radial-quadrants">
          {/* TOP: INVENTORY */}
          <div
            className={`radial-wedge wedge-up ${selected === 'inventory' ? 'active' : ''}`}
            onMouseEnter={() => setSelected('inventory')}
            onClick={() => onSelect('inventory')}
            data-testid="radial-wedge-inventory"
          >
            <div className="wedge-badge top-badge">
              <span className="arrow-icon">▲</span>
              <span>TOP</span>
            </div>
            <div className="wedge-content">
              <Backpack size={28} className="wedge-icon" />
              <strong>INVENTORY</strong>
              <small>GEAR & AMMUNITION</small>
            </div>
            <div className="wedge-glow" />
          </div>

          {/* BOTTOM: CRAFTING */}
          <div
            className={`radial-wedge wedge-down ${selected === 'craft' ? 'active' : ''}`}
            onMouseEnter={() => setSelected('craft')}
            onClick={() => onSelect('craft')}
            data-testid="radial-wedge-craft"
          >
            <div className="wedge-badge bottom-badge">
              <span className="arrow-icon">▼</span>
              <span>BOTTOM</span>
            </div>
            <div className="wedge-content">
              <Hammer size={28} className="wedge-icon" />
              <strong>CRAFTING</strong>
              <small>WEAPONS & WORKSHOP</small>
            </div>
            <div className="wedge-glow" />
          </div>

          {/* LEFT: ZONE MAP */}
          <div
            className={`radial-wedge wedge-left ${selected === 'map' ? 'active' : ''}`}
            onMouseEnter={() => setSelected('map')}
            onClick={() => onSelect('map')}
            data-testid="radial-wedge-map"
          >
            <div className="wedge-badge left-badge">
              <span className="arrow-icon">◄</span>
              <span>LEFT</span>
            </div>
            <div className="wedge-content">
              <Map size={26} className="wedge-icon" />
              <strong>MAP</strong>
              <small>BOSS RADAR</small>
            </div>
            <div className="wedge-glow" />
          </div>

          {/* RIGHT: STATS */}
          <div
            className={`radial-wedge wedge-right ${selected === 'stats' ? 'active' : ''}`}
            onMouseEnter={() => setSelected('stats')}
            onClick={() => onSelect('stats')}
            data-testid="radial-wedge-stats"
          >
            <div className="wedge-badge right-badge">
              <span className="arrow-icon">►</span>
              <span>RIGHT</span>
            </div>
            <div className="wedge-content">
              <Star size={26} className="wedge-icon" />
              <strong>STATS</strong>
              <small>ATTRIBUTES</small>
            </div>
            <div className="wedge-glow" />
          </div>
        </div>

        {/* Center Interactive Hub */}
        <div
          className="radial-center-hub"
          onClick={() => onSelect(selected)}
          style={{ borderColor: currentSector.color }}
          title={`Click to open ${currentSector.label}`}
        >
          {/* Compass Indicators */}
          <div className="hub-compass-arrows">
            <span className={`compass-dir c-top ${selected === 'inventory' ? 'active' : ''}`}>▲</span>
            <span className={`compass-dir c-right ${selected === 'stats' ? 'active' : ''}`}>►</span>
            <span className={`compass-dir c-bottom ${selected === 'craft' ? 'active' : ''}`}>▼</span>
            <span className={`compass-dir c-left ${selected === 'map' ? 'active' : ''}`}>◄</span>
          </div>

          <div className="hub-reticle">
            <Crosshair size={22} style={{ color: currentSector.color }} />
          </div>

          <div className="hub-info">
            <span className="hub-direction" style={{ color: currentSector.color }}>
              [{currentSector.arrow} {currentSector.hint}]
            </span>
            <strong className="hub-title">{currentSector.label}</strong>
            <small className="hub-sub">{currentSector.sub}</small>
          </div>

          <div className="hub-action-btn" style={{ borderColor: currentSector.color, color: currentSector.color }}>
            CLICK TO OPEN
          </div>
        </div>
      </div>

      {/* Bottom helper strip */}
      <div className="radial-footer-hint">
        <button
          type="button"
          className="radial-quick-market-btn"
          onClick={() => onSelect('market')}
        >
          MARKET & SQUAD (M) ↗
        </button>
        <span className="hint-sep">|</span>
        <span>PRESS <kbd>I</kbd> OR <kbd>ESC</kbd> TO CLOSE</span>
      </div>
    </div>
  );
};

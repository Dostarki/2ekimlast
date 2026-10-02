import { useState, useEffect } from 'react';
import { useAccount } from 'wagmi';
import { ArrowRight, ChevronRight, Crosshair, ShieldAlert, UserRound, LoaderCircle, Wallet, ShieldCheck, ShoppingBag } from 'lucide-react';
import { Button } from './ui/button';
import { SkinSelector } from './SkinSelector';
import { CharacterShowcase } from './CharacterShowcase';
import { WalletGate } from './WalletGate';
import { OffgameMarketModal } from './OffgameMarketModal';
import { useAuth } from '../lib/authContext';
export { WEAPONS } from '../game/config';

export const Lobby = ({ skin, setSkin, start, mode, ready, error, loadingMessage, cancel }) => {
  const { user, status, checkAuth } = useAuth();
  const { isConnected } = useAccount();
  const [name, setName] = useState(() => localStorage.getItem('deadzone-name') || 'Wanderer');
  const [marketOpen, setMarketOpen] = useState(false);

  useEffect(() => {
    if (user?.nickname) {
      setName(user.nickname);
      localStorage.setItem('deadzone-name', user.nickname);
    }
  }, [user]);

  const isAuthenticated = status === 'authenticated' && !!user;

  const submit = e => {
    e.preventDefault();
    if (!isAuthenticated || !user.game_access) return;
    localStorage.setItem('deadzone-name', name);
    start(name, 'glock18', skin);
  };

  return (
    <section className="lobby" data-testid="lobby-panel">
      <div className="lobby-heading">
        <div className="eyebrow" data-testid="game-eyebrow">
          <span className="red-tick" /> WESTFALL <span className="eyebrow-slash">/</span> LOADOUT
        </div>
        <h1 className="loadout-title" data-testid="game-title">PREPARE YOUR CHARACTER</h1>
      </div>

      <div className="lobby-wallet-section">
        <div className="wallet-header-info">
          <span className="wallet-step-badge">REQUIRED</span>
          <span className="wallet-step-title">ROBINHOOD CHAIN IDENTITY</span>
        </div>
        <WalletGate onProfileLoaded={(prof) => prof?.nickname && setName(prof.nickname)} />
      </div>

      {/* Off-Game Market & VIP Entry Banner */}
      {isConnected && <div className="lobby-market-banner" data-testid="lobby-market-banner">
        <div className="market-banner-left">
          <div className="market-banner-eyebrow">
            <span className="market-pulse-dot" /> TACTICAL SUPPLY DEPOT
          </div>
          <div className="market-banner-title">TACTICAL SUPPLY</div>
        </div>
        <button
          type="button"
          className="market-banner-btn"
          onClick={() => setMarketOpen(true)}
          data-testid="lobby-market-btn"
        >
          <ShoppingBag size={14} />
          <span>OPEN MARKET</span>
          <ChevronRight size={14} />
        </button>
      </div>}

      <form onSubmit={submit} className="loadout-form">
        <label className="section-label" htmlFor="nickname" data-testid="nickname-label">
          <span>01</span> YOUR CALL SIGN
        </label>
        <div className="nickname-field">
          <UserRound size={16} />
          <input
            id="nickname"
            data-testid="nickname-input"
            autoComplete="nickname"
            minLength={2}
            maxLength={18}
            required
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder="Enter your call sign"
            disabled={!isAuthenticated}
          />
          <span className="field-status">
            {isAuthenticated ? (
              <>VERIFIED <ShieldCheck size={14} className="status-verified-icon" /></>
            ) : (
              <>LOCKED <i className="status-dot offline" /></>
            )}
          </span>
        </div>

        <SkinSelector skin={skin} setSkin={setSkin} />
        <CharacterShowcase skin={skin} weapon="glock18" />

        <div className="friendly-warning" data-testid="friendly-fire-warning">
          <ShieldAlert size={15} />
          <span>Friendly fire is on.</span>
          <span>Central Outpost (0,0) is a Safe Zone. Combat is disabled.</span>
        </div>

        {error && <p className="form-error" role="alert" data-testid="connection-error">{error}</p>}

        {isAuthenticated ? (
          <Button
            className="start-button"
            type="submit"
            data-testid="join-game-button"
            disabled={!ready || mode === 'connecting' || !user.game_access}
          >
            <span className="start-icon">
              {mode === 'connecting' ? <LoaderCircle className="spin" /> : <Crosshair />}
            </span>
            <span className="start-copy">
              {mode === 'connecting' ? 'PREPARING WORLD' : 'JOIN GAME'}
              <small data-testid="join-access-status">{mode === 'connecting' ? loadingMessage : user.game_access ? (user.fee_exempt ? 'ADMIN FREE ACCESS ACTIVE' : 'PERMANENT ACCESS ACTIVE') : 'ONE-TIME ACCESS REQUIRED'}</small>
            </span>
            <ArrowRight size={22} />
          </Button>
        ) : (
          <div className="wallet-lock-notice" data-testid="wallet-lock-notice">
            <Wallet size={16} />
            <span>Wallet sign-in required · One-time access $1 in ETH</span>
          </div>
        )}

        {mode === 'connecting' && <Button variant="outline" type="button" onClick={cancel} data-testid="cancel-world-loading">CANCEL LOADING</Button>}
        <div className="lobby-under-button" data-testid="lobby-mode">
          <span className="status-dot" /> FREE FOR ALL <span>•</span> OPEN WORLD <ChevronRight size={12} />
        </div>
      </form>
      <OffgameMarketModal open={marketOpen} onClose={() => setMarketOpen(false)} onRefreshProfile={checkAuth} />
    </section>
  );
};

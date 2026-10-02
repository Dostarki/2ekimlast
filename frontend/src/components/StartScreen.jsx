import { useState } from 'react';
import { useAccount } from 'wagmi';
import { Button } from './ui/button';
import { Link } from 'react-router-dom';
import { BookOpen, ShoppingBag, ArrowUpRight } from 'lucide-react';
import { OffgameMarketModal } from './OffgameMarketModal';
import { useAuth } from '../lib/authContext';
import './StartScreen.css';

export const StartScreen = ({ onStart }) => {
  const [marketOpen, setMarketOpen] = useState(false);
  const { checkAuth } = useAuth();
  const { isConnected } = useAccount();
  return <section className="start-screen" data-testid="start-screen">
  <picture className="start-banner" data-testid="start-banner">
    <img src="/images/lastzhood-survival-map.jpg" alt="LastZHood survival map background" fetchPriority="high" data-testid="start-banner-image" />
  </picture>
  <header className="start-title"><span data-testid="start-world-name">WESTFALL</span><h1 data-testid="start-game-title">LastZHood</h1></header>
  <Button className="intro-start-button" data-testid="start-game-button" onClick={onStart}>START GAME</Button>
  {isConnected && <button className="start-market-button" data-testid="start-market-button" onClick={() => setMarketOpen(true)}><ShoppingBag size={14} /> OPEN MARKET</button>}
  <Link to="/docs" className="start-docs-link" data-testid="start-docs-button"><BookOpen size={15} aria-hidden="true" /> Docs</Link>
  <nav className="start-early-nav" aria-label="Early access" data-testid="start-navigation"><Link to="/early" data-testid="start-early-button">EARLY <ArrowUpRight size={16} aria-hidden="true" /></Link></nav>
  <OffgameMarketModal open={marketOpen} onClose={() => setMarketOpen(false)} onRefreshProfile={checkAuth} />
</section>;
};

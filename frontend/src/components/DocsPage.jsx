import { useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ArrowRight, Biohazard, BookOpen, Compass, Crosshair, Flag, HelpCircle, Keyboard, Menu, Package, Search, Shield, Users, Wallet, Wrench, X } from 'lucide-react';
import { Dialog, DialogContent, DialogTitle, DialogTrigger } from './ui/dialog';
import { CHAPTERS, GUIDE_UPDATED, findChapter, searchGuide } from '../content/playerDocs';
import './DocsPage.css';

const ICONS = { compass: Compass, keyboard: Keyboard, wallet: Wallet, shield: Shield, crosshair: Crosshair, wrench: Wrench, biohazard: Biohazard, users: Users, flag: Flag, package: Package, help: HelpCircle };
const chapterUrl = (id, hash = '') => `/docs?chapter=${id}${hash ? `#${hash}` : ''}`;

export default function DocsPage() {
  const location = useLocation();
  const chapter = findChapter(new URLSearchParams(location.search).get('chapter'));
  const index = CHAPTERS.indexOf(chapter);
  const [query, setQuery] = useState('');
  const [menuOpen, setMenuOpen] = useState(false);
  const articleTitle = useRef(null);
  const initial = useRef(true);
  const results = searchGuide(query);
  const Icon = ICONS[chapter.icon];
  useEffect(() => {
    document.title = 'Westfall Field Guide — LastZHood';
    document.documentElement.lang = 'en';
    return () => { document.title = 'LastZHood — Westfall'; };
  }, []);
  useEffect(() => {
    setQuery(''); setMenuOpen(false);
    const frame = requestAnimationFrame(() => {
      let hashId = location.hash.slice(1);
      try { hashId = decodeURIComponent(hashId); } catch { /* A malformed shared hash must not break the guide. */ }
      const target = (location.hash && document.getElementById(hashId)) || articleTitle.current;
      if (target) {
        if (!initial.current || location.hash) target.focus({ preventScroll: true });
        if (location.hash) target.scrollIntoView({ block: 'start' });
        else if (!initial.current) window.scrollTo(0, 0);
      }
      initial.current = false;
    });
    return () => cancelAnimationFrame(frame);
  }, [chapter.id, location.hash]);
  const navigation = scope => <nav aria-label="Guide chapters" className="docs-chapters" data-testid={`docs-${scope}-chapters`}>{CHAPTERS.map((ch, i) => {
    const ChapterIcon = ICONS[ch.icon];
    return <Link key={ch.id} to={chapterUrl(ch.id)} data-testid={`docs-${scope}-chapter-${ch.id}`} aria-current={chapter.id === ch.id ? 'page' : undefined} onClick={() => { setMenuOpen(false); setQuery(''); }}><span className="docs-chapter-number">{String(i + 1).padStart(2, '0')}</span><ChapterIcon size={16} aria-hidden="true"/><span>{ch.title}</span></Link>;
  })}</nav>;
  const toc = scope => <nav aria-label="On this page" className="docs-toc-links" data-testid={`docs-${scope}-toc`}>{chapter.sections.map(s => <Link key={s.id} to={chapterUrl(chapter.id, s.id)} data-testid={`docs-${scope}-toc-${s.id}`}>{s.title}</Link>)}</nav>;
  return <div className="docs-page" data-testid="docs-page">
    <a href="#guide-article" className="docs-skip" data-testid="docs-skip-link">Skip to guide</a>
    <header className="docs-header">
      <Link to="/" className="docs-brand" aria-label="LastZHood home" data-testid="docs-home-link"><Biohazard size={25} aria-hidden="true"/>LastZHood<span>®</span></Link>
      <span className="docs-header-label" data-testid="docs-header-label">WESTFALL / FIELD GUIDE</span>
      <Link to="/loadout" className="docs-play" data-testid="docs-start-game">START GAME <ArrowRight size={16} aria-hidden="true"/></Link>
    </header>
    <div className="docs-layout">
      <aside className="docs-sidebar">
        <p className="docs-eyebrow" data-testid="docs-handbook-label"><BookOpen size={14} aria-hidden="true"/> SURVIVOR HANDBOOK</p>
        {navigation('sidebar')}
        <div className="docs-sidebar-foot" data-testid="docs-sidebar-footer"><span>EARLY ACCESS</span><p>Prepare. Survive. Build.</p><small>Updated {GUIDE_UPDATED}</small></div>
      </aside>
      <main id="guide-article" className="docs-main" tabIndex={-1} data-testid="docs-content-container">
        <div className="docs-tools">
          <Dialog open={menuOpen} onOpenChange={setMenuOpen}><DialogTrigger asChild><button className="docs-menu-button" data-testid="docs-mobile-menu-trigger"><Menu size={17} aria-hidden="true"/> CHAPTERS</button></DialogTrigger><DialogContent className="docs-mobile-dialog" aria-describedby={undefined} data-testid="docs-mobile-menu"><DialogTitle data-testid="docs-mobile-menu-title">Field Guide chapters</DialogTitle>{navigation('mobile')}</DialogContent></Dialog>
          <div className="docs-search"><Search size={17} aria-hidden="true"/><label className="sr-only" htmlFor="guide-search" data-testid="docs-search-label">Search the field guide</label><input id="guide-search" value={query} onChange={e => setQuery(e.target.value)} placeholder="Search supplies, controls, missions…" type="search" autoComplete="off" data-testid="docs-search-input"/>{query && <button aria-label="Clear search" onClick={() => setQuery('')} data-testid="docs-search-clear"><X size={16} aria-hidden="true"/></button>}</div>
        </div>
        {query.trim() && <section className="docs-results" aria-label="Search results" data-testid="docs-search-results"><p className="docs-eyebrow" aria-live="polite" data-testid="docs-search-count">{results.length} RESULTS FOR “{query}”</p>{results.length ? results.map(({ chapter: ch, section: s }) => <Link key={s.id} to={chapterUrl(ch.id, s.id)} onClick={() => setQuery('')} data-testid={`docs-search-result-${s.id}`}><small>{ch.title}</small><strong>{s.title}<ArrowRight size={16} aria-hidden="true"/></strong><span>{s.text.slice(0, 150)}…</span></Link>) : <p data-testid="docs-search-empty">No matching sections. Try “medkit”, “wallet” or “mission”.</p>}</section>}
        <article>
          <div className="docs-article-hero"><div className="docs-hero-symbol"><Icon size={38} strokeWidth={1.2} aria-hidden="true"/></div><p className="docs-eyebrow" data-testid="docs-chapter-number">FIELD NOTE {String(index + 1).padStart(2, '0')} / {String(CHAPTERS.length).padStart(2, '0')}</p><h1 ref={articleTitle} tabIndex={-1} data-testid="docs-chapter-title">{chapter.title}</h1><p className="docs-summary" data-testid="docs-chapter-summary">{chapter.summary}</p><div className="docs-hero-rule" data-testid="docs-world-label"><span>WESTFALL–01</span><span>PLAYER GUIDE / ENGLISH</span></div></div>
          <details className="docs-inline-toc"><summary data-testid="docs-inline-toc-toggle">On this page</summary>{toc('inline')}</details>
          {chapter.sections.map((s, i) => <section className="docs-section" key={s.id} data-testid={`docs-section-${s.id}`}><h2 id={s.id} tabIndex={-1} data-testid={`docs-heading-${s.id}`}><span>{String(i + 1).padStart(2, '0')}</span><Link to={chapterUrl(chapter.id, s.id)} data-testid={`docs-heading-link-${s.id}`}>{s.title}</Link></h2><p data-testid={`docs-text-${s.id}`}>{s.text}</p>
            {s.steps && <ol className="docs-steps">{s.steps.map((step, n) => <li key={step} data-testid={`docs-step-${s.id}-${n}`}><span>{String(n + 1).padStart(2, '0')}</span><p>{step}</p></li>)}</ol>}
            {s.cards && <div className="docs-cards">{s.cards.map(([title, text], n) => <div key={title} data-testid={`docs-card-${s.id}-${n}`}><Shield size={20} aria-hidden="true"/><strong>{title}</strong><p>{text}</p></div>)}</div>}
            {s.table && <div className="docs-table-wrap" tabIndex={0} role="region" aria-label={`${s.title} table`} data-testid={`docs-table-${s.id}`}><table><caption data-testid={`docs-table-caption-${s.id}`}>{s.title}</caption><thead><tr>{s.table.headers.map((h, n) => <th key={h} scope="col" data-testid={`docs-table-header-${s.id}-${n}`}>{h}</th>)}</tr></thead><tbody>{s.table.rows.map((row, n) => <tr key={n}>{row.map((cell, j) => j === 0 ? <th scope="row" key={j} data-testid={`docs-table-cell-${s.id}-${n}-${j}`}>{cell}</th> : <td key={j} data-testid={`docs-table-cell-${s.id}-${n}-${j}`}>{cell}</td>)}</tr>)}</tbody></table></div>}
            {s.note && <aside className="docs-note" data-testid={`docs-note-${s.id}`}><Shield size={18} aria-hidden="true"/><p>{s.note}</p></aside>}
            {s.related && <div className="docs-related"><span>CONTINUE READING</span>{s.related.map(id => <Link to={chapterUrl(id)} key={id} data-testid={`docs-related-${s.id}-${id}`}>{findChapter(id).title}<ArrowRight size={13} aria-hidden="true"/></Link>)}</div>}
          </section>)}
          <nav className="docs-pagination" aria-label="Previous and next chapters">{index > 0 ? <Link to={chapterUrl(CHAPTERS[index - 1].id)} data-testid="docs-previous-chapter"><small>PREVIOUS FIELD NOTE</small><strong>{CHAPTERS[index - 1].title}</strong></Link> : <Link to="/loadout" data-testid="docs-prepare-character"><small>READY TO DEPLOY?</small><strong>Prepare your character</strong></Link>}{index < CHAPTERS.length - 1 && <Link to={chapterUrl(CHAPTERS[index + 1].id)} data-testid="docs-next-chapter"><small>NEXT FIELD NOTE →</small><strong>{CHAPTERS[index + 1].title}</strong></Link>}</nav>
        </article>
        <footer className="docs-footer" data-testid="docs-footer">LASTZHOOD / WESTFALL<span>Early Access · Updated {GUIDE_UPDATED}</span></footer>
      </main>
      <aside className="docs-toc"><p className="docs-eyebrow">ON THIS PAGE</p>{toc('sidebar')}<div className="docs-readiness" data-testid="docs-readiness"><Shield size={25} aria-hidden="true"/><strong>Know your next move.</strong><p>Read the guide. Check your loadout. Leave safety prepared.</p><Link to="/loadout" data-testid="docs-sidebar-prepare-character">PREPARE CHARACTER <ArrowRight size={13} aria-hidden="true"/></Link></div></aside>
    </div>
  </div>;
}

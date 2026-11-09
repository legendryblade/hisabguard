import { Component, useEffect, useRef, useState } from 'react';
import type { ErrorInfo, ReactNode } from 'react';
import { api, setAccessToken } from './api';
import { AuthRevision, useResource } from './hooks';
import { Link, navigate, usePath } from './navigation';
import { ErrorBox } from './components';
import Queue from './Queue';
import TripDesk from './TripDesk';
import { ActivityPage, NewTripPage, NotFoundPage, SettingsPage } from './Pages';

class Boundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch(_error: Error, _info: ErrorInfo) { /* Evidence and tokens must not enter console logs. */ }
  render() {
    return this.state.failed ? <main className="fatal"><div className="demo-banner"><strong>Synthetic demonstration</strong><span>Operator review is not bank verification. Follow-ups are drafts only.</span></div><h1>HisabGuard could not display this page</h1><p>Your records remain on the server. Reload to reconnect.</p><button onClick={() => window.location.reload()}>Reload application</button></main> : this.props.children;
  }
}

function Shell({ authOpen, setAuthOpen, reconnect, authRevision }: { authOpen: boolean; setAuthOpen: (open: boolean) => void; reconnect: () => void; authRevision: number }) {
  const path = usePath();
  const status = useResource(api.status, 'provider-status');
  const [navOpen, setNavOpen] = useState(false);
  const [token, setToken] = useState('');
  const [remember, setRemember] = useState(true);
  const [resetBusy, setResetBusy] = useState(false);
  const [resetError, setResetError] = useState<string | null>(null);
  const main = useRef<HTMLElement>(null);
  const tokenInput = useRef<HTMLInputElement>(null);
  useEffect(() => {
    setNavOpen(false);
    main.current?.scrollTo({ top: 0 });
    main.current?.querySelector<HTMLElement>('h1')?.focus();
    document.title = `HisabGuard | ${path === '/' ? 'Trip settlements' : path === '/settings' ? 'Provider settings' : path === '/activity' ? 'Activity' : path === '/trips/new' ? 'New trip' : 'Settlement desk'}`;
  }, [path]);
  useEffect(() => { if (authOpen) tokenInput.current?.focus(); }, [authOpen]);
  const tripMatch = /^\/trips\/(\d+)\/?$/.exec(path);
  let page: ReactNode;
  if (path === '/') page = <Queue />;
  else if (path === '/trips/new') page = <NewTripPage />;
  else if (tripMatch) page = <TripDesk id={tripMatch[1]!} status={status.data} />;
  else if (path === '/activity') page = <ActivityPage />;
  else if (path === '/settings') page = <SettingsPage />;
  else page = <NotFoundPage />;

  async function resetDemo() {
    if (!window.confirm('Reset this synthetic judge sandbox? This does not touch the private operator application, and does not restore the investigation budget.')) return;
    setResetBusy(true); setResetError(null);
    try { await api.resetDemo(); navigate('/'); reconnect(); status.reload(); }
    catch (error) { setResetError(error instanceof Error ? error.message : 'Demo reset failed.'); }
    finally { setResetBusy(false); }
  }

  return <div className="app-shell">
    <a className="skip-link" href="#workspace">Skip to workspace</a>
    <aside className="sidebar">
      <Link className="brand" href="/" aria-label="HisabGuard home"><span className="brand-mark" aria-hidden="true">HG<span /></span><span><strong>HisabGuard</strong><span lang="bn">হিসাবগার্ড</span></span></Link>
      <button className="mobile-menu" type="button" aria-expanded={navOpen} aria-controls="main-navigation" onClick={() => setNavOpen(!navOpen)}>{navOpen ? 'Close menu' : 'Menu'}</button>
      <nav id="main-navigation" className={navOpen ? 'navigation navigation-open' : 'navigation'} aria-label="Main navigation">
        <span className="nav-caption">OPERATOR WORKSPACE</span>
        <Link className={path === '/' || path.startsWith('/trips/') ? 'nav-link active' : 'nav-link'} aria-current={path === '/' || path.startsWith('/trips/') ? 'page' : undefined} href="/"><span className="nav-number">01</span>Trip settlements</Link>
        <Link className={path === '/activity' ? 'nav-link active' : 'nav-link'} aria-current={path === '/activity' ? 'page' : undefined} href="/activity"><span className="nav-number">02</span>Activity</Link>
        <Link className={path === '/settings' ? 'nav-link active' : 'nav-link'} aria-current={path === '/settings' ? 'page' : undefined} href="/settings"><span className="nav-number">03</span>Settings</Link>
      </nav>
      <div className="sidebar-foot"><span className="eyebrow">The review boundary</span><p>Documents support facts.<br />Statements stay statements.</p><small>Single-operator pilot<br />No banking or message sending.</small></div>
    </aside>
    <div className="workspace-shell">
      <header className="topbar"><span className="desk-label">TRANSPORT SETTLEMENT DESK</span><div className="topbar-actions">{status.data ? (status.data.mode === 'model' ? <span className="mode-flag mode-flag-model" role="note">MODEL MODE — live AI calls enabled</span> : <span className="mode-flag mode-flag-demo" role="note">DEMO MODE — deterministic rules only, no AI calls</span>) : <span className="mode-flag">{status.loading ? 'Checking provider mode' : 'Provider mode unavailable'}</span>}{status.data?.judge_mode && <button type="button" disabled={resetBusy} onClick={() => void resetDemo()}>{resetBusy ? 'Resetting...' : 'Reset synthetic demo'}</button>}<button type="button" onClick={() => setAuthOpen(!authOpen)} aria-expanded={authOpen}>Access</button></div></header>
      <main id="workspace" className="workspace" ref={main}>
        <div className="demo-banner"><strong>Synthetic demonstration</strong><span>Illustrative records, not customer validation. Operator confirmation is not bank verification. Follow-ups are drafts only.</span></div>
        {status.data?.judge_mode && <div className="mode-disclosure"><strong>Judge scope: real text investigation on reviewed synthetic records</strong><p>Uploads, OCR and voice processing are excluded from this submission instance. Use synthetic examples only. Investigation attempts remaining: {status.data.judge_runs_remaining ?? 'not reported'}.</p></div>}
        <ErrorBox message={resetError} />
        {status.error && <ErrorBox message={`Provider status: ${status.error}`} retry={status.reload} />}
        {authOpen && <section className="access-panel" aria-labelledby="access-heading"><div><span className="eyebrow">Private workspace</span><h2 id="access-heading">Connect with an access token</h2><p>The token is sent only in the API Authorization header. No provider keys belong here.</p></div>
          <form onSubmit={(event) => { event.preventDefault(); setAccessToken(token, remember); setToken(''); setAuthOpen(false); reconnect(); }}>
            <label htmlFor="access-token">Access token</label><input ref={tokenInput} id="access-token" type="password" autoComplete="off" value={token} onChange={(event) => setToken(event.target.value)} required />
            <label className="check-label"><input type="checkbox" checked={remember} onChange={(event) => setRemember(event.target.checked)} />Remember for this browser session only</label>
            <div className="button-row"><button className="primary" type="submit">Connect and retry</button><button type="button" onClick={() => { setAccessToken('', false); setToken(''); reconnect(); }}>Clear token</button><button type="button" onClick={() => setAuthOpen(false)}>Cancel</button></div>
          </form>
        </section>}
        <div key={`${path}:${authRevision}`} className="route-content">{page}</div>
        <footer className="workspace-footer"><span>HisabGuard / Evidence before settlement</span><span>BDT · Draft-only follow-ups · Synthetic pilot</span></footer>
      </main>
    </div>
  </div>;
}

export default function App() {
  const [authOpen, setAuthOpen] = useState(false);
  const [authRevision, setAuthRevision] = useState(0);
  useEffect(() => {
    const onUnauthorized = () => setAuthOpen(true);
    window.addEventListener('hisabguard:unauthorized', onUnauthorized);
    return () => window.removeEventListener('hisabguard:unauthorized', onUnauthorized);
  }, []);
  return <Boundary><AuthRevision.Provider value={authRevision}><Shell authOpen={authOpen} setAuthOpen={setAuthOpen} reconnect={() => setAuthRevision((value) => value + 1)} authRevision={authRevision} /></AuthRevision.Provider></Boundary>;
}

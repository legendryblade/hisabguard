import { useState } from 'react';
import { api } from './api';
import { Badge, Empty, ErrorBox, Loading, PageHeader } from './components';
import { useResource } from './hooks';
import { Link } from './navigation';
import { label, money } from './utils';
import { tripStatuses } from './types';

export default function Queue() {
  const resource = useResource(api.trips, 'queue');
  const [search, setSearch] = useState('');
  const [view, setView] = useState<'all' | 'flagged'>('flagged');
  const [status, setStatus] = useState('all');
  const data = resource.data;
  const trips = data?.trips.filter((trip) => (view === 'all' || trip.exceptions_count > 0) && (status === 'all' || trip.status === status)
    && [trip.code, trip.customer, trip.driver, trip.truck, trip.origin, trip.destination].join(' ').toLowerCase().includes(search.toLowerCase().trim()))
    .sort((a, b) => b.exceptions_count - a.exceptions_count || b.id - a.id) ?? [];
  return <>
    <PageHeader eyebrow="01 / Settlement register" title="Trip settlements" actions={<Link className="button primary" href="/trips/new">New trip</Link>}><p>Find the missing proof. Review the record. Then close the account.</p></PageHeader>
    {resource.loading && <Loading text="Loading trip register..." />}
    <ErrorBox message={resource.error} retry={resource.reload} />
    {data && <>
      <section className="register-totals" aria-label="Independent queue totals">
        <div className="total-main"><span>Customer outstanding</span><strong className="amount">{money(data.overview.outstanding_bdt)}</strong><small>Independent settlement total, not promises</small></div>
        <div><span>Trips in register</span><strong>{data.overview.trips}</strong><small>All trips, regardless of filter</small></div>
        <div><span>Exceptions</span><strong className="risk-text">{data.overview.exceptions}</strong><small>Evidence issues to review</small></div>
        <div><span>Pending approvals</span><strong>{data.overview.pending_approvals}</strong><small>Draft messages, not sent</small></div>
      </section>
      <section className="queue-section" aria-labelledby="queue-title">
        <div className="section-header"><div><span className="eyebrow">REVIEW QUEUE</span><h2 id="queue-title">{view === 'flagged' ? 'Flagged trips' : 'All trips'} <span className="count">{trips.length}</span></h2></div><button type="button" onClick={resource.reload}>Refresh register</button></div>
        <div className="queue-controls">
          <div className="segmented" role="group" aria-label="Queue view"><button aria-pressed={view === 'flagged'} className={view === 'flagged' ? 'selected' : ''} onClick={() => setView('flagged')}>Flagged trips</button><button aria-pressed={view === 'all'} className={view === 'all' ? 'selected' : ''} onClick={() => setView('all')}>All trips</button></div>
          <label className="search-field">Search trips<input type="search" placeholder="Trip, customer, truck or driver" value={search} onChange={(event) => setSearch(event.target.value)} /></label>
          <label className="status-field">Settlement status<select value={status} onChange={(event) => setStatus(event.target.value)}><option value="all">All statuses</option>{tripStatuses.map((value) => <option key={value} value={value}>{label(value)}</option>)}</select></label>
        </div>
        {!data.trips.length ? <Empty title="Start the first trip packet"><p>Add a trip, then attach the invoice, delivery proof and payment records.</p><Link className="button primary" href="/trips/new">New trip</Link></Empty>
          : !trips.length ? <Empty title="No trips match this view"><p>Try all trips or clear the search and status filters.</p><button onClick={() => { setView('all'); setSearch(''); setStatus('all'); }}>Show all trips</button></Empty>
          : <table className="trip-table"><caption className="sr-only">Settlement queue. Customer outstanding and driver advance balance are independent accounts.</caption><thead><tr><th>Trip / counterparties</th><th>Evidence</th><th>Customer due</th><th>Driver balance</th><th>Review status</th><th><span className="sr-only">Open</span></th></tr></thead><tbody>{trips.map((trip) => <tr key={trip.id}>
            <td data-label="Trip"><strong className="trip-code">{trip.code}</strong><span>{trip.customer}</span><small>{trip.truck} · {trip.driver}</small><small>{trip.origin || 'Origin not recorded'} → {trip.destination || 'Destination not recorded'}</small></td>
            <td data-label="Evidence"><strong>{trip.evidence_count}</strong><small>records</small></td>
            <td data-label="Customer due"><strong className="amount">{money(trip.outstanding_bdt)}</strong><small>Received {money(trip.received_bdt)}</small></td>
            <td data-label="Driver balance"><strong className="amount">{money(trip.advance_balance_bdt)}</strong><small>Advance less expense / returns</small></td>
            <td data-label="Review status"><Badge value={trip.status} />{trip.exceptions_count > 0 && <span className="risk-text">{trip.exceptions_count} {trip.exceptions_count === 1 ? 'issue' : 'issues'}</span>}</td>
            <td><Link className="button open-trip" href={`/trips/${encodeURIComponent(String(trip.id))}`}>Open trip<span className="sr-only"> {trip.code}</span><span aria-hidden="true">↗</span></Link></td>
          </tr>)}</tbody></table>}
      </section>
      <div className="queue-note"><strong>Two balances. Two responsibilities.</strong><p>A customer's promise does not reduce outstanding money. The driver's unaccounted advance is tracked separately until supported expenses or cash returns are reviewed.</p></div>
    </>}
  </>;
}

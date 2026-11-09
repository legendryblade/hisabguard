import type { ReactNode } from 'react';
import { dateTime, jsonText, label } from './utils';
import { Link } from './navigation';
import type { Audit } from './types';

export function Badge({ value, children }: { value: string; children?: ReactNode }) {
  return <span className={`badge badge-${value}`}>{children ?? label(value)}</span>;
}
export function ErrorBox({ message, retry }: { message: string | null; retry?: () => void }) {
  if (!message) return null;
  return <div className="feedback feedback-error" role="alert"><div><strong>Needs attention</strong><p>{message}</p></div>{retry && <button type="button" onClick={retry}>Retry</button>}</div>;
}
export function Notice({ children }: { children: ReactNode }) {
  return <div className="feedback feedback-success" role="status">{children}</div>;
}
export function Loading({ text = 'Loading settlement records...' }: { text?: string }) {
  return <div className="loading" role="status"><span className="loading-line" />{text}</div>;
}
export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return <div className="empty"><span className="eyebrow">No records</span><h3>{title}</h3>{children}</div>;
}
export function Sources({ ids, tripId }: { ids: number[]; tripId?: number }) {
  if (!ids.length) return <span className="muted">No supporting evidence IDs</span>;
  return <span className="sources" aria-label="Evidence sources">{ids.map((id, index) => <a key={`${id}-${index}`} href={`${tripId === undefined ? '' : `/trips/${encodeURIComponent(String(tripId))}`}#evidence-${id}`} onClick={() => window.dispatchEvent(new CustomEvent('hisabguard:show-evidence', { detail: id }))}>E{id}</a>)}</span>;
}
export function AuditList({ records, global = false }: { records: Audit[]; global?: boolean }) {
  if (!records.length) return <Empty title="No activity recorded yet"><p>Evidence reviews, investigation runs and draft decisions will appear here.</p></Empty>;
  return <ol className="audit-list">{[...records].sort((a, b) => b.id - a.id).map((entry) => <li key={entry.id}>
    <div className="audit-id">A{entry.id}</div>
    <div><div className="audit-heading"><strong>{label(entry.event)}</strong><span>{entry.actor}</span></div>
      <time dateTime={entry.created_at}>{dateTime(entry.created_at)}</time>
      {global && entry.trip_id !== null && <Link className="text-link" href={`/trips/${encodeURIComponent(String(entry.trip_id))}`}>Open trip {entry.trip_id}</Link>}
      <details><summary>Event details</summary><pre>{jsonText(entry.detail)}</pre></details>
    </div>
  </li>)}</ol>;
}

export function PageHeader({ eyebrow, title, children, actions }: { eyebrow: string; title: string; children?: ReactNode; actions?: ReactNode }) {
  return <header className="page-heading"><div><span className="eyebrow">{eyebrow}</span><h1 tabIndex={-1}>{title}</h1>{children}</div>{actions && <div className="header-actions">{actions}</div>}</header>;
}

import { useEffect, useRef, useState } from 'react';
import { api, ApiError, downloadBlob } from './api';
import { AuditList, Badge, Empty, ErrorBox, Loading, Notice, PageHeader, Sources } from './components';
import EvidenceSection from './Evidence';
import type { Mutation } from './Evidence';
import { useResource, useTask } from './hooks';
import { Link } from './navigation';
import { canClose, dateTime, jsonText, latestRun, money } from './utils';
import type { Action, MoneyColumn, ProviderStatus, TripDetail } from './types';

const moneyLabels: Record<MoneyColumn, string> = {
  invoice_bdt: 'Invoice', received_bdt: 'Received payments', outstanding_bdt: 'Customer outstanding',
  expense_bdt: 'Reviewed expenses', advance_bdt: 'Driver advance', cash_return_bdt: 'Cash returned', advance_balance_bdt: 'Driver advance balance',
};

function MoneyLedger({ detail }: { detail: TripDetail }) {
  const settlement = detail.settlement;
  function line(column: MoneyColumn, main = false) {
    return <div className={main ? 'ledger-line ledger-balance' : 'ledger-line'} key={column}><div><span>{moneyLabels[column]}</span><Sources ids={settlement.sources[column] ?? []} /></div><strong className="amount">{money(settlement[column])}</strong></div>;
  }
  return <section className="money-ledger" aria-label="Independent settlement money summary"><div className="ledger-heading"><span className="eyebrow">INDEPENDENT VALIDATOR / CONFIRMED RECORDS ONLY</span><span>Revision {detail.trip.revision}</span></div><div className="ledger-accounts"><div><h2>Customer account</h2>{line('invoice_bdt')}{line('received_bdt')}{line('outstanding_bdt', true)}</div><div><h2>Driver account</h2>{line('advance_bdt')}{line('expense_bdt')}{line('cash_return_bdt')}{line('advance_balance_bdt', true)}</div></div><div className="ledger-foot"><span><strong>Delivery proof:</strong> {settlement.delivery_confirmed ? 'Confirmed by reviewed record' : 'Not confirmed'}</span><span>Statements and excluded records do not change money.</span></div></section>;
}

function BlockingIssues({ detail }: { detail: TripDetail }) {
  return <section className="issues-panel" aria-labelledby="issues-heading"><div className="section-header"><div><span className="eyebrow">THE CLOSURE GATE</span><h2 id="issues-heading">Evidence issues <span className="count">{detail.settlement.issues.length}</span></h2></div><Badge value={detail.settlement.can_settle ? 'confirmed' : 'blocking'}>{detail.settlement.can_settle ? 'Validator eligible' : 'Closure blocked'}</Badge></div>
    {!detail.settlement.issues.length ? <p>No evidence issues reported by the independent validator. A current completed investigation is still required to close.</p> : <ul className="issue-list">{detail.settlement.issues.map((issue, index) => <li key={`${issue.code}-${index}`}><span className={`issue-marker issue-${issue.severity}`} aria-hidden="true">{issue.severity === 'blocking' ? '!' : 'i'}</span><div><div className="issue-title"><strong>{issue.title}</strong><Badge value={issue.severity} /></div><p>{issue.detail}</p><div className="issue-ref"><code>{issue.code}</code><Sources ids={issue.evidence_ids} /></div></div></li>)}</ul>}
  </section>;
}

function InvestigationSection({ detail, status, busy, mutate }: { detail: TripDetail; status: ProviderStatus | null; busy: boolean; mutate: Mutation }) {
  const [reply, setReply] = useState('');
  const current = latestRun(detail);
  const settled = detail.trip.status === 'settled';
  return <section id="investigation" className="desk-section" aria-labelledby="investigation-heading"><div className="section-header"><div><span className="eyebrow">02 / Read, ask, reassess</span><h2 id="investigation-heading">Investigation</h2></div><button className="primary" disabled={busy || settled || !status} onClick={() => mutate((signal) => api.investigate(detail.trip.id, signal), 'Investigation saved. Review the persisted run, evidence citations and proposed follow-ups.')}>{busy ? 'Working...' : current?.status === 'failed' ? 'Retry investigation' : 'Investigate trip'}</button></div>
    <div className="mode-disclosure"><strong>{status ? status.mode === 'model' ? `Bounded model${status.model_name ? ` / ${status.model_name}` : ''}` : 'Deterministic review demonstration' : 'Provider mode unavailable'}</strong><p>{status ? status.mode === 'model' ? 'The configured model can read evidence, ask questions and draft follow-ups. The independent validator, not the model, controls money and closure.' : 'No investigation model is configured. This is a labelled deterministic review, not a pretend AI agent.' : 'Refresh provider status before running an investigation. No AI activity is implied.'}</p></div>
    {!current ? <Empty title="No investigation has run"><p>Review the draft evidence, then investigate the account. Results, tools and questions will be persisted here.</p></Empty> : <>
      {current.question && <section className="question-ticket" aria-labelledby="question-heading"><span className="eyebrow">NEXT EVIDENCE NEEDED / RUN R{current.id}</span><h3 id="question-heading">{current.question}</h3><p><strong>Recipient:</strong> {current.recipient || 'Not specified by the run'}</p><Sources ids={current.evidence_ids} />{current.revision !== detail.trip.revision && <p className="risk-text">This question belongs to revision {current.revision}. Re-investigate the changed evidence.</p>}
        <form onSubmit={(event) => { event.preventDefault(); if (reply.trim()) mutate((signal) => api.reply(detail.trip.id, reply.trim(), signal), 'Reply saved as a confirmed statement, not a transaction. Investigate again to reassess.', () => setReply('')); }}><label>Reply text<textarea rows={4} name="reply" required value={reply} disabled={busy || settled} onChange={(event) => setReply(event.target.value)} placeholder="Record the actual customer or driver response" /></label><p className="muted">This records a statement only. A promise cannot change received money or trip identifiers.</p><button type="submit" disabled={busy || settled || !reply.trim()}>{busy ? 'Saving statement...' : 'Record reply as statement'}</button></form>
      </section>}
      <div className="run-list">{[...detail.investigations].sort((a, b) => b.id - a.id).map((run) => <article className={`run-ticket run-${run.status}`} key={run.id}><header><div><span className="eyebrow">RUN R{run.id} / REVISION {run.revision}</span><h3>{run.mode === 'demo' ? 'Deterministic demo review' : 'Bounded model investigation'}</h3></div><Badge value={run.status} /></header><div className="run-meta"><time dateTime={run.created_at}>{dateTime(run.created_at)}</time>{run.revision !== detail.trip.revision && <span className="risk-text">Superseded by evidence revision {detail.trip.revision}</span>}</div><p className="record-text">{run.summary || 'No summary recorded.'}</p><Sources ids={run.evidence_ids} />
        {run.question && <p><strong>Question for {run.recipient || 'unspecified recipient'}:</strong> {run.question}</p>}
        {run.status === 'failed' && <p className="risk-text">This run failed. No successful demo fallback is claimed. Retry after checking the provider.</p>}
        <details><summary>Persisted tools and results ({run.steps.length})</summary>{run.steps.length ? <ol className="tool-list">{run.steps.map((step, index) => <li key={index}><strong>{index + 1}. {step.tool}</strong><h4>Arguments</h4><pre>{jsonText(step.args)}</pre><h4>Result</h4><pre>{jsonText(step.result)}</pre></li>)}</ol> : <p>No tool steps were recorded for this run.</p>}</details>
        <details><summary>Follow-ups linked to this revision</summary>{detail.actions.filter((action) => action.revision === run.revision).length ? detail.actions.filter((action) => action.revision === run.revision).map((action) => <p key={action.id}><a href={`#action-${action.id}`}>Draft F{action.id}</a> · {action.recipient} · {action.status} · <Sources ids={action.evidence_ids} /></p>) : <p>No follow-ups persisted for this revision.</p>}</details>
      </article>)}</div>
    </>}
  </section>;
}

function Followups({ detail, busy, mutate, download }: { detail: TripDetail; busy: boolean; mutate: Mutation; download: (action: Action) => void }) {
  return <section id="followups" className="desk-section" aria-labelledby="followups-heading"><div className="section-header"><div><span className="eyebrow">03 / Review before export</span><h2 id="followups-heading">Follow-ups <span className="count">{detail.actions.length}</span></h2></div><span className="draft-label">DRAFT ONLY / NEVER SENT</span></div><p>Approve the exact wording below for text export. Approval does not send a message, mark money received or close the trip.</p>
    {!detail.actions.length ? <Empty title="No follow-up drafts yet"><p>Run an investigation to identify the next useful question or draft.</p></Empty> : <div className="action-list">{[...detail.actions].sort((a, b) => b.id - a.id).map((action) => {
      const stale = action.status === 'stale' || action.revision !== detail.trip.revision;
      return <article className="action-ticket" id={`action-${action.id}`} key={action.id}><header><div><span className="eyebrow">DRAFT F{action.id} / REVISION {action.revision}</span><h3>To: {action.recipient}</h3></div><div className="action-badges"><Badge value={action.status}>{action.status === 'approved' ? 'Approved draft' : undefined}</Badge>{stale && action.status !== 'stale' && <Badge value="stale">Stale revision</Badge>}</div></header><p className="message-copy">{action.message}</p><div className="action-provenance"><Sources ids={action.evidence_ids} /><time dateTime={action.created_at}>{dateTime(action.created_at)}</time></div>
        {stale ? <p className="risk-text">Evidence has changed. This draft cannot be approved or exported; investigate the current revision.</p> : <div className="button-row">{action.status === 'pending' && <><button className="primary" disabled={busy} onClick={() => mutate((signal) => api.decide(action.id, 'approve', signal), `Draft F${action.id} approved for download only. No message has been sent.`)}>Approve draft</button><button disabled={busy} onClick={() => mutate((signal) => api.decide(action.id, 'reject', signal), `Draft F${action.id} rejected. No message has been sent.`)}>Reject draft</button></>}{action.status === 'approved' && <button className="secondary" disabled={busy} onClick={() => download(action)}>Download approved text</button>}{action.status === 'rejected' && <span className="muted">Rejected draft. No export or sending action is available.</span>}</div>}
      </article>;
    })}</div>}
  </section>;
}

export default function TripDesk({ id, status }: { id: string; status: ProviderStatus | null }) {
  const resource = useResource((signal) => api.trip(id, signal), `trip-${id}`);
  const task = useTask();
  const detail = resource.data;
  const [closeChecked, setCloseChecked] = useState(false);
  const reportUrls = useRef<string[]>([]);
  const pendingReport = useRef<Window | null>(null);
  useEffect(() => () => { pendingReport.current?.close(); reportUrls.current.forEach((url) => URL.revokeObjectURL(url)); }, []);
  const latestRunId = detail ? latestRun(detail)?.id : undefined;
  useEffect(() => { setCloseChecked(false); }, [detail?.trip.revision, latestRunId]);
  useEffect(() => {
    if (!detail || !window.location.hash) return;
    // Wait until the evidence packet is mounted for deep evidence links.
    const frame = requestAnimationFrame(() => document.getElementById(window.location.hash.slice(1))?.scrollIntoView({ block: 'start' }));
    return () => cancelAnimationFrame(frame);
  }, [detail]);
  const mutate: Mutation = (work, notice, after) => {
    void task.run(work, (next) => { resource.replace(next); task.setNotice(notice); after?.(); }, async (error, signal) => {
      if (error instanceof ApiError && (error.status === 502 || error.status === 409)) {
        setCloseChecked(false);
        const next = await api.trip(id, signal);
        if (!signal.aborted) resource.replace(next);
      }
    });
  };
  function exportReport() {
    if (!detail || task.busy) return;
    // Open synchronously from the click so popup blockers do not swallow a later authenticated result.
    const tab = window.open('about:blank', '_blank');
    if (!tab) { task.setError('The printable report needs a new tab. Allow popups for this workspace and retry.'); return; }
    pendingReport.current = tab;
    tab.opener = null;
    tab.document.title = 'Preparing HisabGuard report';
    tab.document.body.textContent = 'Fetching the authenticated evidence packet...';
    void task.run((signal) => api.report(detail.trip.id, signal), (blob) => {
      const url = URL.createObjectURL(new Blob([blob], { type: 'text/html' }));
      reportUrls.current.push(url);
      tab.location.replace(url);
      pendingReport.current = null;
      task.setNotice('Printable report opened. Use the browser print command in the report tab.');
    }, () => { tab.close(); pendingReport.current = null; });
  }
  return <>
    <Link className="back-link" href="/">← Back to trip settlements</Link>
    <PageHeader eyebrow="01 / Trip settlement desk" title={detail ? detail.trip.code : 'Trip settlement'} actions={detail && <><button disabled={task.busy} onClick={exportReport}>Printable report</button><button disabled={task.busy} onClick={() => void task.run(api.backup, (blob) => { downloadBlob(blob, 'hisabguard-backup.json'); task.setNotice('JSON backup downloaded. Original binary files are excluded.'); })}>JSON backup</button><button disabled={task.busy || resource.loading} onClick={resource.reload}>Refresh trip</button></>}>
      {detail ? <><div className="trip-heading-meta"><Badge value={detail.trip.status} /><span>Revision {detail.trip.revision}</span><span>{detail.trip.customer}</span></div><p>{detail.trip.truck} · {detail.trip.driver} · {detail.trip.origin || 'Origin not recorded'} → {detail.trip.destination || 'Destination not recorded'}</p></> : <p>The evidence packet and independent money ledger.</p>}
    </PageHeader>
    {resource.loading && <Loading text="Loading trip evidence and settlement..." />}<ErrorBox message={resource.error} retry={resource.reload} />
    <div className="task-feedback" aria-live="polite"><ErrorBox message={task.error} />{task.notice && <Notice>{task.notice}</Notice>}{task.busy && <Loading text="Saving or fetching the requested record. Please wait..." />}</div>
    {detail && <>
      <MoneyLedger detail={detail} />
      <BlockingIssues detail={detail} />
      <nav className="desk-tabs" aria-label="Trip desk sections"><a href="#evidence">Evidence <span>{detail.evidence.length}</span></a><a href="#investigation">Investigation <span>{detail.investigations.length}</span></a><a href="#followups">Follow-ups <span>{detail.actions.length}</span></a><a href="#trip-activity">Activity <span>{detail.audit.length}</span></a></nav>
      <div className="desk-body"><EvidenceSection detail={detail} busy={task.busy} mutate={mutate} uploadsEnabled={status?.uploads_enabled !== false} /><InvestigationSection detail={detail} status={status} busy={task.busy} mutate={mutate} /><Followups detail={detail} busy={task.busy} mutate={mutate} download={(action) => void task.run((signal) => api.actionExport(action.id, signal), (blob) => { downloadBlob(blob, `hisabguard-draft-${action.id}.txt`); task.setNotice(`Approved draft F${action.id} downloaded. It has not been sent.`); })} />
        <section className="closure-panel" aria-labelledby="closure-heading"><span className="eyebrow">INDEPENDENT VALIDATOR + OPERATOR DECISION</span><h2 id="closure-heading">Close settlement</h2>{detail.trip.status === 'settled' ? <><Badge value="settled" /><p>The settlement has been closed by the operator after validator approval. This is not an independent bank verification.</p></> : <>
          <p>Both accounts must reconcile, delivery must be confirmed and all blocking issues must be resolved. A completed investigation must match the current evidence revision.</p>
          {!canClose(detail) && <p className="risk-text">{!detail.settlement.can_settle ? 'Closure is blocked by the independent validator. Resolve the evidence issues above.' : 'The latest investigation is not completed at the current revision. Investigate this trip again before closure.'}</p>}
          <label className="check-label"><input type="checkbox" checked={closeChecked} disabled={task.busy || !canClose(detail)} onChange={(event) => setCloseChecked(event.target.checked)} />I have reviewed the evidence and independently computed balances, and approve closing this settlement.</label><button className="primary" disabled={task.busy || !canClose(detail) || !closeChecked} onClick={() => mutate((signal) => api.close(detail.trip.id, signal), 'Settlement closed after the independent validator and operator review gates passed.')}>Close settlement</button>
        </>}</section>
        <section id="trip-activity" className="desk-section" aria-labelledby="trip-activity-heading"><div className="section-header"><div><span className="eyebrow">04 / Persisted decision trail</span><h2 id="trip-activity-heading">Activity</h2></div><Link className="text-link" href="/activity">All trip activity</Link></div><AuditList records={detail.audit} /></section>
      </div>
    </>}
  </>;
}

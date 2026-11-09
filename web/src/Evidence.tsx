import { useEffect, useState } from 'react';
import { api, downloadBlob } from './api';
import { Badge, Empty, ErrorBox, Loading } from './components';
import { useResource } from './hooks';
import { dateTime, decimalInput, label, money } from './utils';
import { evidenceKinds } from './types';
import type { Evidence, EvidenceFields, EvidenceKind, TripDetail } from './types';

export type Mutation = (work: (signal: AbortSignal) => Promise<TripDetail>, notice: string, after?: () => void) => void;
interface FieldDraft {
  kind: EvidenceKind; amount_bdt: string; transaction_id: string; trip_ref: string;
  note: string; text: string; delivered: '' | 'yes' | 'no';
}
const blankFields: FieldDraft = { kind: 'invoice', amount_bdt: '', transaction_id: '', trip_ref: '', note: '', text: '', delivered: '' };
function draftOf(evidence: Evidence): FieldDraft {
  return { kind: evidence.kind, amount_bdt: evidence.amount_bdt ?? '', transaction_id: evidence.transaction_id ?? '', trip_ref: evidence.trip_ref ?? '', note: evidence.note ?? '', text: evidence.text ?? '', delivered: evidence.delivered === null ? '' : evidence.delivered ? 'yes' : 'no' };
}
function reviewFields(fields: FieldDraft): EvidenceFields {
  return { kind: fields.kind, amount_bdt: decimalInput(fields.amount_bdt), transaction_id: fields.transaction_id.trim() || null, trip_ref: fields.trip_ref.trim() || null, note: fields.note.trim() || null, text: fields.text.trim() || null, delivered: fields.delivered === '' ? null : fields.delivered === 'yes' };
}
function ScalarEditor({ fields, setFields, lockedStatement = false }: { fields: FieldDraft; setFields: (fields: FieldDraft) => void; lockedStatement?: boolean }) {
  return <div className="field-grid">
    <label>Evidence kind<select name="kind" value={fields.kind} disabled={lockedStatement} onChange={(event) => setFields({ ...fields, kind: event.target.value as EvidenceKind })}>{evidenceKinds.map((kind) => <option key={kind} value={kind}>{label(kind)}</option>)}</select>{lockedStatement && <small>Statement kind is locked. A promise cannot become a payment.</small>}</label>
    <label>Amount (BDT)<input name="amount_bdt" type="text" inputMode="decimal" placeholder="e.g. 3500.00" value={fields.amount_bdt} onChange={(event) => setFields({ ...fields, amount_bdt: event.target.value })} /><small>Optional decimal amount; never a computed balance.</small></label>
    <label>Transaction ID<input name="transaction_id" value={fields.transaction_id} onChange={(event) => setFields({ ...fields, transaction_id: event.target.value })} /><small>Use the original identifier, not an invented reference.</small></label>
    <label>Trip reference<input name="trip_ref" value={fields.trip_ref} onChange={(event) => setFields({ ...fields, trip_ref: event.target.value })} /></label>
    <label>Delivery confirmation<select name="delivered" value={fields.delivered} onChange={(event) => setFields({ ...fields, delivered: event.target.value as FieldDraft['delivered'] })}><option value="">Not recorded</option><option value="yes">Delivery confirmed by this record</option><option value="no">Delivery not confirmed</option></select><small>Review the signed challan or actual delivery proof.</small></label>
    <label>Operator note<textarea name="note" rows={3} value={fields.note} onChange={(event) => setFields({ ...fields, note: event.target.value })} /></label>
    <label className="full-width">Record text / transcript<textarea name="text" rows={4} value={fields.text} onChange={(event) => setFields({ ...fields, text: event.target.value })} /><small>{fields.kind === 'statement' ? 'This remains a statement. It does not mark money received.' : 'Preserve relevant original wording. Do not replace proof with a conclusion.'}</small></label>
  </div>;
}

function OriginalPreview({ evidence }: { evidence: Evidence }) {
  const resource = useResource((signal) => api.file(evidence.id, signal), `original-${evidence.id}`);
  const [url, setUrl] = useState<string | null>(null);
  const [mediaError, setMediaError] = useState(false);
  useEffect(() => {
    if (!resource.data) return;
    const next = URL.createObjectURL(resource.data);
    setUrl(next); setMediaError(false);
    return () => URL.revokeObjectURL(next);
  }, [resource.data]);
  const mime = resource.data?.type || evidence.mime || '';
  return <div className="original-preview"><div className="original-heading"><strong>Original file · E{evidence.id}</strong><span>{evidence.filename}</span></div>
    {resource.loading && <Loading text="Fetching private original..." />}<ErrorBox message={resource.error} retry={resource.reload} />
    {resource.data && url && <>
      {!mediaError && mime.startsWith('image/') ? <img src={url} alt={`Original evidence E${evidence.id}: ${evidence.title}`} loading="lazy" onError={() => setMediaError(true)} />
        : !mediaError && (mime.startsWith('audio/') || evidence.source_type === 'audio') ? <audio controls src={url} aria-label={`Original audio for evidence E${evidence.id}`} onError={() => setMediaError(true)}>Your browser cannot play this audio.</audio>
          : <p>Inline preview is unavailable for this format. Download the original to review it.</p>}
      <button type="button" onClick={() => downloadBlob(resource.data!, evidence.filename || `evidence-${evidence.id}`)}>Download original</button>
    </>}
  </div>;
}

function EvidenceTicket({ evidence, busy, settled, mutate }: { evidence: Evidence; busy: boolean; settled: boolean; mutate: Mutation }) {
  const [editing, setEditing] = useState(false);
  const [preview, setPreview] = useState(false);
  const [fields, setFields] = useState(() => draftOf(evidence));
  const [checked, setChecked] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { setFields(draftOf(evidence)); setChecked(false); }, [evidence]);
  function confirm() {
    try {
      const reviewed = reviewFields(fields);
      setError(null);
      mutate((signal) => api.review(evidence.id, 'confirm', reviewed, signal), `E${evidence.id} confirmed by the operator. This is not independent bank verification.`, () => setEditing(false));
    } catch (error) { setError(error instanceof Error ? error.message : 'Check the evidence fields.'); }
  }
  return <article className={`evidence-ticket evidence-${evidence.state}`} id={`evidence-${evidence.id}`} aria-labelledby={`evidence-title-${evidence.id}`}>
    <header className="ticket-header"><span className="ticket-id">E{evidence.id}</span><div><div className="ticket-title"><h3 id={`evidence-title-${evidence.id}`}>{evidence.title}</h3><Badge value={evidence.state} /></div><span className="muted">{label(evidence.kind)} · {evidence.source_type === 'manual' ? 'Typed operator record' : evidence.source_type === 'image' ? 'Image original / extraction proposal' : 'Audio original / transcript proposal'} · {dateTime(evidence.created_at)}</span></div></header>
    <div className="ticket-body">
      <div className="ticket-facts"><div><span>Recorded amount</span><strong className="amount">{money(evidence.amount_bdt)}</strong></div><div><span>Transaction ID</span><strong>{evidence.transaction_id || 'Not recorded'}</strong></div><div><span>Trip reference</span><strong>{evidence.trip_ref || 'Not recorded'}</strong></div><div><span>Delivery field</span><strong>{evidence.delivered === null ? 'Not recorded' : evidence.delivered ? 'Confirmed by record' : 'Not confirmed'}</strong></div></div>
      <div className="ticket-boundary">{evidence.state === 'draft' ? 'Draft only. Not included in settlement arithmetic until operator confirmation.' : evidence.state === 'excluded' ? 'Excluded from settlement totals. The original and audit history are retained.' : evidence.kind === 'statement' ? 'Confirmed statement, not a payment. No money is marked received.' : 'Operator-confirmed record. Not independently bank-verified.'}{evidence.synthetic && <span> Synthetic record.</span>}</div>
      {(evidence.note || evidence.text) && <div className="record-copy">{evidence.note && <div><strong>Operator note</strong><p>{evidence.note}</p></div>}{evidence.text && <div><strong>{evidence.source_type === 'audio' ? 'Transcript / reviewed text' : 'Record text'}</strong><p>{evidence.text}</p></div>}</div>}
      <details className="confidence-details"><summary>{evidence.source_type === 'manual' ? 'Source and field confidence' : 'Provider-proposed field confidence'}</summary><p>Confidence is an extraction hint, not evidence authenticity or bank verification. Original fields are visible above; corrections happen in operator review.</p>{Object.keys(evidence.confidence).length ? <dl className="confidence-list">{Object.entries(evidence.confidence).map(([field, value]) => <div key={field}><dt>{label(field)}</dt><dd>{Math.round(value * 100)}%</dd></div>)}</dl> : <p>No provider confidence values were recorded.</p>}<p>Source: {evidence.source_type}. File: {evidence.filename || 'No original binary; explicitly typed record'}.</p></details>
      {evidence.extraction_error && <div className="feedback feedback-error"><div><strong>Manual review required</strong><p>{evidence.extraction_error}</p><p>The original is retained. Open it, correct the fields, then explicitly confirm or exclude this record. No successful extraction is implied.</p></div></div>}
      <div className="button-row">{evidence.filename && <button type="button" aria-expanded={preview} onClick={() => setPreview(!preview)}>{preview ? 'Hide original' : 'View original'}</button>}<button type="button" className={evidence.state === 'draft' ? 'secondary' : ''} disabled={busy || settled} aria-expanded={editing} onClick={() => { setEditing(!editing); setError(null); }}>{editing ? 'Cancel review' : evidence.state === 'draft' ? 'Review evidence' : 'Review / correct record'}</button></div>
      {preview && <OriginalPreview evidence={evidence} />}
      {editing && <form className="review-editor" onSubmit={(event) => { event.preventDefault(); if (checked) confirm(); }}>
        <div className="review-heading"><h3>Operator review · E{evidence.id}</h3><p>Check every scalar field against the original. Confirmation is your review decision, not bank verification.</p></div>
        <fieldset disabled={busy || settled}><ScalarEditor fields={fields} setFields={setFields} lockedStatement={evidence.kind === 'statement'} /><label className="check-label review-check"><input type="checkbox" checked={checked} onChange={(event) => setChecked(event.target.checked)} />I have checked the kind, amount, transaction ID, trip reference, delivery field, note and text against the available record.</label></fieldset>
        <ErrorBox message={error} />
        <div className="button-row"><button className="primary" type="submit" disabled={busy || settled || !checked}>{busy ? 'Saving review...' : 'Confirm evidence'}</button><button type="button" disabled={busy || settled} onClick={() => mutate((signal) => api.review(evidence.id, 'exclude', reviewFields(draftOf(evidence)), signal), `E${evidence.id} excluded. Original evidence and audit history remain.`, () => setEditing(false))}>Exclude evidence</button></div>
      </form>}
    </div>
  </article>;
}

function EvidenceIntake({ tripId, busy, mutate, close, uploadsEnabled }: { tripId: number; busy: boolean; mutate: Mutation; close: () => void; uploadsEnabled: boolean }) {
  const [mode, setMode] = useState<'typed' | 'upload'>('typed');
  const [fields, setFields] = useState<FieldDraft>({ ...blankFields });
  const [title, setTitle] = useState('');
  const [hint, setHint] = useState<EvidenceKind>('invoice');
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  function submit() {
    setError(null);
    if (!title.trim()) { setError('Enter an evidence title.'); return; }
    if (mode === 'typed') {
      try {
        const payload = { ...reviewFields(fields), title: title.trim() };
        mutate((signal) => api.addEvidence(tripId, payload, signal), 'Typed operator record added as draft. Review it before it affects settlement.', close);
      } catch (error) { setError(error instanceof Error ? error.message : 'Check the record fields.'); }
    } else {
      if (!file) { setError('Choose an image or audio original.'); return; }
      if (!file.type.startsWith('image/') && !file.type.startsWith('audio/')) { setError('Only image or audio originals are accepted.'); return; }
      if (file.size > 10 * 1024 * 1024) { setError('The original must be no larger than 10 MB.'); return; }
      const data = new FormData();
      data.set('file', file); data.set('title', title.trim()); data.set('kind_hint', hint);
      mutate((signal) => api.upload(tripId, data, signal), 'Original stored. Inspect the draft and any extraction error; manual review may be required.', close);
    }
  }
  return <section className="evidence-intake" aria-labelledby="add-evidence-heading"><div className="section-header"><div><span className="eyebrow">NEW RECORD</span><h3 id="add-evidence-heading">Add evidence</h3></div><button type="button" onClick={close} disabled={busy}>Cancel</button></div>
    <div className="segmented" role="group" aria-label="Evidence input method"><button className={mode === 'typed' ? 'selected' : ''} aria-pressed={mode === 'typed'} disabled={busy} onClick={() => { setMode('typed'); setError(null); }}>Typed operator record</button><button className={mode === 'upload' ? 'selected' : ''} aria-pressed={mode === 'upload'} disabled={busy || !uploadsEnabled} onClick={() => { setMode('upload'); setError(null); }}>Upload image / audio</button></div>
    {!uploadsEnabled && <p className="risk-text">Judge-demo scope: use synthetic typed records and statements only. Original previews work, but uploads and unverified OCR/audio processing are disabled.</p>}
    <p>{mode === 'typed' ? 'Explicitly labelled operator record. This is not an imported transaction and starts as draft.' : 'Upload the original (maximum 10 MB). Extraction and transcription proposals stay draft; failures remain visible for manual review.'}</p>
    <form onSubmit={(event) => { event.preventDefault(); submit(); }}><fieldset disabled={busy}><label>Evidence title<input name="title" required value={title} onChange={(event) => setTitle(event.target.value)} /></label>
      {mode === 'typed' ? <ScalarEditor fields={fields} setFields={setFields} /> : <div className="field-grid"><label>Kind hint<select name="kind_hint" value={hint} onChange={(event) => setHint(event.target.value as EvidenceKind)}>{evidenceKinds.map((kind) => <option key={kind} value={kind}>{label(kind)}</option>)}</select><small>A hint, not a confirmed classification.</small></label><label>Original image or audio<input type="file" name="file" accept="image/*,audio/*" required onChange={(event) => setFile(event.target.files?.[0] ?? null)} /><small>Maximum 10 MB. A repeated identical original returns a duplicate error.</small></label></div>}
    </fieldset><ErrorBox message={error} /><button className="primary" type="submit" disabled={busy}>{busy ? 'Saving evidence...' : mode === 'typed' ? 'Add draft record' : 'Upload original'}</button></form>
  </section>;
}

export default function EvidenceSection({ detail, busy, mutate, uploadsEnabled = true }: { detail: TripDetail; busy: boolean; mutate: Mutation; uploadsEnabled?: boolean }) {
  const [adding, setAdding] = useState(false);
  const [filter, setFilter] = useState('all');
  useEffect(() => {
    let frame = 0;
    const reveal = (event: Event) => {
      const evidenceId: unknown = (event as CustomEvent<unknown>).detail;
      if (typeof evidenceId !== 'number') return;
      setFilter('all');
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => document.getElementById(`evidence-${evidenceId}`)?.scrollIntoView({ block: 'start' }));
    };
    window.addEventListener('hisabguard:show-evidence', reveal);
    return () => { window.removeEventListener('hisabguard:show-evidence', reveal); cancelAnimationFrame(frame); };
  }, []);
  const evidence = detail.evidence.filter((item) => filter === 'all' || item.state === filter).sort((a, b) => a.id - b.id);
  const settled = detail.trip.status === 'settled';
  return <section id="evidence" className="desk-section" aria-labelledby="evidence-heading">
    <div className="section-header"><div><span className="eyebrow">01 / Original → proposal → review</span><h2 id="evidence-heading">Evidence <span className="count">{detail.evidence.length}</span></h2></div><button className="secondary" type="button" disabled={busy || settled} aria-expanded={adding} onClick={() => setAdding(!adding)}>Add evidence</button></div>
    {adding && <EvidenceIntake tripId={detail.trip.id} busy={busy} mutate={mutate} close={() => setAdding(false)} uploadsEnabled={uploadsEnabled} />}
    <div className="evidence-filters"><label>Evidence state<select value={filter} onChange={(event) => setFilter(event.target.value)}><option value="all">All evidence</option><option value="draft">Draft</option><option value="confirmed">Confirmed</option><option value="excluded">Excluded</option></select></label><p>Only confirmed financial records enter the independent ledger. Statements never count as receipt.</p></div>
    {!evidence.length ? <Empty title={detail.evidence.length ? 'No evidence in this state' : 'The evidence packet is empty'}><p>{detail.evidence.length ? 'Choose All evidence to see the complete packet.' : 'Add the invoice, signed challan, payment record and advance accounting to begin.'}</p>{detail.evidence.length > 0 && <button onClick={() => setFilter('all')}>Show all evidence</button>}</Empty> : <div className="evidence-list">{evidence.map((item) => <EvidenceTicket key={item.id} evidence={item} busy={busy} settled={settled} mutate={mutate} />)}</div>}
  </section>;
}

import { useState } from 'react';
import { api, downloadBlob } from './api';
import { AuditList, Badge, ErrorBox, Loading, Notice, PageHeader } from './components';
import { useResource, useTask } from './hooks';
import { Link, navigate } from './navigation';
import type { NewTrip } from './types';

export function NewTripPage() {
  const task = useTask();
  const [fields, setFields] = useState<NewTrip>({ code: '', customer: '', driver: '', truck: '', origin: '', destination: '' });
  return <>
    <Link className="back-link" href="/">← Back to trip settlements</Link>
    <PageHeader eyebrow="01 / New settlement packet" title="New trip"><p>Start with the people and route. Evidence is added after the trip is created.</p></PageHeader>
    <div className="intake-layout"><section className="paper-panel">
      <div className="panel-heading"><span className="eyebrow">TRIP DETAILS</span><h2>Open a trip record</h2></div>
      <form className="form-grid" onSubmit={(event) => { event.preventDefault(); void task.run((signal) => api.newTrip(Object.fromEntries(Object.entries(fields).map(([key, value]) => [key, value.trim()])) as unknown as NewTrip, signal), (detail) => navigate(`/trips/${encodeURIComponent(String(detail.trip.id))}`)); }}>
        <fieldset disabled={task.busy}><div className="field-grid">
          <label>Trip code <span className="optional">Optional</span><input name="code" value={fields.code} onChange={(event) => setFields({ ...fields, code: event.target.value })} /><small>Leave blank to use the server-assigned code.</small></label>
          <label>Truck<input name="truck" required value={fields.truck} onChange={(event) => setFields({ ...fields, truck: event.target.value })} /></label>
          <label>Customer<input name="customer" required value={fields.customer} onChange={(event) => setFields({ ...fields, customer: event.target.value })} /></label>
          <label>Driver<input name="driver" required value={fields.driver} onChange={(event) => setFields({ ...fields, driver: event.target.value })} /></label>
          <label>Origin <span className="optional">Optional</span><input name="origin" value={fields.origin} onChange={(event) => setFields({ ...fields, origin: event.target.value })} /></label>
          <label>Destination <span className="optional">Optional</span><input name="destination" value={fields.destination} onChange={(event) => setFields({ ...fields, destination: event.target.value })} /></label>
        </div></fieldset>
        <ErrorBox message={task.error} />
        <div className="form-footer"><button className="primary" type="submit" disabled={task.busy}>{task.busy ? 'Creating trip...' : 'Create trip'}</button><Link className="button" href="/">Cancel</Link></div>
      </form>
    </section><aside className="intake-note"><span className="eyebrow">NEXT AT THE DESK</span><h2>Build the account from proof.</h2><ol><li>Add invoice and delivery evidence.</li><li>Record received payments, expenses and advances.</li><li>Review each draft before it affects money.</li><li>Investigate gaps and approve a follow-up draft.</li></ol><p>A typed record is an operator's record, not an imported bank transaction.</p></aside></div>
  </>;
}

export function ActivityPage() {
  const resource = useResource(api.activity, 'global-activity');
  return <>
    <PageHeader eyebrow="02 / Audit register" title="Activity" actions={<button onClick={resource.reload} disabled={resource.loading}>Refresh activity</button>}><p>Persisted operator decisions and investigation events. Nothing here implies a message was sent.</p></PageHeader>
    {resource.loading && <Loading text="Loading activity register..." />}<ErrorBox message={resource.error} retry={resource.reload} />
    {resource.data && <section className="paper-panel"><div className="panel-heading"><h2>All trip activity</h2><span className="muted">{resource.data.activity.length} recorded events</span></div><AuditList records={resource.data.activity} global /></section>}
  </>;
}

export function SettingsPage() {
  const resource = useResource(api.status, 'settings-status');
  const task = useTask();
  const status = resource.data;
  return <>
    <PageHeader eyebrow="03 / Workspace configuration" title="Settings" actions={<button onClick={resource.reload} disabled={resource.loading}>Refresh provider status</button>}><p>Capabilities reported by the backend. Configure providers on the server, not in this browser.</p></PageHeader>
    {resource.loading && <Loading text="Checking provider capabilities..." />}<ErrorBox message={resource.error} retry={resource.reload} />
    {status && <>
      <section className="paper-panel"><div className="panel-heading"><h2>Provider and access status</h2><Badge value={status.mode}>{status.mode === 'model' ? 'Bounded model mode' : 'Deterministic demo mode'}</Badge></div>
        <dl className="settings-list"><div><dt>Investigation model</dt><dd>{status.model_configured ? status.model_name || 'Configured model (name not reported)' : 'Not configured; deterministic review demonstration'}</dd></div><div><dt>Image extraction</dt><dd>{status.vision_configured ? 'Configured; proposals still require review' : 'Not configured; originals can be reviewed manually'}</dd></div><div><dt>Audio transcription</dt><dd>{status.stt_configured ? 'Configured; transcript proposals still require review' : 'Not configured; originals can be reviewed manually'}</dd></div><div><dt>API authentication</dt><dd>{status.auth_required ? 'Access token required' : 'Optional for loopback development; public hosting requires a token'}</dd></div><div><dt>External delivery</dt><dd>Draft only. Approving a message does not send it.</dd></div><div><dt>Dataset disclosure</dt><dd>Synthetic demonstration, not validated customer data.</dd></div></dl>
      </section>
      <section className="paper-panel"><div className="panel-heading"><h2>Server environment names</h2></div><p>No secret values are exposed. An administrator sets these variables on the server.</p><div className="env-columns"><div><h3>Reasoning and vision</h3><ul className="env-list">{['HISABGUARD_LLM_BASE_URL', 'HISABGUARD_LLM_API_KEY', 'HISABGUARD_LLM_MODEL', 'HISABGUARD_VISION_MODEL'].map((name) => <li key={name}><code>{name}</code></li>)}</ul></div><div><h3>Speech to text</h3><ul className="env-list">{['HISABGUARD_STT_BASE_URL', 'HISABGUARD_STT_API_KEY', 'HISABGUARD_STT_MODEL'].map((name) => <li key={name}><code>{name}</code></li>)}</ul></div><div><h3>Workspace access</h3><code>HISABGUARD_ACCESS_TOKEN</code><p>Use Access in the top bar to enter the operator token. Provider keys must never be entered there.</p></div></div></section>
    </>}
    <section className="paper-panel"><div className="panel-heading"><h2>Backup the register</h2></div><p>Download the real versioned JSON export. Original binary files and secrets are not included; retain originals separately.</p><ErrorBox message={task.error} />{task.notice && <Notice>{task.notice}</Notice>}<button disabled={task.busy} onClick={() => void task.run(api.backup, (blob) => { downloadBlob(blob, 'hisabguard-backup.json'); task.setNotice('JSON backup downloaded. Original binary files are not included.'); })}>{task.busy ? 'Preparing backup...' : 'Download JSON backup'}</button></section>
  </>;
}

export function NotFoundPage() {
  return <><PageHeader eyebrow="Unknown route" title="This page is not in the register"><p>The link may be incomplete. Your trip records are available from the settlement queue.</p></PageHeader><Link className="button primary" href="/">Back to trip settlements</Link></>;
}

import { evidenceKinds, moneyColumns, tripStatuses } from './types.ts';
import type { Action, Audit, Evidence, EvidenceFields, Investigation, NewEvidence, NewTrip, ProviderStatus, QueueData, Settlement, Trip, TripDetail, TripSummary } from './types.ts';
import { errorDetail } from './utils.ts';

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) { super(message); this.name = 'ApiError'; this.status = status; }
}

let accessToken = '';
try { accessToken = sessionStorage.getItem('hisabguard-access-token') ?? ''; } catch { /* Session storage may be unavailable in private contexts. */ }
export function setAccessToken(token: string, remember: boolean) {
  accessToken = token.trim();
  try {
    if (remember && accessToken) sessionStorage.setItem('hisabguard-access-token', accessToken);
    else sessionStorage.removeItem('hisabguard-access-token');
  } catch { /* The token still works in memory for this page. */ }
}

function record(value: unknown): value is Record<string, unknown> { return !!value && typeof value === 'object' && !Array.isArray(value); }
function text(value: unknown): value is string { return typeof value === 'string'; }
function nullableText(value: unknown) { return value === null || text(value); }
function id(value: unknown): value is number { return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0; }
function ids(value: unknown): value is number[] { return Array.isArray(value) && value.every(id); }
function amount(value: unknown): value is string { return text(value) && /^-?\d+\.\d{2}$/.test(value); }
function list<T>(value: unknown, guard: (entry: unknown) => entry is T): value is T[] { return Array.isArray(value) && value.every(guard); }
function isTrip(value: unknown): value is Trip {
  return record(value) && id(value.id) && id(value.revision) && ['code', 'customer', 'driver', 'truck', 'created_at'].every((key) => text(value[key])) && nullableText(value.origin) && nullableText(value.destination) && tripStatuses.some((status) => status === value.status);
}
function isEvidence(value: unknown): value is Evidence {
  return record(value) && id(value.id) && id(value.trip_id) && text(value.title) && text(value.created_at) && evidenceKinds.some((kind) => kind === value.kind)
    && ['draft', 'confirmed', 'excluded'].includes(String(value.state)) && ['manual', 'image', 'audio'].includes(String(value.source_type))
    && (value.amount_bdt === null || amount(value.amount_bdt)) && ['transaction_id', 'trip_ref', 'note', 'text', 'filename', 'mime', 'extraction_error'].every((key) => nullableText(value[key]))
    && (value.delivered === null || typeof value.delivered === 'boolean') && typeof value.synthetic === 'boolean'
    && record(value.confidence) && Object.values(value.confidence).every((entry) => typeof entry === 'number' && Number.isFinite(entry) && entry >= 0 && entry <= 1);
}
function isSettlement(value: unknown): value is Settlement {
  return record(value) && moneyColumns.every((key) => amount(value[key])) && typeof value.delivery_confirmed === 'boolean' && typeof value.can_settle === 'boolean'
    && record(value.sources) && Object.values(value.sources).every(ids) && Array.isArray(value.issues)
    && value.issues.every((issue: unknown) => record(issue) && text(issue.code) && text(issue.title) && text(issue.detail) && ['blocking', 'warning'].includes(String(issue.severity)) && ids(issue.evidence_ids));
}
function isRun(value: unknown): value is Investigation {
  return record(value) && id(value.id) && id(value.trip_id) && id(value.revision) && ['model', 'demo'].includes(String(value.mode))
    && ['investigating', 'completed', 'failed', 'awaiting_response'].includes(String(value.status)) && text(value.summary) && text(value.created_at)
    && nullableText(value.question) && nullableText(value.recipient) && ids(value.evidence_ids) && Array.isArray(value.steps)
    && value.steps.every((step: unknown) => record(step) && text(step.tool) && 'args' in step && 'result' in step);
}
function isAction(value: unknown): value is Action {
  return record(value) && id(value.id) && id(value.trip_id) && id(value.revision) && value.kind === 'followup' && text(value.recipient) && text(value.message)
    && ids(value.evidence_ids) && ['pending', 'approved', 'rejected', 'stale'].includes(String(value.status)) && text(value.created_at);
}
function isAudit(value: unknown): value is Audit {
  return record(value) && id(value.id) && (value.trip_id === null || id(value.trip_id)) && text(value.actor) && text(value.event) && record(value.detail) && text(value.created_at);
}
export function isTripDetail(value: unknown): value is TripDetail {
  return record(value) && isTrip(value.trip) && list(value.evidence, isEvidence) && isSettlement(value.settlement)
    && list(value.investigations, isRun) && list(value.actions, isAction) && list(value.audit, isAudit);
}
function isSummary(value: unknown): value is TripSummary {
  return isTrip(value) && record(value) && ['invoice_bdt', 'received_bdt', 'outstanding_bdt', 'expense_bdt', 'advance_bdt', 'advance_balance_bdt'].every((key) => amount(value[key])) && id(value.evidence_count) && id(value.exceptions_count);
}
function isQueue(value: unknown): value is QueueData {
  return record(value) && list(value.trips, isSummary) && record(value.overview) && ['trips', 'exceptions', 'pending_approvals'].every((key) => id((value.overview as Record<string, unknown>)[key])) && amount(value.overview.outstanding_bdt);
}
function isStatus(value: unknown): value is ProviderStatus {
  return record(value) && ['model_configured', 'vision_configured', 'stt_configured', 'auth_required'].every((key) => typeof value[key] === 'boolean')
    && nullableText(value.model_name) && ['model', 'demo'].includes(String(value.mode)) && value.external_delivery === 'draft_only' && value.demo === true;
}
function isActivity(value: unknown): value is { activity: Audit[] } { return record(value) && list(value.activity, isAudit); }

async function response(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`);
  let result: Response;
  try { result = await fetch(`/api${path}`, { ...init, headers, credentials: 'same-origin', cache: 'no-store' }); }
  catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error;
    throw new ApiError('Cannot reach the settlement API. Check the connection and retry.', 0);
  }
  if (init.signal?.aborted) throw new DOMException('Request cancelled', 'AbortError');
  if (!result.ok) {
    let detail: unknown;
    try { const body: unknown = await result.json(); detail = record(body) ? body.detail : undefined; } catch { /* Never display a server HTML error page. */ }
    if (init.signal?.aborted) throw new DOMException('Request cancelled', 'AbortError');
    if (result.status === 401) window.dispatchEvent(new Event('hisabguard:unauthorized'));
    throw new ApiError(detail ? errorDetail(detail) : result.status === 401 ? 'An access token is required. Use the access panel to reconnect.' : `Request failed (${result.status}). Please retry.`, result.status);
  }
  return result;
}
async function json<T>(path: string, guard: (value: unknown) => value is T, init: RequestInit = {}): Promise<T> {
  const result = await response(path, init);
  let value: unknown;
  try { value = await result.json(); } catch { throw new ApiError('The API returned an unreadable response. Please retry.', result.status); }
  if (!guard(value)) throw new ApiError('The API response does not match the settlement contract. Please retry or check the backend version.', result.status);
  return value;
}
const enc = (value: string | number) => encodeURIComponent(String(value));
const post = (body?: unknown, signal?: AbortSignal): RequestInit => ({ method: 'POST', signal, ...(body === undefined ? {} : { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }) });

export const api = {
  status: (signal?: AbortSignal) => json('/status', isStatus, { signal }),
  trips: (signal?: AbortSignal) => json('/trips', isQueue, { signal }),
  resetDemo: (signal?: AbortSignal) => json('/demo/reset', isQueue, post(undefined, signal)),
  trip: (tripId: string | number, signal?: AbortSignal) => json(`/trips/${enc(tripId)}`, isTripDetail, { signal }),
  newTrip: (fields: NewTrip, signal?: AbortSignal) => json('/trips', isTripDetail, post(fields, signal)),
  addEvidence: (tripId: number, fields: NewEvidence, signal?: AbortSignal) => json(`/trips/${enc(tripId)}/evidence`, isTripDetail, post(fields, signal)),
  upload: (tripId: number, data: FormData, signal?: AbortSignal) => json(`/trips/${enc(tripId)}/upload`, isTripDetail, { method: 'POST', body: data, signal }),
  review: (evidenceId: number, decision: 'confirm' | 'exclude', fields: EvidenceFields, signal?: AbortSignal) => json(`/evidence/${enc(evidenceId)}/review`, isTripDetail, post({ decision, fields }, signal)),
  investigate: (tripId: number, signal?: AbortSignal) => json(`/trips/${enc(tripId)}/investigate`, isTripDetail, post(undefined, signal)),
  reply: (tripId: number, text: string, signal?: AbortSignal) => json(`/trips/${enc(tripId)}/reply`, isTripDetail, post({ text }, signal)),
  decide: (actionId: number, decision: 'approve' | 'reject', signal?: AbortSignal) => json(`/actions/${enc(actionId)}/decision`, isTripDetail, post({ decision }, signal)),
  close: (tripId: number, signal?: AbortSignal) => json(`/trips/${enc(tripId)}/close`, isTripDetail, post({ decision: 'approve_settlement' }, signal)),
  activity: (signal?: AbortSignal) => json('/activity', isActivity, { signal }),
  file: async (evidenceId: number, signal?: AbortSignal) => (await response(`/evidence/${enc(evidenceId)}/file`, { signal })).blob(),
  actionExport: async (actionId: number, signal?: AbortSignal) => (await response(`/actions/${enc(actionId)}/export`, { signal })).blob(),
  report: async (tripId: number, signal?: AbortSignal) => (await response(`/trips/${enc(tripId)}/report`, { signal })).blob(),
  backup: async (signal?: AbortSignal) => (await response('/export', { signal })).blob(),
};

export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url; anchor.download = filename; anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

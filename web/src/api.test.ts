import assert from 'node:assert/strict';
import { mock, test } from 'node:test';
import { api, ApiError, isTripDetail, setAccessToken } from './api.ts';

const queue = { trips: [], overview: { trips: 0, exceptions: 0, outstanding_bdt: '0.00', pending_approvals: 0 } };

test('requests send tokens in headers only and carry cancellation signals', async (context) => {
  context.after(() => { mock.restoreAll(); setAccessToken('', false); });
  const controller = new AbortController();
  setAccessToken('synthetic-test-token', false);
  mock.method(globalThis, 'fetch', async (url: string, init: RequestInit) => {
    assert.equal(url, '/api/trips');
    assert.equal(new Headers(init.headers).get('Authorization'), 'Bearer synthetic-test-token');
    assert.equal(init.signal, controller.signal);
    assert.equal(init.cache, 'no-store');
    return Response.json(queue);
  });
  assert.deepEqual(await api.trips(controller.signal), queue);
});

test('path ids are encoded rather than inserted into an API URL', async (context) => {
  context.after(() => mock.restoreAll());
  mock.method(globalThis, 'fetch', async (url: string) => {
    assert.equal(url, '/api/trips/12%20%2F%3F');
    return Response.json({ detail: 'Trip not found' }, { status: 404 });
  });
  await assert.rejects(api.trip('12 /?'), (error: unknown) => error instanceof ApiError && error.status === 404 && error.message === 'Trip not found');
});

test('upload conflicts retain the exact safe API detail', async (context) => {
  context.after(() => mock.restoreAll());
  mock.method(globalThis, 'fetch', async (_url: string, init: RequestInit) => {
    assert.equal(init.method, 'POST');
    assert.ok(init.body instanceof FormData);
    assert.equal(new Headers(init.headers).has('Content-Type'), false);
    return Response.json({ detail: 'This identical original already exists on this trip as E4.' }, { status: 409 });
  });
  await assert.rejects(api.upload(1, new FormData()), (error: unknown) => error instanceof ApiError && error.status === 409 && error.message === 'This identical original already exists on this trip as E4.');
});

test('invalid successful responses fail safely instead of rendering a broken route', async (context) => {
  context.after(() => mock.restoreAll());
  mock.method(globalThis, 'fetch', async () => Response.json({ trips: [{ amount_bdt: 25000 }], overview: {} }));
  await assert.rejects(api.trips(), /does not match the settlement contract/);
  assert.equal(isTripDetail({ trip: {}, evidence: [], settlement: {} }), false);
});

test('401 opens access recovery without exposing response HTML', async (context) => {
  const previous = Object.getOwnPropertyDescriptor(globalThis, 'window');
  const target = new EventTarget();
  Object.defineProperty(globalThis, 'window', { value: target, configurable: true });
  context.after(() => {
    mock.restoreAll();
    if (previous) Object.defineProperty(globalThis, 'window', previous);
    else Reflect.deleteProperty(globalThis, 'window');
  });
  let events = 0;
  target.addEventListener('hisabguard:unauthorized', () => events++);
  mock.method(globalThis, 'fetch', async () => new Response('<html>untrusted</html>', { status: 401 }));
  await assert.rejects(api.trips(), /access token is required/);
  assert.equal(events, 1);
});

test('obsolete responses are aborted before unauthorized events or state changes', async (context) => {
  context.after(() => mock.restoreAll());
  const controller = new AbortController();
  mock.method(globalThis, 'fetch', async () => {
    controller.abort();
    return Response.json({ detail: 'Old unauthorized response' }, { status: 401 });
  });
  await assert.rejects(api.trips(controller.signal), { name: 'AbortError' });
});

test('judge reset is an authenticated POST without secret query parameters', async (context) => {
  context.after(() => { mock.restoreAll(); setAccessToken('', false); });
  setAccessToken('synthetic-test-token', false);
  mock.method(globalThis, 'fetch', async (url: string, init: RequestInit) => {
    assert.equal(url, '/api/demo/reset');
    assert.equal(init.method, 'POST');
    assert.equal(new Headers(init.headers).get('Authorization'), 'Bearer synthetic-test-token');
    return Response.json(queue);
  });
  assert.deepEqual(await api.resetDemo(), queue);
});

test('active investigation snapshots remain valid during concurrent read-back', () => {
  const detail = { trip: { id: 1, code: 'TEST', customer: 'Synthetic', driver: 'Synthetic', truck: 'TEST', origin: '', destination: '', status: 'investigating', revision: 1, created_at: '' }, evidence: [],
    settlement: { invoice_bdt: '0.00', received_bdt: '0.00', outstanding_bdt: '0.00', expense_bdt: '0.00', advance_bdt: '0.00', cash_return_bdt: '0.00', advance_balance_bdt: '0.00', delivery_confirmed: false, can_settle: false, sources: {}, issues: [] },
    investigations: [{ id: 1, trip_id: 1, revision: 1, mode: 'model', status: 'investigating', summary: '', question: null, recipient: null, evidence_ids: [], steps: [], created_at: '' }], actions: [], audit: [] };
  assert.equal(isTripDetail(detail), true);
});

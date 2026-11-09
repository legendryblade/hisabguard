import assert from 'node:assert/strict';
import { test } from 'node:test';
import { canClose, decimalInput, errorDetail, latestRun, money } from './utils.ts';
import type { TripDetail } from './types.ts';

test('BDT formatting preserves exact paisa and very large decimal strings', () => {
  assert.equal(money('32000.00'), 'BDT 32,000.00');
  assert.equal(money('7000.01'), 'BDT 7,000.01');
  assert.equal(money('-1500.00'), 'BDT -1,500.00');
  assert.equal(money('900719925474099312345.09'), 'BDT 900,719,925,474,099,312,345.09');
  assert.equal(money(null), 'Not recorded');
  assert.equal(money('NaN'), 'Not recorded');
});

test('input normalization never uses floating-point financial arithmetic', () => {
  assert.equal(decimalInput(' 0003500.5 '), '3500.50');
  assert.equal(decimalInput('25000'), '25000.00');
  assert.equal(decimalInput('0.01'), '0.01');
  assert.equal(decimalInput(''), null);
  for (const value of ['1.001', '-1', 'NaN', 'Infinity', '1e4', '3,500.00']) assert.throws(() => decimalInput(value), /non-negative decimal/);
});

test('FastAPI validation details are readable and do not stringify raw error objects', () => {
  assert.equal(errorDetail('Duplicate original on this trip.'), 'Duplicate original on this trip.');
  assert.equal(errorDetail([{ loc: ['body', 'amount_bdt'], msg: 'Invalid decimal', input: '<script>bad</script>' }]), 'amount_bdt: Invalid decimal');
  assert.equal(errorDetail({ unexpected: 'object' }), 'The request could not be completed. Please retry.');
});

function detailFixture(): TripDetail {
  return {
    trip: { id: 1, code: 'TEST', customer: 'Synthetic customer', driver: 'Synthetic driver', truck: 'Synthetic truck', origin: '', destination: '', status: 'ready_for_review', revision: 3, created_at: '2026-11-07T00:00:00Z' },
    evidence: [], actions: [], audit: [],
    settlement: { invoice_bdt: '32000.00', received_bdt: '32000.00', outstanding_bdt: '0.00', expense_bdt: '3500.00', advance_bdt: '5000.00', cash_return_bdt: '1500.00', advance_balance_bdt: '0.00', delivery_confirmed: true, can_settle: true, issues: [], sources: {} },
    investigations: [{ id: 2, trip_id: 1, revision: 3, mode: 'demo', status: 'completed', summary: 'Synthetic test fixture only', question: null, recipient: null, evidence_ids: [], steps: [], created_at: '2026-11-07T00:00:00Z' }],
  };
}

test('close gate requires validator eligibility and the latest completed current-revision run', () => {
  const detail = detailFixture();
  assert.equal(canClose(detail), true);
  detail.trip.revision = 4;
  assert.equal(canClose(detail), false);
  detail.trip.revision = 3;
  detail.settlement.can_settle = false;
  assert.equal(canClose(detail), false);
  detail.settlement.can_settle = true;
  detail.investigations.push({ ...detail.investigations[0]!, id: 5, status: 'failed' });
  assert.equal(latestRun(detail)?.id, 5);
  assert.equal(canClose(detail), false);
  detail.investigations.pop();
  detail.trip.status = 'settled';
  assert.equal(canClose(detail), false);
});

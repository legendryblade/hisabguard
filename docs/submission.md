# HisabGuard Submission

**Read this honestly.** HisabGuard is a working evidence-first prototype with genuine live-model calls on synthetic records. It is **not** validated deployment, **not** banking integration, and **not** a tested real-operator product. Treat every claim below accordingly.

## Problem And One Workflow

Small transport operators in Bangladesh juggle invoices, challans, fuel receipts, driver advances and customer voice promises across WhatsApp threads and paper notebooks. Disputes stall because no one sees the full picture against a single invoice, and verbal promises get recorded as money received.

The hero workflow is synthetic **TRIP-104**: a BDT 32,000 invoice, BDT 25,000 payment record, signed challan, BDT 3,500 fuel receipt and BDT 5,000 driver advance. Customer outstanding is BDT 7,000; the BDT 1,500 advance balance is separately accountable. **A promise to pay tomorrow changes neither.** Review evidence, investigate the exception, request the next useful proof, then approve and export a follow-up draft. Do not present these amounts as money recovered or savings.

Use the [90-second demo script](demo.md). Closure remains blocked in this walkthrough. Any separate closure demonstration requires reviewed payment/cash-return records, a completed current-revision investigation and explicit owner approval; typed records are operator attestations, not bank verification.

## Bounded AI And Evidence Architecture

Implementation references: [PRD](../PRD.md), [API contract](api-contract.md), [agent loop](../app/agent.py), [provider clients](../app/providers.py) and [independent validator](../app/settlement.py).

| Layer | Exact Responsibility And Boundary |
|-------|-----------------------------------|
| Evidence intake | Private image/audio originals and explicitly labelled manual records persist with evidence ids. Vision proposes fields; schema validation precedes storage as draft evidence. Audio transcription always remains a statement, never a payment or delivery proof. Failed processing preserves originals for manual review; it does not invent fields. |
| Human review | Only explicit operator confirmation puts financial evidence into arithmetic; draft/excluded records do not change totals. Exclusion retains original/audit history. Screenshots and signatures are not independently authenticated. |
| Deterministic validator | Integer-paisa BDT arithmetic, source-id mapping, duplicate transaction/file-hash checks, invoice/delivery conflicts, missing evidence, outstanding payment and advance accounting. Advance balance = advances - expenses - cash returned. Statements/promises do not count as payment. Closure requires reconciled balances, reviewed delivery and no blocking issues. |
| Model tool loop | OpenAI-compatible chat completions choose only `get_trip_records`, `inspect_document`, `compare_payment`, `identify_missing_evidence`, `request_clarification`, `prepare_followup`, `finish_investigation`. At most eight model turns, eight calls per turn, one question and one follow-up per run; arguments and current-trip ids are validated. Document/statement text is treated as untrusted data. |
| Proposal checks | Follow-ups require evidence citations and checks of explicitly labelled currency figures against independent totals or confirmed cited amounts. Final persisted settlement summary is deterministic. These checks do not prove every natural-language claim true; the owner must review the draft. |
| Human control and persistence | SQLite/private filesystem retain evidence, revisions, questions, tool calls/results, actions and audit events. Evidence changes stale pending approvals and invalidate old-revision exports/closure recommendations. Closure requires the validator, a completed current-revision investigation and explicit owner decision. |

The model has no evidence-review, ledger-write, approval, payment, message-send or settlement-close tool. Approval authorizes a draft download only. HisabGuard does not pay, send WhatsApp/messages, move money, call a bank/bKash/government API, verify signatures independently or issue fraud verdicts.

## Providers And Verification Status

Live-provider clients were exercised through OpenRouter with `nvidia/nemotron-3.5-super-vl:free`. Six synthetic investigations completed; the lexical routing proxy scored the live model 5/6 versus 4/6 for the actual baseline, but several questions were overly broad and the duplicate-fuel case addressed the wrong party. **Do not treat 5/6 as an accuracy claim it is not.** Full-field vision was 1/3; a confidence-handling fix is unit-tested but the live retest was blocked by rate limits. Current free requests are rate-limited and the paid model returned HTTP 402. A configured status flag does not guarantee availability.

| Path | Configuration And Protocol | Evidence Status |
|------|----------------------------|-----------------|
| Reasoning | `HISABGUARD_LLM_BASE_URL`, `HISABGUARD_LLM_API_KEY`, `HISABGUARD_LLM_MODEL`; OpenAI-compatible `/chat/completions` with tool calls | Actual NVIDIA/OpenRouter calls and traces recorded (see [evaluation results](evaluation-results.md)). |
| Vision | Same reasoning endpoint/key plus `HISABGUARD_VISION_MODEL`; multimodal chat completions with JSON field proposal | Three synthetic image calls tested; 1/3 full-field matches. Parser fix's live retest blocked by provider quota. |
| Speech | `HISABGUARD_STT_BASE_URL`, `HISABGUARD_STT_API_KEY`, `HISABGUARD_STT_MODEL`; `/audio/transcriptions` | Not exercised live. Real Bangla audio accuracy is unknown and must not be advertised. |
| No credentials | Explicitly labelled deterministic `demo` mode, not a model call | Demonstrates rules only; cannot prove live integration. |
| Unit tests | Mocked provider responses and synthetic fixtures | Validate controlled behavior, not endpoint availability, real extraction/transcription accuracy or customer impact. |

Provider/model, recorded questions, code/data hashes, timing conditions and failed attempts are published in [evaluation results](evaluation-results.md). A local HTTP smoke check alone is not a model call. Real-input accuracy and impact still need separate benchmarks and consent.

## Submission Artifacts

| Deliverable | Location / Status |
|-------------|-------------------|
| Repository | **Public**: https://github.com/legendryblade/hisabguard |
| Setup | [README](../README.md). Local run: `cd E:\hisabguard && .venv\Scripts\python -m uvicorn app.main:app --port 8834`. Judges run everything offline; no provider keys included. |
| Public judge URL | Temporary Cloudflare tunnel was up at submission prep time; **not durable**. Do not depend on it; use the repo + local run instead. |
| 90-second recording | Live model workflow recorded: `artifacts/recording-live-20261108-180806/HisabGuard-live-demo.mp4` (101.76 s). Deterministic UI preview: `artifacts/recording-demo-20261108-112336/`. Not validated on real customer inputs. |
| Technical evaluation | [Actual synthetic live results](evaluation-results.md), including misses and provider failures. Not real customer or receipt-accuracy validation. |
| Operator review | **NOT INTERVIEWED**: [15-20 minute protocol and blank observation sheet](operator-validation.md). No completed interviews, quotes or outcomes claimed. |
| Tool disclosure | AI-assisted coding is disclosed as the development method; no "Devin" claim is made because Devin itself was not used for this codebase. |
| Team registration | Registered team of 3–4 members (confirmed by the team). |

Deadline supplied by the team: **Nov 10, 2026, 23:45 Bangladesh local time (GMT+6)** (as listed on the official Devpost page). Verify before relying on it.

## Honest Impact And Release Gate

The hypothesis is that evidence-linked exceptions and targeted follow-ups can help an operator reconcile a trip without counting promises as cash. User fit, time benefit, revenue recovery and broader impact are unproven. No invented statistics, savings, adoption or guaranteed prize are claimed. Synthetic demonstrations and mocked tests are not interviews or real-world impact evidence.

This is a single-operator pilot, not multi-tenant production software. Before real uploads/public use, agree consent and provider processing, retention/deletion and private backup policies, restrict access and complete a security/data-protection review. Never upload real NID, customer phone or bank account data without explicit permission; default to synthetic/redacted artifacts as described in the operator protocol.

Record unresolved failures/limitations alongside results. Completing artifacts does not guarantee selection or a prize.
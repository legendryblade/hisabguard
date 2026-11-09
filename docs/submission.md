# HisabGuard Submission Draft

**Not ready to submit.** Public judge access, a successful live-workflow video and real operator review remain pending. Genuine synthetic live-provider evaluation is now documented, with failures and weaknesses; it is not validated deployment or real-world impact.

## Problem And One Workflow

HisabGuard is an evidence-first trip-settlement investigation workspace for small transport operators in Bangladesh. The illustrative three-truck operator receives invoices, challans, expenses, advances, payment screenshots and voice promises in different places. This persona is synthetic; no customer research or adoption is implied.

The single hero workflow is synthetic TRIP-104: a BDT 32,000 invoice, BDT 25,000 payment record, signed challan, BDT 3,500 fuel receipt and BDT 5,000 driver advance. Customer outstanding is BDT 7,000; the BDT 1,500 advance balance remains separately accountable. A promise to pay tomorrow changes neither. Review evidence, investigate the exception, request the next useful proof, then approve and export a follow-up draft. Do not present these amounts as money recovered or savings.

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

Live-provider clients were exercised through OpenRouter with `nvidia/nemotron-3.5-super-vl:free`. Six synthetic investigations completed, with a 5/6 lexical routing proxy versus 4/6 for the actual baseline; human inspection found broader questions than desired. Full-field vision was 1/3. Current free requests are rate-limited and the paid model returned HTTP 402. A configured status flag does not guarantee availability.

| Path | Configuration And Protocol | Evidence Status |
|------|----------------------------|-----------------|
| Reasoning | `HISABGUARD_LLM_BASE_URL`, `HISABGUARD_LLM_API_KEY`, `HISABGUARD_LLM_MODEL`; OpenAI-compatible `/chat/completions` with tool calls | Actual NVIDIA/OpenRouter calls and traces recorded; current quota prevents a reliable new recording. |
| Vision | Same reasoning endpoint/key plus `HISABGUARD_VISION_MODEL`; multimodal chat completions with JSON field proposal | Three synthetic image calls tested; 1/3 full-field matches. Parser fix's live retest blocked by 429. |
| Speech | `HISABGUARD_STT_BASE_URL`, `HISABGUARD_STT_API_KEY`, `HISABGUARD_STT_MODEL`; `/audio/transcriptions` | Real Bangla audio call, transcript comparison and outcome pending. |
| No credentials | Explicitly labelled deterministic `demo` mode, not a model call | May demonstrate rules, but cannot prove live integration. |
| Unit tests | Mocked provider responses and synthetic fixtures | Validate controlled behavior, not endpoint availability, real extraction/transcription accuracy or customer impact. No pass count claimed here. |

Provider/model, recorded questions, code/data hashes, timing conditions and failed attempts are published in [evaluation results](evaluation-results.md). A local HTTP smoke check alone is not a model call. Real-input accuracy and impact still need separate benchmarks and consent.

## Submission Artifacts

| Deliverable | Location / Status |
|-------------|-------------------|
| Local demo address | `http://127.0.0.1:8834/` per [README](../README.md); local only, not a public deployed judge link, and availability was not tested for this document. |
| Public working judge URL | **PENDING**. Deploy with TLS, workspace authentication and restricted private storage; verify from outside the developer machine and provide judge access privately. Never publish provider keys or access tokens. |
| Repository/setup | Local workspace `E:\hisabguard`; [setup instructions](../README.md). Public repository URL and judge access pending. |
| 90-second recording | A labelled deterministic UI preview exists under `artifacts/recording-demo-20261108-112336/`; it is not the live-AI submission video. Live recording and judge-accessible video URL remain **PENDING**. |
| Technical evaluation | [Actual synthetic live results](evaluation-results.md), including misses and provider failures. Not real customer or receipt-accuracy validation. |
| Operator review | **NOT INTERVIEWED**: [15-20 minute protocol and blank observation sheet](operator-validation.md). No completed interviews, quotes or outcomes claimed. |
| Tool disclosure | List only development tools actually used and evidenced by the team. No Devin-use claim is made; other AI coding assistance is not evidence of Devin usage. |
| Team registration | Supplied Devpost brief requires a registered team of **3-4 members**. Member identities/registration confirmation pending; verify the live organizer rules before submission. |

The deadline supplied by the user is **Nov 10, 2026, 22:45 GMT+5**, equivalent to **Nov 10, 2026, 23:45 Bangladesh local time (GMT+6)**. This is a timezone conversion of the supplied deadline, not independent verification of an official date. Verify the live organizer/Devpost deadline and eligibility rules before relying on it.

## Honest Impact And Release Gate

The hypothesis is that evidence-linked exceptions and targeted follow-ups can help an operator reconcile a trip without counting promises as cash. User fit, time benefit, revenue recovery and broader impact are unproven. No invented statistics, savings, adoption or guaranteed prize are claimed. Synthetic demonstrations and mocked tests are not interviews or real-world impact evidence.

This is a single-operator pilot, not multi-tenant production software. Before real uploads/public use, agree consent and provider processing, retention/deletion and private backup policies, restrict access and complete a security/data-protection review. Never upload real NID, customer phone or bank account data without explicit permission; default to synthetic/redacted artifacts as described in the operator protocol.

Keep this draft pending until the public URL and video work for judges, the main agent records successful real-provider evidence for every advertised live feature (or clearly marks unsupported paths), and a consented real operator review is documented. Record unresolved failures/limitations alongside results. Registration and live organizer requirements must also be checked; completing artifacts does not guarantee selection or a prize.

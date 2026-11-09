---
goal: Build a bounded evidence-first transport settlement investigation product
version: 1
date_created: 2026-11-08
last_updated: 2026-11-08
owner: HisabGuard team
status: In progress
tags: [feature, evidence, agent, frontend, verification]
---

# Introduction

![Status: In progress](https://img.shields.io/badge/status-In%20progress-yellow)

Implement the one-trip evidence-to-approved-follow-up workflow described in PRD.md and docs/api-contract.md. Do not copy the policy-only claims or unsafe money/state shortcuts of earlier prototypes.

## 1. Requirements & Constraints

- **REQ-001**: Persist originals, reviews, trips, revisions, investigations, follow-ups, and audit records.
- **REQ-002**: Use bounded real model tool calls when configured, clearly labelled demo mode otherwise.
- **REQ-003**: Reassess statements without counting promises as payments; compute integer-paisa totals from reviewed evidence only.
- **SEC-001**: Authenticate public deployments, bound and validate uploads, keep originals private, escape reports, reject stale approvals.
- **CON-001**: Single-operator pilot with SQLite/private filesystem; no real messaging, banking, fraud score, or customer-validation claims.
- **GUD-001**: Exception-first, responsive, keyboard-accessible desk with visible evidence references and failure recovery.
- **PAT-001**: React/TypeScript with FastAPI API, dedicated providers module, independently validated settlement and source ids.

## 2. Implementation Steps

### Implementation Phase 1

- **GOAL-001**: Complete product/API contract and persistent evidence/settlement core; verify using isolated pytest databases.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Write PRD.md and docs/api-contract.md defining money, review, revision and endpoint semantics | Yes | 2026-11-08 |
| TASK-002 | Implement app/store.py, app/schemas.py, app/settlement.py, app/demo.py with transactional evidence review and source-linked integer-paisa balances | Yes | 2026-11-08 |
| TASK-003 | Implement app/agent.py and app/main.py with allowlisted tools, review/approval separation, invalidation and private upload/report APIs | Yes | 2026-11-08 |

### Implementation Phase 2

- **GOAL-002**: Build provider clients and operable frontend; verify provider mocks and npm typecheck/build.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-004 | Implement app/providers.py and tests/test_providers.py for real chat/vision/audio, safe malformed response handling and credential isolation | Yes | 2026-11-08 |
| TASK-005 | Implement web/src/App.tsx, web/src/api.ts, web/src/types.ts and web/src/styles.css for queue, trip intake, upload/review, investigate/reply and approval/export | Yes | 2026-11-08 |

### Implementation Phase 3

- **GOAL-003**: Verify all acceptance workflows in backend and desktop/mobile browser, write deployment docs and start verified localhost service.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-006 | Run tests/test_workflow.py and scripts/browser_check.py against isolated data; fix provider failure, duplicate money, stale approval and responsive rendering defects | Yes | 2026-11-08 |
| TASK-007 | Write README.md, .env.example, Dockerfile, compose.yml, .dockerignore, requirements files and docs/demo.md; start port 8834 and verify API/assets/browser | Yes | 2026-11-08 |

### Implementation Phase 4

- **GOAL-004**: Verify genuine provider calls, compare live next-evidence decisions to the existing deterministic reviewer, and create honestly labelled demo/submission artifacts.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-008 | Add scripts/provider_env.py and scripts/run.py for explicit user-authorized OpenRouter credential mapping in process memory only; test credential isolation in tests/test_readiness.py | Yes | 2026-11-08 |
| TASK-009 | Add data/evaluation.json and scripts/evaluate.py with preregistered synthetic routing targets, an actual app/demo.py baseline, validator-invariance checks and bounded live OCR/model calls | Yes | 2026-11-08 |
| TASK-010 | Run synthetic live evaluation, fix observed provider/tool failures, and publish actual questions, scores, timings and limits in docs/evaluation-results.md | Partial: results published and fixes unit-tested; focused prompt/OCR live retest blocked by 429 | 2026-11-08 |
| TASK-011 | Start the tested reasoning/vision model, verify real browser activity, record a synthetic live demo with scripts/record_demo.py, and prepare docs/operator-validation.md and docs/submission.md | Partial: recorder and labelled 90s demo preview exercised; live recording/activation blocked by provider access | 2026-11-08 |

### Implementation Phase 5

- **GOAL-005**: Produce verified live-AI artifacts and a protected, synthetic-only public judge instance; publish only authorized intended source and accurately report remaining submission gates.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-012 | Add judge-only reset, synthetic evidence tagging, disabled uploads and bounded investigation attempts in app/main.py and app/store.py; test normal-data/reset isolation in tests/test_judge.py | No | |
| TASK-013 | Add scripts/prepare_submission.py to verify supplied in-memory provider configuration, run evaluation/recording, start isolated judge service and authenticated Cloudflare HTTPS tunnel, and write non-secret progress plus separate private access credentials | No | |
| TASK-014 | Add judge reset/scope disclosure and active-run type validation in web/src; verify npm tests/build and external authenticated browser flow | No | |
| TASK-015 | Update accurate Devpost copy/setup and record verified source/video/demo links; inspect status/diff/log, commit only intended files, and publish the user-authorized public GitHub repository/release | No | |

## 3. Alternatives

- **ALT-001**: PostgreSQL/object storage from day one deferred for the single-operator local pilot; public multi-tenant operation requires further engineering.
- **ALT-002**: Policy-only planner presented as AI rejected; demo review mode is disclosed separately.

## 4. Dependencies

- **DEP-001**: Python FastAPI, Pydantic, HTTPX, dotenv, multipart, Pillow, pytest; React, Vite and TypeScript.
- **DEP-002**: Actual vision/reasoning and STT credentials for live provider verification; no key fabrication or cross-project credential reuse.
- **DEP-003**: Installed Edge and Playwright for browser evidence and mobile viewport tests.
- **DEP-004**: User explicitly approved the available OPENROUTER_API_KEY for synthetic live tests and model-mode activation. No secret is displayed or written to the repository. Model catalogue confirms openai/gpt-4.1-mini supports image input and tools.
- **DEP-005**: User confirmed eligible 3-4-person team registration and authorized public GitHub creation, intended-source commit/push, and protected synthetic HTTPS demo publication. A supplied provider credential must remain in process memory and never enter source, logs, artifacts or Git.

## 5. Files

- **FILE-001**: app/store.py, app/schemas.py, app/settlement.py, app/demo.py, app/agent.py, app/main.py own the core and APIs.
- **FILE-002**: app/providers.py and tests/test_providers.py own provider configuration and mocks.
- **FILE-003**: web/src and web/package.json own the product UI/build.
- **FILE-004**: tests/test_workflow.py, scripts/browser_check.py, README.md, docs/demo.md and deployment files own verification/handoff.
- **FILE-005**: scripts/provider_env.py, scripts/run.py, scripts/evaluate.py, scripts/record_demo.py, data/evaluation.json, tests/test_readiness.py and submission/validation/evaluation docs own live-readiness work.
- **FILE-006**: scripts/prepare_submission.py, tests/test_judge.py and judge-mode UI/API additions own final publication readiness. Private .judge data and access metadata are excluded from Git and Docker.

## 6. Testing

- **TEST-001**: Isolated pytest workflow cases cover invoices/payments/promises, duplicate ids/files, delivery proof, conflicting invoices, negative/nonfinite values and advance accounting.
- **TEST-002**: Provider mocks cover valid tool calls, errors, malformed extraction, transcription and no secret disclosure.
- **TEST-003**: Browser walkthrough covers upload/review, investigation/reply, approve/reject/export, persistence, report, 390px and 1440px viewports with console/network failure assertions.
- **TEST-004**: Preregistered synthetic cases compare actual rule-based reviewer and live-model questions using disclosed recipient/keyword checks; report all samples and unchanged accounting. No claim of real customer or Bangla STT accuracy follows from this test.

## 7. Risks & Assumptions

- **RISK-001**: No credentials means live model accuracy and Bangla STT remain unverified; demo must say so.
- **RISK-002**: Screenshots and human confirmation are not independent bank verification; product is a review tool, not fraud proof.
- **RISK-003**: Live provider calls consume API credits and may fail despite advertised capabilities. Cap evaluation calls, stop on invalid credentials, and never swap canned responses into recorded model mode.
- **RISK-004**: No transport operator has been interviewed. Prepare an interview protocol and mark validation/public deployment as outstanding, not completed.
- **RISK-005**: Temporary Cloudflare judge URL requires this machine and the tunnel process to remain running. A public repo/video does not itself guarantee eligible submission. Official deadline header says November 10 23:45 +06; rules page contains stale September dates, so retain that discrepancy in the eligibility notes.
- **ASSUMPTION-001**: No HisabGuard directory exists at E:/hisabguard; create a separate product without touching other projects.
- **ASSUMPTION-002**: External follow-ups remain downloadable approved drafts, not automated sends.

## 8. Related Specifications / Further Reading

- [Product requirements](../../PRD.md)
- [API contract](../../docs/api-contract.md)
- [OpenAI tool calling](https://platform.openai.com/docs/guides/function-calling)

## Verification Results

- `python -m pytest tests -q`: 135 passed. Provider tests use mocked HTTP responses, not live credentials.
- `npm run test`: 10 passed. `npm run typecheck` and `npm run build`: passed. `npm audit`: zero vulnerabilities.
- `python scripts/browser_check.py`: 29 checks passed in real Edge against isolated data at 1440px and 390px. Desktop and mobile screenshots inspected.
- `python scripts/live_smoke.py`: running root, trip, new-trip, settings and activity routes render; zero uncaught JavaScript exceptions. No production records changed.
- Local server running on `http://127.0.0.1:8834/`; status reports demo mode, no model/STT keys configured.
- Compose configuration validated. Docker image execution remains unverified because the Docker daemon is unavailable. Live provider accuracy, customer validation and public deployment are outside this completed pilot's verified scope.

## Readiness Extension Results And Blockers

- User approved OpenRouter synthetic calls. Paid model returned 402; free Gemma returned 429; NVIDIA free model completed genuine tool calls after optional reasoning was disabled.
- Six live synthetic investigations completed. Lexical/recipient proxy matched 5/6 routes versus 4/6 for the actual deterministic reviewer; all ledger values remained unchanged. Manual inspection found overly broad questions and a wrong duplicate-claim recipient. This is not operator-validation evidence.
- Full-field OCR was 1/3. Unknown confidence handling was fixed without inventing values; the live retest received 429 for every image. Latest focused prompt and parser changes remain unverified live.
- `python -m pytest tests -q`: 144 passed after readiness/provider additions. User data and provider secrets were not saved in evaluation artifacts.
- `scripts/record_demo.py --mode demo --seconds 90`: successful 90.02s labelled deterministic browser preview; it does not represent a live-AI run.
- Actual evaluation, unchanged baseline, raw generated questions, timings, hashes and failed attempts are published in docs/evaluation-results.md. Submission and operator-interview materials remain explicit about missing public hosting/live recording/real-user review.
- Next actionable task: supply funded accessible provider capacity or wait for a verified quota recovery, then rerun the focused-prompt/vision evaluation and `scripts/record_demo.py --mode live --provider openrouter --model <accessible model>`. Do not enable a known-unavailable default or pass the deterministic preview off as AI.

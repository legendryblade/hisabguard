---
goal: Implement the complete evidence-first HisabGuard frontend against API contract v1
version: 1
date_created: 2026-11-07
last_updated: 2026-11-07
owner: Frontend agent
status: Completed
tags: [feature, frontend, accessibility, verification]
---

# Introduction

![Status: Completed](https://img.shields.io/badge/status-Completed-brightgreen)

Frontend continuation of the shared feature-settlement-hisabguard-1.md plan, TASK-005. The shared plan was read first and remains owned by the main agent. This scoped plan tracks frontend implementation only.

## 1. Requirements & Constraints

- **REQ-001**: Implement queue, intake, evidence upload/review, investigation/reply, draft approval/export, settlement close, report, backup, activity and settings using real API endpoints.
- **REQ-002**: Display backend decimal strings and evidence citations; never calculate received money from statements.
- **SEC-001**: Bearer header authentication, session-only optional token persistence, escaped text, authenticated binary fetch, revoked object URLs and cancellation of obsolete reads.
- **CON-001**: Change only web files and docs/design-contract.md; no background server, shared plan edits, backend edits or git operations.
- **GUD-001**: Navy navigation, paper desk, orange risk, blue selection, 16px text, 44px controls and structural 390px reflow.
- **PAT-001**: React 18.3, native browser-history routing, strict TypeScript, Vite 7 compatible with verified Node 24; plain CSS and no UI framework.

## 2. Implementation Steps

### Implementation Phase 1

- **GOAL-001**: Contract, tooling and design are established; verify by reading files and npm install.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Add web/package.json, web/tsconfig.json, web/vite.config.ts and web/index.html with Vite 7.3.7 and /api proxy to port 8834 | Yes | 2026-11-07 |
| TASK-002 | Add docs/design-contract.md and web/src/types.ts, web/src/api.ts, web/src/utils.ts with contract schemas, auth, binary handling and decimal formatting | Yes | 2026-11-07 |

### Implementation Phase 2

- **GOAL-002**: Every specified route and API mutation is wired; verify npm run typecheck and source reads.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-003 | Add web/src/App.tsx, web/src/components.tsx, web/src/hooks.ts, web/src/main.tsx and web/src/navigation.tsx with shell, auth recovery and cancellable reads | Yes | 2026-11-07 |
| TASK-004 | Add web/src/Queue.tsx, web/src/TripDesk.tsx, web/src/Evidence.tsx, web/src/Pages.tsx implementing all routes and review gates | Yes | 2026-11-07 |
| TASK-005 | Add web/src/styles.css with compact ledger, evidence tickets, mobile nav, focus and reduced-motion states | Yes | 2026-11-07 |

### Implementation Phase 3

- **GOAL-003**: Run unit tests, strict typecheck and production build; document exact automation labels and unverified browser scope.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-006 | Add web/src/utils.test.ts and web/src/api.test.ts for decimal strings, safe errors, current-revision gating, headers, encoding, malformed JSON, conflicts and cancellation | Yes | 2026-11-07 |
| TASK-007 | Run npm run test, npm run typecheck and npm run build in web; record results in web/README.md and this plan | Yes | 2026-11-07 |

## 3. Alternatives

- **ALT-001**: Component/UI frameworks and icon packages rejected because native controls and a typographic ledger best fit this compact settlement desk.
- **ALT-002**: Floating-point formatting rejected; exact decimal strings are grouped without Number conversion.
- **ALT-003**: Optional Router 6 rejected after npm audit reported moderate advisories; four fixed route patterns use native history and real anchors instead.

## 4. Dependencies

- **DEP-001**: Backend implements docs/api-contract.md on port 8834; frontend development uses same-origin /api proxy.
- **DEP-002**: Main agent owns actual browser E2E and backend integration verification.

## 5. Files

- **FILE-001**: web/package.json, web/package-lock.json, web/tsconfig.json, web/vite.config.ts, web/index.html and web/.gitignore own tooling.
- **FILE-002**: web/src/*.ts, web/src/*.tsx and web/src/styles.css own frontend behavior and tests.
- **FILE-003**: docs/design-contract.md and web/README.md document visual decisions and frontend handoff.

## 6. Testing

- **TEST-001**: Node built-in test runner checks exact money display, error formatting, revision gates, bearer auth, encoded ids, duplicate detail, malformed responses and cancelled requests without a new test framework. All 10 tests pass.
- **TEST-002**: npm run typecheck and npm run build verify strict TypeScript and production bundling; both pass. npm install reports zero vulnerabilities without script approval or security changes.
- **TEST-003**: Main-agent browser E2E verifies upload, review, replies, approval, downloads and 1440/390px behavior; not claimed by this agent.

## 7. Risks & Assumptions

- **RISK-001**: Backend/provider implementation is concurrent; no fabricated API data or live credential verification.
- **RISK-002**: Fonts use installed Fira Sans/Noto Sans Bengali with system fallback, not a privacy-sensitive remote font fetch.
- **ASSUMPTION-001**: SPA fallback for production client routes is owned by the backend/deployment agent.

## 8. Related Specifications / Further Reading

- [PRD](../../../../PRD.md)
- [API contract](../../../../docs/api-contract.md)
- [Shared plan](../../../../.opencode/plans/feature-settlement-hisabguard-1.md)

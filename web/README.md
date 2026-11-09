# HisabGuard Frontend

Complete React 18.3.1 / strict TypeScript settlement desk using API contract v1. It contains no production demo arrays, simulated API success, financial floating-point arithmetic, provider keys, or sending integration.

## Commands

Run from `E:\hisabguard\web`:

```powershell
npm install
npm run dev
npm run test
npm run typecheck
npm run build
```

`dev` is a foreground command on `127.0.0.1:5181`; `/api` proxies to `127.0.0.1:8834`. No server was started by the frontend agent. Production output is `web/dist`; the backend/deployment owner must serve assets and the SPA fallback for client routes. All API URLs stay same-origin.

Vite `7.3.7` was selected after `npm view vite@7 version` and its engines were checked against installed Node `24.18.0`. The final dependency install reported zero vulnerabilities. The optional Router 6 dependency was removed after the registry audit identified moderate advisories; a small native History API router supports real anchors, modified clicks, back/forward and unknown routes. No security settings or global npm configuration were changed. npm's esbuild install-script warning was not approved; the production build succeeds with the normally installed platform binary.

## Routes And Automation

| Route | Heading | Main controls |
|-------|---------|---------------|
| `/` | Trip settlements | New trip, Flagged trips, All trips, Search trips, Settlement status, Refresh register, Open trip (accessible name includes the trip code) |
| `/trips/new` | New trip | Trip code, Truck, Customer, Driver, Origin, Destination; Create trip, Cancel, Back to trip settlements |
| `/trips/:id` | Actual trip code | Evidence, Investigation, Follow-ups, Activity section links; Printable report, JSON backup, Refresh trip |
| `/activity` | Activity | Refresh activity, Event details, Open trip followed by numeric id |
| `/settings` | Settings | Refresh provider status, Download JSON backup |
| Unknown route | This page is not in the register | Back to trip settlements |

The root defaults to Flagged trips. Choose All trips to find newly created trips with no exceptions or settled trips. Queue totals always come from `overview`, independent of the visible search/filter.

### Evidence

- `Add evidence` opens an inline form. Choose `Typed operator record` or `Upload image / audio`.
- Typed labels: `Evidence title`, `Evidence kind`, `Amount (BDT)`, `Transaction ID`, `Trip reference`, `Delivery confirmation`, `Operator note`, `Record text / transcript`. Submit: `Add draft record`.
- Upload labels: `Evidence title`, `Kind hint`, `Original image or audio`. Submit: `Upload original`. Input name is `file`; accepts image/audio, maximum 10 MB. A 409 renders the actual safe duplicate detail.
- Scope an evidence ticket by `#evidence-<id>` or its accessible title. `View original` fetches the authenticated original and exposes `Download original`, image preview or native audio controls. The toggle becomes `Hide original`.
- `Review evidence` opens a draft editor; reviewed records expose `Review / correct record`. All contract review fields are editable except an original statement's locked kind.
- Check the checkbox beginning `I have checked the kind, amount, transaction ID...`, then use `Confirm evidence`. `Exclude evidence` preserves the original and audit trail. Both decisions are operator review, not bank verification.
- Source links `E<id>` reveal the full evidence list even when a state filter previously hid the cited record.

### Investigation And Follow-ups

- `Investigate trip` calls the real endpoint. A latest failed run changes the label to `Retry investigation`. A 502 triggers a trip reload and leaves the safe error visible alongside the persisted failed run; no fake demo fallback is substituted.
- A persisted question shows its actual recipient and evidence IDs. `Reply text` starts empty. Submit with `Record reply as statement`, then click `Investigate trip` again.
- Scope actions by `#action-<id>`. Current pending actions offer `Approve draft` and `Reject draft`. Current approved actions offer `Download approved text`. Stale revisions have no approval/export controls. Status badges preserve the persisted decision and separately disclose revision staleness.
- Approved text is fetched with bearer authentication and downloaded as `hisabguard-draft-<id>.txt`. Approval never sends it.

### Closure, Reports And Access

- `Close settlement` is enabled only after `can_settle`, the latest completed current-revision investigation, and the checkbox beginning `I have reviewed the evidence and independently computed balances...`. Actual API 409 details remain visible; a settled badge is rendered after success.
- `Printable report` synchronously opens a tab, fetches real authenticated HTML, and navigates the tab to a blob URL. Allow this site's popups in browser automation. Print from that tab. HTML is never inserted into the React tree.
- `JSON backup` or `Download JSON backup` downloads real `/api/export` output as `hisabguard-backup.json`; binaries and secrets are not included.
- `Access` opens the inline token panel. A 401 also opens it automatically. Label `Access token`, checkbox `Remember for this browser session only`, submit `Connect and retry`; `Clear token` removes memory/session storage. Tokens are never put in URLs or localStorage.
- Mobile navigation uses `Menu` / `Close menu`; the nav's expanded state is exposed. The content pane, not the global body, scrolls. Tests can scroll `#workspace` and use section links or `scroll_into_view_if_needed` for evidence/actions.

## Verification

- `npm run test`: 10 passing built-in Node tests covering exact decimal strings, decimal validation, human FastAPI errors, latest-run closure gating, bearer headers, URL encoding, exact duplicate details, malformed responses, 401 recovery events and obsolete response cancellation.
- `npm run typecheck`: passed with strict TypeScript, unused-symbol and unchecked-index checks.
- `npm run build`: passed with Vite 7.3.7. Final build output lives in `web/dist`.
- Source finish review covered 44px controls, visible focus, 16px body/control text, mobile structural reflow, long-content wrapping, escaped React text, audio controls, token secrecy, draft-only states and URL cleanup.

## Known Verification Gaps

The frontend agent did not run a browser, start background services, exercise the live concurrent backend, or test genuine provider credentials. The main agent owns actual desktop 1440px/mobile 390px E2E and screenshots. Fonts use local Fira Sans/Noto Sans Bengali with system fallback; no remote font fetch is required. Backend contract correctness, original accuracy, public hosting, SPA serving, real Bangla transcription accuracy and persistence tests are separately owned.

## Ownership

Only `web/**` and `docs/design-contract.md` were changed. The shared plan was read, not edited; the scoped continuation is `web/.opencode/plans/feature-settlement-web-1.md`. No app, root tests, deployment files, other project files, git initialization or commits were touched.

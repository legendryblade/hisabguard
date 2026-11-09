# HisabGuard Settlement Desk

## Product And Hierarchy

This is an operator's trip-settlement desk, not an analytics dashboard or chatbot. The queue puts flagged trips and independently computed customer outstanding money first. A trip is a numbered evidence packet: original records, reviewed financial facts, unsupported statements, an investigation log, and gated draft follow-ups.

Customer outstanding and driver advance balance are separate ledgers. Every amount links to evidence IDs. Human confirmation is operator review, never independent bank verification. The synthetic demonstration notice and draft-only messaging disclosure remain visible on every route.

## Visual Contract

- Navy #14283e navigation rail with a typographic HG document mark, HisabGuard name and Bengali হিসাবগার্ড subtitle (a product requirement for Bangla transport operators).
- Warm paper #f6f3ec workspace and white evidence tickets, sturdy #c8cecF borders, restrained #c2410c risk/action accent with white text, blue #1d4e89 selected states.
- Fira Sans, Noto Sans Bengali, system sans-serif fallback, 16px minimum body/control type and tabular decimal amounts. No remote font dependency.
- Grid header labelled Trip settlements, a ruled queue and numbered evidence tickets. No decorative gradients, fake charts, savings metrics, ungrounded AI status, emoji or ornamental icon package.
- Desktop navigation is fixed within the app grid, local top navigation is sticky and the content pane scrolls. Mobile at 390px reflows navigation, ledger and table rows into one column. Wide tool JSON uses a local scroll region, never page overflow.

## Interaction Contract

- Controls have visible names, minimum 44px targets, visible focus rings, disabled pending states and reduced-motion support.
- Each route has real loading, empty, error and retry handling. A 401 opens an access-token panel without removing the page; tokens use bearer headers only and optional sessionStorage, never localStorage or query parameters.
- Evidence originals use authenticated blob fetches. React renders strings; no raw HTML insertion. Object URLs are revoked. Images retain natural aspect ratio; audio has native controls.
- Uploads and typed records start draft. Failed extraction preserves the original and offers manual review. Statement kind is locked during review. Confirm is explicitly an operator decision; exclude preserves audit history.
- Investigation mode comes from /api/status and persisted runs, not a frontend simulation. Failed runs remain visible. Replies become statements, then require a new investigation.
- Approve and reject are available only for current pending follow-ups; approved drafts can be downloaded but are never sent. Stale actions cannot be clicked. Close requires independent can_settle and the latest completed current-revision investigation.
- Printable reports and backups are authenticated downloads of real backend output. Report HTML is opened as a standalone blob document, never injected into the application.

## Finish Gate

Strict TypeScript, 10 native Node unit/request tests and the Vite 7.3.7 production build pass. The final dependency install reported zero vulnerabilities; the optional vulnerable Router 6 dependency was avoided in favor of native browser-history routing. Source review checks the stated accessibility and reflow rules. Main-agent browser E2E owns real 1440px/390px screenshots and backend workflow verification. This contract does not claim browser or live-provider tests were performed by the frontend agent.

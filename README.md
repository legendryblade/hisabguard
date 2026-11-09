# HisabGuard

Evidence-first trip settlement investigations for small transport operators in Bangladesh. This repository is a working single-operator pilot, not an independently bank-verified accounting service or a production fraud detector.

## What Works

- A trip register with outstanding customer payments, driver advance balances, blocking exceptions, and pending approvals.
- Private original image/audio uploads, configurable vision extraction and speech transcription, and manual operator records.
- Explicit evidence review: extracted fields are proposals until confirmed. Excluded records retain their originals and audit history.
- Independent integer-paisa arithmetic with source ids. A payment promise or voice note never increases received money.
- Duplicate original/transaction checks across trips, conflicting invoice/delivery checks, and missing-evidence questions.
- A bounded model tool loop: read records, inspect documents, compare payment, identify missing evidence, request clarification, prepare a follow-up, and finish. No approval, evidence-review, payment or closure tools are exposed to the model.
- Persistent questions, replies, tool results, revisions, stale approvals, and a decision trail.
- Owner approval/rejection of draft follow-ups, approved text export, printable evidence packets, JSON backup, and validator-gated settlement closure.

**No keys configured:** the app runs a clearly labelled deterministic review demonstration. It does not claim that model calls or OCR have happened. Processing failures preserve originals for manual review rather than inventing fields. All voice transcripts remain statements, even when they mention money.

## Local Run

Tested with Python 3.14 and Node 24. Install the pinned dependencies in a project virtual environment and build the frontend:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt
```

From `web/`:

```powershell
npm ci
npm run build
```

From the repository root:

```powershell
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8834
```

Open **http://127.0.0.1:8834/**. The backend serves both the API and the built frontend. For frontend development, `npm run dev` in `web/` proxies `/api` to the same backend; set `HISABGUARD_DEV_ORIGIN=http://127.0.0.1:5181` to permit development-origin writes.

## Real Model And Speech Configuration

The backend reads this repository's `.env` and only `HISABGUARD_*` environment variables. It never borrows keys from Shiri, OrderRescue or another product. `.env.example` lists the configuration; `.env` is ignored by Git and Docker.

The user-authorized `scripts/run.py --provider openrouter` launcher can explicitly map an already available `OPENROUTER_API_KEY` into HisabGuard's process environment. This is opt-in, does not read another project's configuration, and never prints or saves the key.

| Feature | Required Variables |
|---------|--------------------|
| Reasoning and tool calls | `HISABGUARD_LLM_BASE_URL`, `HISABGUARD_LLM_API_KEY`, `HISABGUARD_LLM_MODEL` |
| Vision extraction | Same endpoint/key plus `HISABGUARD_VISION_MODEL` |
| Bangla voice transcription | `HISABGUARD_STT_BASE_URL`, `HISABGUARD_STT_API_KEY`, `HISABGUARD_STT_MODEL` |
| Private remote access | `HISABGUARD_ACCESS_TOKEN` |
| Storage location | `HISABGUARD_DATA_DIR` (default `runtime/`) |
| Synthetic seed on empty database | `HISABGUARD_SEED_DEMO=1`; use `0` with a fresh data directory for an empty register |

Reasoning/vision endpoints must support OpenAI-compatible chat completions, multimodal messages and tool calls. STT supports OpenAI-compatible `/audio/transcriptions`, including Groq's Whisper endpoint. A configured flag means credentials are present, not that the provider has been benchmarked. Do not enter provider keys in the UI's Access panel; that panel accepts only the workspace access token.

## Demo

Three **explicitly synthetic** trip packets are created only on the first empty-database run:

| Trip | Investigation |
|------|---------------|
| TRIP-104 | Invoice BDT 32,000; payment BDT 25,000; fuel BDT 3,500; advance BDT 5,000; signed delivery record; payment promise. BDT 7,000 remains outstanding and BDT 1,500 of advance needs accounting. |
| TRIP-106 | Missing delivery proof; asks the driver for the signed challan rather than claiming completion. |
| TRIP-108 | Duplicate fuel transaction; counted once, flagged, and retained for review. |

Follow the [90-second demo](docs/demo.md). For the full closure path, review an additional BDT 7,000 payment and a BDT 1,500 cash return, investigate the current revision, and explicitly approve closure. A typed record is an operator attestation, not a banking integration.

## Verification

From the root:

```powershell
python -m pytest tests -q
python scripts/browser_check.py
python scripts/live_smoke.py
```

From `web/`:

```powershell
npm run test
npm run typecheck
npm run build
npm audit
```

The automated workflow tests use temporary SQLite directories; they do not delete the running application's data. Browser tests start an isolated server on `8864` and use installed Edge with Playwright. `live_smoke.py` is read-only and checks the real server on `8834`. On a machine without Edge, install a Playwright browser and change the browser channel appropriately.

The suite covers cent precision, promises, duplicate receipts/transactions, conflicting delivery records, invalid model calls, invented currency figures, concurrency, context growth, provider failure, approval freshness, stale exports, closure, private files and escaped reports. Browser tests cover upload/review, reply/reassessment, approval/export, closure, failed-provider recovery, access-token recovery, persistence, and 1440px/390px layouts.

Live provider accuracy, real Bangla transcription latency and real customer impact are **not measured** by mocked tests or synthetic fixtures.

## Live Evaluation And Submission Readiness

[Measured results](docs/evaluation-results.md) now include actual OpenRouter tool calls. The small synthetic routing proxy scored the live model 5/6 versus the existing reviewer 4/6, but human inspection found overly broad questions and a duplicate-receipt recipient error. This is not proof of winning, production readiness or real operator benefit. The full-field vision test was 1/3; a confidence-validation fix is unit-tested but its live retest was rate-limited.

The paid model returned HTTP 402 and current free requests return HTTP 429. The application remains in explicitly labelled demo mode until a reliable model/quota is available. After that, enable the model deliberately with:

```powershell
python scripts/run.py --provider openrouter --model "nvidia/nemotron-3.5-super-vl:free" --reasoning off
```

Reasoning-off is an OpenRouter extension for models whose reasoning is optional, not a parameter sent to arbitrary compatible endpoints. Do not use it on mandatory-reasoning models.

The [operator-validation protocol](docs/operator-validation.md) has no completed interviews. The [submission draft](docs/submission.md) lists public hosting, team registration and live video as outstanding.

Record only synthetic data in an isolated store:

```powershell
python scripts/record_demo.py --mode live --provider openrouter --model "nvidia/nemotron-3.5-super-vl:free" --reasoning off
python scripts/record_demo.py --mode demo --seconds 90
```

The second command produces a clearly labelled deterministic UI preview, not an AI demo. It was exercised successfully for 90 seconds. Playwright's video encoder is installed only in the ignored project `.cache/playwright/` directory; on a fresh machine install it there with `PLAYWRIGHT_BROWSERS_PATH` set before `python -m playwright install ffmpeg`. No recording reads or modifies the running application's user evidence.

## Docker

The image builds the frontend and runs the API as a non-root user with private persistent storage. Compose requires a nonempty access token because connections reach the container from a non-loopback address:

```powershell
docker compose up --build -d
```

The default port is loopback-bound at `8834`; enter the configured workspace token through Access. For public hosting, put TLS and an authenticated reverse proxy in front of the app. Compose syntax is validated. Image build/runtime was not verified on this workstation because the Docker daemon is unavailable.

## Storage And Safety

`runtime/hisabguard.sqlite3` stores records; `runtime/originals/` stores private binaries. Evidence is not exposed through a static directory. JSON export excludes secrets and original binaries; retain a separate private originals backup. Excluding an entry is a correction, not a deletion. Settled records cannot be edited through the normal evidence endpoints; duplicate evidence elsewhere can invalidate earlier assumptions and requires operator review.

This is a single-operator pilot. Before real public use, add a documented retention/deletion policy, encrypted backups, institutional access controls, upload rate/storage limits, and a security/data-protection review. Screenshots, synthetic signatures and model prose cannot establish independent financial truth.

## Specifications

- [PRD](PRD.md)
- [API contract](docs/api-contract.md)
- [Design contract](docs/design-contract.md)
- [Implementation plan](.opencode/plans/feature-settlement-hisabguard-1.md)

No actual messages, payments, courier requests or government submissions are sent. Do not claim real customer validation, money recovered, fraud detection, Devin use or public deployment without evidence.

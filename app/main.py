"""Private evidence APIs and explicit, safe production SPA routing."""

import hashlib
import hmac
import html
import ipaddress
import json
import os
import sqlite3
import threading
import uuid
import warnings
import wave
from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from . import agent, demo, providers
from .schemas import ActionDecision, CloseDecision, EvidenceCreate, EvidenceReview, Extraction, Reply, TripCreate
from .settlement import bdt
from .store import ROOT, Store, StoreError

MAX_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 20_000_000
IMAGE_TYPES = {"image/png": ("PNG", ".png"), "image/jpeg": ("JPEG", ".jpg"),
               "image/webp": ("WEBP", ".webp"), "image/gif": ("GIF", ".gif")}
AUDIO_TYPES = {"audio/wav": ("audio/wav", ".wav"), "audio/x-wav": ("audio/wav", ".wav"),
               "audio/mpeg": ("audio/mpeg", ".mp3"), "audio/mp3": ("audio/mpeg", ".mp3"),
               "audio/webm": ("audio/webm", ".webm"), "audio/ogg": ("audio/ogg", ".ogg")}


def validate_file(data, mime):
    if not data or len(data) > MAX_BYTES:
        raise StoreError(413, "Evidence must be nonempty and at most 10 MB")
    if mime in IMAGE_TYPES:
        from PIL import Image
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(data)) as image:
                    if image.format != IMAGE_TYPES[mime][0] or image.width * image.height > MAX_PIXELS:
                        raise ValueError("Image type or pixel limit")
                    image.verify()
            return "image", mime, IMAGE_TYPES[mime][1]
        except Exception:
            raise StoreError(415, "Invalid image or image exceeds the pixel limit") from None
    if mime in AUDIO_TYPES:
        canonical, extension = AUDIO_TYPES[mime]
        valid = False
        if extension == ".wav":
            try:
                with wave.open(BytesIO(data), "rb") as audio:
                    valid = (data[:4] == b"RIFF" and data[8:12] == b"WAVE" and
                             1 <= audio.getnchannels() <= 8 and 1 <= audio.getsampwidth() <= 4
                             and 1 <= audio.getframerate() <= 192000 and audio.getnframes() > 0)
            except Exception:
                valid = False
        elif extension == ".mp3":
            valid = (len(data) >= 10 and data[:3] == b"ID3" and data[3] in {2, 3, 4}
                     and all(byte < 128 for byte in data[6:10]))
            if len(data) >= 4 and data[0] == 255 and data[1] & 224 == 224:
                valid = bool(data[1] & 6 and data[2] >> 4 not in {0, 15} and data[2] & 12 != 12)
        elif extension == ".webm":
            valid = data.startswith(b"\x1a\x45\xdf\xa3") and b"webm" in data[:4096]
        elif extension == ".ogg":
            valid = len(data) >= 27 and data.startswith(b"OggS\x00") and (b"OpusHead" in data[:4096] or b"\x01vorbis" in data[:4096])
        if valid:
            return "audio", canonical, extension
        raise StoreError(415, "Invalid audio content signature")
    raise StoreError(415, "Only PNG, JPEG, WebP, GIF, WAV, MP3, WebM, and Ogg evidence is supported")


def process_upload(store, trip_id, data, title, kind_hint, mime):
    source_type, mime, extension = validate_file(data, mime)
    file_hash = hashlib.sha256(data).hexdigest()
    with store.connect() as db:
        trip = store.require(db, "trips", trip_id)
        if trip["status"] == "settled":
            raise StoreError(409, "Settled trip cannot be modified")
        if db.execute("SELECT id FROM evidence WHERE trip_id=? AND file_hash=?", (trip_id, file_hash)).fetchone():
            raise StoreError(409, "Identical original already exists on this trip")
    fields = {"title": title, "kind": kind_hint if source_type == "image" else "statement"}
    extraction_error = None
    try:
        status = providers.get_status()
        if source_type == "image":
            if not status.get("vision_configured"):
                raise ValueError("unavailable")
            extracted = providers.extract_image(data, mime)
        else:
            if not status.get("stt_configured"):
                raise ValueError("unavailable")
            transcript = providers.transcribe_audio(data, "voice-note" + extension, mime)
            if not isinstance(transcript, str) or not transcript.strip() or len(transcript) > 12000:
                raise ValueError("Invalid transcription")
            fields["text"] = transcript.strip()
            # Speech is always a statement, even if a model describes a payment.
            # The investigator may interpret it, but receipt evidence is separate.
            extracted = {"kind": "statement", "text": transcript.strip(),
                         "note": "Speech transcription, not a transaction receipt or delivery proof."}
        proposal = Extraction.model_validate(extracted)
        parsed = proposal.model_dump(exclude_unset=True)
        if proposal.title is None:
            parsed.pop("title", None)
        # Semantic type validation also applies to proposals, but wrong trip references
        # remain visible for explicit correction rather than being silently discarded.
        store.validate_confirmation({"code": proposal.trip_ref or trip["code"]}, proposal.model_dump())
        fields.update(parsed)
        if source_type == "audio":
            fields["text"] = transcript.strip()
    except Exception:
        extraction_error = "Extraction unavailable or invalid. Original retained; explicitly correct and review the fields before use."
    filename = uuid.uuid4().hex + extension
    path = store.originals / filename
    try:
        path.write_bytes(data)
        store.add_evidence(trip_id, fields, source_type=source_type, filename=filename,
                           mime=mime, file_hash=file_hash, extraction_error=extraction_error)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return store.detail(trip_id)


def render_report(detail):
    def escape(value):
        return html.escape(str(value if value is not None else ""), quote=True)

    trip, settlement = detail["trip"], detail["settlement"]
    financial = "".join(f"<tr><th>{escape(key)}</th><td>BDT {escape(settlement[key])}</td><td>{escape(', '.join('#' + str(item) for item in ids))}</td></tr>"
                        for key, ids in settlement["sources"].items())
    issues = "".join(f"<li><strong>{escape(issue['severity'])}: {escape(issue['title'])}</strong> {escape(issue['detail'])} Evidence: {escape(issue['evidence_ids'])}</li>" for issue in settlement["issues"])
    evidence = "".join(f"<section><h3>Evidence #{row['id']}: {escape(row['title'])}</h3><p>{escape(row['kind'])}; state: {escape(row['state'])}; source: {escape(row['source_type'])}; synthetic: {escape(row['synthetic'])}</p><p>BDT {escape(row['amount_bdt'])}; transaction: {escape(row['transaction_id'])}; trip ref: {escape(row['trip_ref'])}; delivered: {escape(row['delivered'])}</p><p>{escape(row['note'])}</p><pre>{escape(row['text'])}</pre><p>Extraction error: {escape(row['extraction_error'])}; field confidence: {escape(json.dumps(row['confidence']))}; original: {escape(row['filename'])}</p></section>" for row in detail["evidence"])
    actions = "".join(f"<section><h3>Draft #{row['id']}: {escape(row['status'])}, revision {row['revision']}</h3><p>Recipient: {escape(row['recipient'])}; evidence {escape(row['evidence_ids'])}</p><pre>{escape(row['message'])}</pre></section>" for row in detail["actions"])
    runs = "".join(f"<section><h3>Investigation #{row['id']}: {escape(row['mode'])} / {escape(row['status'])}, revision {row['revision']}</h3><pre>{escape(row['summary'])}</pre><p>Question: {escape(row['question'])}; evidence {escape(row['evidence_ids'])}</p></section>" for row in detail["investigations"])
    audit = "".join(f"<li>#{row['id']} {escape(row['created_at'])} {escape(row['actor'])}: {escape(row['event'])} {escape(json.dumps(row['detail']))}</li>" for row in detail["audit"])
    return ("<!doctype html><html lang='en'><head><meta charset='utf-8'><title>HisabGuard evidence packet</title>"
            "<style>body{font:15px system-ui;margin:2rem;color:#17243a}table{border-collapse:collapse}th,td{border:1px solid #aaa;padding:.5rem;text-align:left}pre{white-space:pre-wrap;overflow-wrap:anywhere}section{break-inside:avoid;border-top:1px solid #ccc} @media print{body{margin:.5in}}</style></head><body>"
            f"<h1>{escape(trip['code'])} evidence packet</h1><p>{escape(trip['customer'])}; driver {escape(trip['driver'])}; truck {escape(trip['truck'])}; {escape(trip['origin'])} to {escape(trip['destination'])}</p>"
            f"<p>Status: {escape(trip['status'])}; revision {trip['revision']}; delivery confirmed: {escape(settlement['delivery_confirmed'])}; eligible for human settlement review: {escape(settlement['can_settle'])}</p>"
            "<p>Synthetic documents are labelled. Human-reviewed records are not independent bank or provider verification. Approved follow-ups are drafts only, never sent.</p>"
            f"<h2>Independent settlement and sources</h2><table><tr><th>Total</th><th>BDT</th><th>Evidence ids</th></tr>{financial}</table><h2>Findings</h2><ul>{issues}</ul><h2>Evidence index</h2>{evidence}<h2>Investigations</h2>{runs}<h2>Follow-up proposals</h2>{actions}<h2>Audit trail</h2><ul>{audit}</ul></body></html>")


def create_app(data_dir=None):
    @asynccontextmanager
    async def lifespan(application):
        application.state.judge_mode = os.getenv("HISABGUARD_JUDGE_MODE") == "1"
        directory = data_dir
        if application.state.judge_mode:
            directory = data_dir or os.getenv("HISABGUARD_DATA_DIR")
            if not directory or Path(directory).resolve() == (ROOT / "runtime").resolve():
                raise RuntimeError("Judge mode requires an explicit isolated data directory, not the normal runtime")
            application.state.judge_token = os.getenv("HISABGUARD_ACCESS_TOKEN", "")
            if not application.state.judge_token.strip():
                raise RuntimeError("Judge mode requires an access token, including on loopback")
            try:
                maximum = int(os.getenv("HISABGUARD_JUDGE_MAX_RUNS", "20"))
            except ValueError:
                raise RuntimeError("Judge investigation limit must be an integer from 1 to 1000") from None
            if not 1 <= maximum <= 1000:
                raise RuntimeError("Judge investigation limit must be an integer from 1 to 1000")
            application.state.judge_max_runs = maximum
        application.state.store = await run_in_threadpool(Store, directory, judge_mode=application.state.judge_mode)
        if os.getenv("HISABGUARD_SEED_DEMO", "1") != "0":
            await run_in_threadpool(demo.seed, application.state.store)
        yield

    application = FastAPI(title="HisabGuard", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    application.state.judge_mode = False
    application.state.judge_run_lock = threading.Lock()
    application.state.judge_budget_lock = threading.Lock()
    application.state.judge_runs_attempted = 0

    @application.exception_handler(StoreError)
    async def store_error(request, exc):
        return JSONResponse({"detail": exc.detail}, status_code=exc.status)

    @application.exception_handler(sqlite3.Error)
    async def database_error(request, exc):
        return JSONResponse({"detail": "Storage is temporarily unavailable; no partial transaction was committed. Retry the request."}, status_code=503)

    @application.exception_handler(Exception)
    async def unexpected_error(request, exc):
        return JSONResponse({"detail": "Request failed safely. Please retry."}, status_code=500)

    @application.middleware("http")
    async def access(request: Request, call_next):
        if request.url.path == "/api" or request.url.path.startswith("/api/"):
            public = request.method == "GET" and request.url.path == "/api/status"
            if not public:
                token = request.app.state.judge_token if request.app.state.judge_mode else os.getenv("HISABGUARD_ACCESS_TOKEN", "")
                if token:
                    supplied = request.headers.get("authorization", "")
                    if not hmac.compare_digest(supplied.encode(), ("Bearer " + token).encode()):
                        return JSONResponse({"detail": "Access token required"}, status_code=401)
                else:
                    try:
                        loopback = request.client is not None and ipaddress.ip_address(request.client.host).is_loopback
                    except ValueError:
                        loopback = request.client is not None and request.client.host == "localhost"
                    hostname = request.url.hostname or ""
                    try:
                        local_host = ipaddress.ip_address(hostname).is_loopback
                    except ValueError:
                        local_host = hostname == "localhost"
                    if not loopback or not local_host:
                        return JSONResponse({"detail": "Configure an access token before non-loopback access"}, status_code=401)
            if request.method not in {"GET", "HEAD", "OPTIONS"}:
                origin = request.headers.get("origin")
                allowed = {str(request.base_url).rstrip("/")}
                configured = os.getenv("HISABGUARD_DEV_ORIGIN", "")
                allowed.update(value.strip().rstrip("/") for value in configured.split(",") if value.strip())
                if origin and (origin not in allowed or urlsplit(origin).scheme not in {"http", "https"}):
                    return JSONResponse({"detail": "Cross-origin writes are not allowed"}, status_code=403)
            segments = request.url.path.split("/")
            if (request.app.state.judge_mode and request.method == "POST" and len(segments) == 5
                    and segments[1:3] == ["api", "trips"] and segments[4] == "upload"):
                return JSONResponse({"detail": "Uploads are disabled in judge mode; use synthetic manual examples only"}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        if request.url.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-store"
        return response

    def store(request):
        return request.app.state.store

    @application.get("/api/status")
    def status(request: Request):
        configured = providers.get_status()
        model = bool(configured.get("model_configured"))
        state = request.app.state
        with state.judge_budget_lock:
            remaining = max(0, state.judge_max_runs - state.judge_runs_attempted) if state.judge_mode else None
        return {"model_configured": model, "model_name": configured.get("model_name"),
                "vision_configured": not state.judge_mode and bool(configured.get("vision_configured")),
                "stt_configured": not state.judge_mode and bool(configured.get("stt_configured")), "mode": "model" if model else "demo",
                "external_delivery": "draft_only", "demo": True,
                "auth_required": state.judge_mode or bool(os.getenv("HISABGUARD_ACCESS_TOKEN")),
                "judge_mode": state.judge_mode, "uploads_enabled": not state.judge_mode,
                "judge_runs_remaining": remaining}

    @application.get("/api/trips")
    def trips(request: Request):
        repository = store(request)
        with repository.connect() as db:
            details = [repository.detail(row[0], db) for row in db.execute("SELECT id FROM trips ORDER BY id")]
        summaries = []
        for item in details:
            summaries.append({**item["trip"], **{key: item["settlement"][key] for key in
                ("invoice_bdt", "received_bdt", "outstanding_bdt", "expense_bdt", "advance_bdt", "advance_balance_bdt")},
                "evidence_count": len(item["evidence"]), "exceptions_count": sum(issue["severity"] == "blocking" for issue in item["settlement"]["issues"])})
        return {"trips": summaries, "overview": {"trips": len(summaries), "exceptions": sum(item["exceptions_count"] for item in summaries),
                "outstanding_bdt": bdt(sum(max(int(item["outstanding_bdt"].replace(".", "")), 0) for item in summaries)),
                "pending_approvals": sum(action["status"] == "pending" for item in details for action in item["actions"])}}

    @application.post("/api/demo/reset")
    def reset_demo(request: Request):
        state = request.app.state
        if not state.judge_mode:
            raise StoreError(403, "Demo reset is available only in the isolated judge sandbox")
        if not state.judge_run_lock.acquire(blocking=False):
            raise StoreError(409, "An investigation or demo reset is in progress; wait for it to finish")
        try:
            store(request).reset_demo()
            return trips(request)
        finally:
            state.judge_run_lock.release()

    @application.post("/api/trips")
    def create_trip(request: Request, body: TripCreate):
        repository = store(request)
        return repository.detail(repository.create_trip(body.model_dump()))

    @application.get("/api/trips/{trip_id}")
    def trip_detail(trip_id: int, request: Request):
        return store(request).detail(trip_id)

    @application.post("/api/trips/{trip_id}/evidence")
    def add_evidence(trip_id: int, request: Request, body: EvidenceCreate):
        repository = store(request)
        repository.add_evidence(trip_id, body.model_dump(), synthetic=request.app.state.judge_mode)
        return repository.detail(trip_id)

    @application.post("/api/trips/{trip_id}/upload")
    async def upload(trip_id: int, request: Request, file: UploadFile = File(...), title: str = Form(...), kind_hint: str = Form(...)):
        try:
            body = EvidenceCreate.model_validate({"kind": kind_hint, "title": title})
        except ValidationError:
            raise StoreError(422, "A valid evidence kind and nonempty title are required") from None
        try:
            data = await file.read(MAX_BYTES + 1)
            return await run_in_threadpool(process_upload, store(request), trip_id, data, body.title, body.kind, file.content_type)
        finally:
            await file.close()

    @application.post("/api/evidence/{evidence_id}/review")
    def review_evidence(evidence_id: int, request: Request, body: EvidenceReview):
        repository = store(request)
        trip_id = repository.review(evidence_id, body.decision, body.fields.model_dump(exclude_unset=True) if body.fields else None)
        return repository.detail(trip_id)

    @application.get("/api/evidence/{evidence_id}/file")
    def original(evidence_id: int, request: Request):
        path, mime = store(request).original_path(evidence_id)
        return FileResponse(path, media_type=mime, filename=path.name, content_disposition_type="inline", headers={"Cache-Control": "no-store"})

    @application.post("/api/trips/{trip_id}/investigate")
    def investigate_trip(trip_id: int, request: Request):
        repository = store(request)
        state = request.app.state
        if state.judge_mode:
            if not state.judge_run_lock.acquire(blocking=False):
                raise StoreError(409, "An investigation or demo reset is in progress; wait for it to finish")
            try:
                with repository.connect() as db:
                    trip = repository.require(db, "trips", trip_id)
                    if trip["status"] == "settled":
                        raise StoreError(409, "Settled trip cannot be investigated")
                if providers.get_status().get("model_configured"):
                    with state.judge_budget_lock:
                        if state.judge_runs_attempted >= state.judge_max_runs:
                            raise StoreError(429, "Judge model investigation budget exhausted")
                        # Failed upstream attempts still consume credits; never refund this count.
                        state.judge_runs_attempted += 1
                agent.investigate(repository, trip_id)
                return repository.detail(trip_id)
            finally:
                state.judge_run_lock.release()
        agent.investigate(repository, trip_id)
        return repository.detail(trip_id)

    @application.post("/api/trips/{trip_id}/reply")
    def reply(trip_id: int, request: Request, body: Reply):
        repository = store(request)
        repository.add_evidence(trip_id, {"kind": "statement", "title": "Operator-recorded response", "text": body.text,
            "note": "Explicitly reviewed operator-recorded statement; not payment or external verification."},
            confirmed=True, synthetic=request.app.state.judge_mode)
        return repository.detail(trip_id)

    @application.post("/api/actions/{action_id}/decision")
    def decide_action(action_id: int, request: Request, body: ActionDecision):
        repository = store(request)
        return repository.detail(repository.action_decision(action_id, body.decision))

    @application.get("/api/actions/{action_id}/export")
    def export_action(action_id: int, request: Request):
        message = store(request).export_action(action_id)
        return Response(message.encode("utf-8"), media_type="text/plain; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="followup-{action_id}.txt"'})

    @application.post("/api/trips/{trip_id}/close")
    def close(trip_id: int, request: Request, body: CloseDecision):
        repository = store(request)
        repository.close(trip_id)
        return repository.detail(trip_id)

    @application.get("/api/trips/{trip_id}/report", response_class=HTMLResponse)
    def report(trip_id: int, request: Request):
        return HTMLResponse(render_report(store(request).detail(trip_id)), headers={
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"})

    @application.get("/api/export")
    def backup(request: Request):
        repository = store(request)
        with repository.connect() as db:
            return {"version": "hisabguard.backup.v1", "trips": [repository.detail(row[0], db) for row in db.execute("SELECT id FROM trips ORDER BY id")],
                    "originals_included": False, "note": "Original binaries and secret configuration are not included. Keep a separate private originals backup."}

    @application.get("/api/activity")
    def activity(request: Request):
        repository = store(request)
        with repository.connect() as db:
            return {"activity": repository.history(db, "audit")}

    @application.api_route("/api/{unknown:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
    @application.api_route("/api", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
    def unknown_api(unknown: str = ""):
        return JSONResponse({"detail": "API route not found"}, status_code=404)

    distribution = ROOT / "web" / "dist"
    assets = distribution / "assets"
    if assets.is_dir():
        application.mount("/assets", StaticFiles(directory=assets), name="assets")

    @application.get("/{client_route:path}")
    def client(client_route: str):
        if client_route == "ui":
            return RedirectResponse("/", status_code=307)
        segments = client_route.split("/")
        allowed = client_route in {"", "activity", "settings", "trips/new"} or (len(segments) == 2 and segments[0] == "trips" and segments[1].isascii() and segments[1].isdigit())
        if not allowed:
            return JSONResponse({"detail": "Route not found"}, status_code=404)
        index = distribution / "index.html"
        if not index.is_file():
            return JSONResponse({"detail": "Frontend build is unavailable"}, status_code=404)
        return FileResponse(index, media_type="text/html")

    return application


app = create_app()

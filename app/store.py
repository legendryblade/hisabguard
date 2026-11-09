"""Small transactional SQLite store with private originals and explicit write fields."""

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager, nullcontext
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from .schemas import FINANCIAL_KINDS, ReviewFields
from .settlement import calculate, transaction_key, validate_followup

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_FIELDS = {"kind", "title", "amount_bdt", "transaction_id", "trip_ref", "note", "text", "delivered", "confidence"}
RUN_LEASE_SECONDS = 600
MODEL_DRAFT_LABEL = "Proposed follow-up draft for human review. Not verified truth; no external verification was performed.\n\n"


class StoreError(Exception):
    def __init__(self, status: int, detail: str):
        self.status, self.detail = status, detail
        super().__init__(detail)


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, data_dir=None, *, judge_mode=False):
        directory = data_dir or os.getenv("HISABGUARD_DATA_DIR")
        if judge_mode and (not directory or Path(directory).resolve() == (ROOT / "runtime").resolve()):
            raise RuntimeError("Judge mode requires an explicit isolated data directory, not the normal runtime")
        self.judge_mode = judge_mode
        self.data_dir = Path(directory or ROOT / "runtime").resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.originals = self.data_dir / "originals"
        self.originals.mkdir(exist_ok=True)
        self.db_path = self.data_dir / "hisabguard.sqlite3"
        with self.connect(transaction=False) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS trips (
                    id INTEGER PRIMARY KEY, code TEXT UNIQUE NOT NULL,
                    customer TEXT NOT NULL, driver TEXT NOT NULL, truck TEXT NOT NULL,
                    origin TEXT NOT NULL, destination TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'collecting', revision INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS evidence (
                    id INTEGER PRIMARY KEY, trip_id INTEGER NOT NULL REFERENCES trips(id),
                    title TEXT NOT NULL, kind TEXT NOT NULL, original_kind TEXT NOT NULL,
                    state TEXT NOT NULL DEFAULT 'draft', amount_paisa INTEGER,
                    transaction_id TEXT, trip_ref TEXT, note TEXT, text TEXT, delivered INTEGER,
                    confidence TEXT NOT NULL DEFAULT '{}', source_type TEXT NOT NULL,
                    synthetic INTEGER NOT NULL DEFAULT 0, filename TEXT, mime TEXT,
                    file_hash TEXT, extraction_error TEXT, created_at TEXT NOT NULL);
                CREATE UNIQUE INDEX IF NOT EXISTS evidence_file_unique
                    ON evidence(trip_id,file_hash) WHERE file_hash IS NOT NULL;
                CREATE INDEX IF NOT EXISTS evidence_transaction ON evidence(transaction_id);
                CREATE TABLE IF NOT EXISTS investigations (
                    id INTEGER PRIMARY KEY, trip_id INTEGER NOT NULL REFERENCES trips(id),
                    revision INTEGER NOT NULL, mode TEXT NOT NULL, status TEXT NOT NULL,
                    summary TEXT NOT NULL DEFAULT '', question TEXT, recipient TEXT,
                    evidence_ids TEXT NOT NULL DEFAULT '[]', steps TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS actions (
                    id INTEGER PRIMARY KEY, trip_id INTEGER NOT NULL REFERENCES trips(id),
                    revision INTEGER NOT NULL, kind TEXT NOT NULL DEFAULT 'followup',
                    recipient TEXT NOT NULL, message TEXT NOT NULL, evidence_ids TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS audit (
                    id INTEGER PRIMARY KEY, trip_id INTEGER REFERENCES trips(id),
                    actor TEXT NOT NULL, event TEXT NOT NULL, detail TEXT NOT NULL,
                    created_at TEXT NOT NULL);
            """)

    @contextmanager
    def connect(self, write=False, transaction=True):
        db = sqlite3.connect(self.db_path, timeout=5, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.create_function("transaction_key", 1, transaction_key, deterministic=True)
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=5000")
        try:
            if transaction:
                db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def require(self, db, table, record_id):
        if table not in {"trips", "evidence", "actions", "investigations"}:
            raise ValueError("invalid table")
        row = db.execute(f"SELECT * FROM {table} WHERE id=?", (record_id,)).fetchone()
        if row is None:
            raise StoreError(404, "Record not found")
        return dict(row)

    def audit(self, db, trip_id, actor, event, detail):
        db.execute("INSERT INTO audit(trip_id,actor,event,detail,created_at) VALUES(?,?,?,?,?)",
                   (trip_id, actor, event, json.dumps(detail), now()))

    def reset_demo(self):
        if not self.judge_mode or self.data_dir == (ROOT / "runtime").resolve():
            raise StoreError(403, "Demo reset is available only in the isolated judge sandbox")
        from . import demo
        with self.connect(True) as db:
            if db.execute("SELECT 1 FROM evidence WHERE synthetic!=1 LIMIT 1").fetchone():
                raise StoreError(409, "Demo reset refused: non-synthetic evidence exists")
            if db.execute("SELECT 1 FROM investigations WHERE status='investigating' LIMIT 1").fetchone():
                raise StoreError(409, "An investigation is still in progress; demo reset refused")
            for table in ("audit", "actions", "investigations", "evidence", "trips"):
                db.execute(f"DELETE FROM {table}")
            # Reuse the seeder inside this transaction, retaining all original binaries.
            demo.seed(SimpleNamespace(connect=lambda *args: nullcontext(db), originals=self.originals,
                                      insert_trip=self.insert_trip, insert_evidence=self.insert_evidence))
            self.audit(db, None, "operator", "demo_reset", {"synthetic": True})

    def bump(self, db, trip_ids):
        for trip_id in set(trip_ids):
            db.execute("UPDATE trips SET revision=revision+1,status='collecting' WHERE id=?", (trip_id,))
            db.execute("UPDATE actions SET status='stale' WHERE trip_id=? AND status='pending'", (trip_id,))

    def affected(self, db, trip_id, transaction_ids, hashes):
        affected = {trip_id}
        for field, values in (("transaction_id", transaction_ids), ("file_hash", hashes)):
            for value in set(values) - {None, ""}:
                column = "transaction_key(transaction_id)" if field == "transaction_id" else field
                value = transaction_key(value) if field == "transaction_id" else value
                affected.update(row[0] for row in db.execute(
                    f"SELECT DISTINCT trip_id FROM evidence WHERE {column}=? AND state='confirmed'", (value,)))
        return affected

    def create_trip(self, fields):
        if set(fields) - {"code", "customer", "driver", "truck", "origin", "destination"}:
            raise ValueError("unknown trip fields")
        with self.connect(True) as db:
            return self.insert_trip(db, fields)

    def insert_trip(self, db, fields):
        code = fields.get("code") or f"TRIP-{uuid.uuid4().hex[:8].upper()}"
        try:
            record_id = db.execute("INSERT INTO trips(code,customer,driver,truck,origin,destination,created_at) VALUES(?,?,?,?,?,?,?)",
                (code, fields["customer"], fields["driver"], fields["truck"], fields.get("origin", ""), fields.get("destination", ""), now())).lastrowid
        except sqlite3.IntegrityError as exc:
            raise StoreError(409, "Trip code already exists") from exc
        self.audit(db, record_id, "operator", "trip_created", {"code": code})
        return record_id

    def insert_evidence(self, db, trip_id, fields, *, source_type="manual", synthetic=False,
                        confirmed=False, filename=None, mime=None, file_hash=None, extraction_error=None):
        if set(fields) - EVIDENCE_FIELDS:
            raise ValueError("unknown evidence fields")
        trip = self.require(db, "trips", trip_id)
        if trip["status"] == "settled":
            raise StoreError(409, "Settled trip cannot be modified")
        parsed = ReviewFields.model_validate({key: value for key, value in fields.items() if key in ReviewFields.model_fields})
        if confirmed:
            self.validate_confirmation(trip, parsed.model_dump())
        amount = parsed.amount_bdt
        paisa = int(amount.replace(".", "")) if amount is not None else None
        try:
            record_id = db.execute("""INSERT INTO evidence(trip_id,title,kind,original_kind,state,amount_paisa,
                transaction_id,trip_ref,note,text,delivered,confidence,source_type,synthetic,filename,mime,file_hash,extraction_error,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (trip_id, fields["title"], parsed.kind, parsed.kind, "confirmed" if confirmed else "draft", paisa,
                 parsed.transaction_id, parsed.trip_ref, parsed.note, parsed.text, parsed.delivered,
                 json.dumps(fields.get("confidence", {})), source_type, int(synthetic), filename, mime,
                 file_hash, extraction_error, now())).lastrowid
        except sqlite3.IntegrityError as exc:
            raise StoreError(409, "Identical original already exists on this trip") from exc
        self.bump(db, self.affected(db, trip_id, [parsed.transaction_id] if confirmed else [], [file_hash] if confirmed else []))
        self.audit(db, trip_id, "synthetic_reviewer" if synthetic else "operator", "evidence_added",
                   {"evidence_id": record_id, "source_type": source_type, "synthetic": synthetic, "state": "confirmed" if confirmed else "draft"})
        return record_id

    def add_evidence(self, trip_id, fields, **kwargs):
        with self.connect(True) as db:
            return self.insert_evidence(db, trip_id, fields, **kwargs)

    def validate_confirmation(self, trip, fields):
        if fields.get("trip_ref") and fields["trip_ref"] != trip["code"]:
            raise StoreError(409, "Evidence trip reference does not match this trip; correct it before confirming")
        if fields["kind"] in FINANCIAL_KINDS and fields.get("amount_bdt") is None:
            raise StoreError(422, "Financial evidence requires an explicit amount")
        if fields["kind"] not in FINANCIAL_KINDS and fields.get("amount_bdt") is not None:
            raise StoreError(422, "Statements and delivery records cannot carry ledger amounts")
        if fields["kind"] != "delivery" and fields.get("delivered") is not None:
            raise StoreError(422, "Only delivery evidence may confirm delivery")
        if fields["kind"] == "delivery" and fields.get("delivered") is None:
            raise StoreError(422, "Delivery evidence requires an explicit delivered value")

    def review(self, evidence_id, decision, fields=None):
        with self.connect(True) as db:
            old = self.require(db, "evidence", evidence_id)
            trip = self.require(db, "trips", old["trip_id"])
            if trip["status"] == "settled":
                raise StoreError(409, "Settled trip cannot be modified")
            merged = {key: self.serialize_evidence(old)[key] for key in ReviewFields.model_fields}
            if fields is not None and decision == "confirm":
                if set(fields) - set(ReviewFields.model_fields):
                    raise StoreError(422, "Unknown review field")
                merged.update(fields)
            parsed = ReviewFields.model_validate(merged).model_dump()
            if decision == "confirm" and "statement" in {old["original_kind"], old["kind"]} and parsed["kind"] != "statement":
                raise StoreError(409, "A statement cannot be converted into a transaction or delivery proof")
            if decision == "confirm":
                self.validate_confirmation(trip, parsed)
                if old["extraction_error"] and fields is None:
                    raise StoreError(422, "Extraction failed; explicitly correct fields before confirming")
            amount = parsed["amount_bdt"]
            affected = self.affected(db, old["trip_id"], [old["transaction_id"], parsed["transaction_id"]], [old["file_hash"]])
            db.execute("""UPDATE evidence SET state=?,kind=?,amount_paisa=?,transaction_id=?,trip_ref=?,note=?,text=?,delivered=?,extraction_error=? WHERE id=?""",
                ("confirmed" if decision == "confirm" else "excluded", parsed["kind"],
                 int(amount.replace(".", "")) if amount is not None else None, parsed["transaction_id"],
                 parsed["trip_ref"], parsed["note"], parsed["text"], parsed["delivered"],
                 None if decision == "confirm" else old["extraction_error"], evidence_id))
            affected.update(self.affected(db, old["trip_id"], [parsed["transaction_id"]], [old["file_hash"]]))
            self.bump(db, affected)
            self.audit(db, old["trip_id"], "operator", "evidence_reviewed",
                       {"evidence_id": evidence_id, "decision": decision, "corrected_fields": list(fields or {}), "source_type": old["source_type"]})
            return old["trip_id"]

    def serialize_evidence(self, row):
        from .settlement import bdt
        result = {key: row[key] for key in ("id", "trip_id", "title", "kind", "state", "transaction_id", "trip_ref", "note", "text", "source_type", "filename", "mime", "extraction_error", "created_at")}
        result.update(amount_bdt=bdt(row["amount_paisa"]) if row["amount_paisa"] is not None else None,
                      delivered=bool(row["delivered"]) if row["delivered"] is not None else None,
                      confidence=json.loads(row["confidence"]), synthetic=bool(row["synthetic"]))
        return result

    def all_evidence(self, db):
        rows = [dict(row) for row in db.execute("SELECT * FROM evidence ORDER BY id")]
        for row in rows:
            row["delivered"] = bool(row["delivered"]) if row["delivered"] is not None else None
        return rows

    def history(self, db, table, trip_id=None):
        if table not in {"investigations", "actions", "audit"}:
            raise ValueError("invalid history table")
        query = f"SELECT * FROM {table}"
        filters = ["status!='investigating'"] if table == "investigations" else []
        args = ()
        if trip_id is not None:
            filters.append("trip_id=?")
            args = (trip_id,)
        if filters:
            query += " WHERE " + " AND ".join(filters)
        rows = [dict(row) for row in db.execute(query + " ORDER BY id", args)]
        for row in rows:
            for field in {"steps", "evidence_ids", "detail"} & row.keys():
                row[field] = json.loads(row[field])
        return rows

    def detail(self, trip_id, db=None):
        if db is None:
            with self.connect() as connection:
                return self.detail(trip_id, connection)
        trip = self.require(db, "trips", trip_id)
        rows = self.all_evidence(db)
        return {"trip": trip, "evidence": [self.serialize_evidence(row) for row in rows if row["trip_id"] == trip_id],
                "settlement": calculate(trip_id, rows),
                **{table: self.history(db, table, trip_id) for table in ("investigations", "actions", "audit")}}

    def start_run(self, trip_id, mode):
        with self.connect(True) as db:
            trip = self.require(db, "trips", trip_id)
            if trip["status"] == "settled":
                raise StoreError(409, "Settled trip cannot be investigated")
            cutoff = (datetime.now(timezone.utc) - timedelta(seconds=RUN_LEASE_SECONDS)).isoformat()
            active = db.execute("SELECT id,created_at FROM investigations WHERE trip_id=? AND status='investigating'", (trip_id,)).fetchall()
            if any(row["created_at"] > cutoff for row in active):
                raise StoreError(409, "An investigation is already in progress for this trip; wait for it to finish")
            for row in active:
                db.execute("UPDATE investigations SET status='failed',summary=? WHERE id=?",
                           ("Investigation expired without completion. No follow-up was committed; retry the investigation.", row["id"]))
                self.audit(db, trip_id, "system", "investigation_expired", {"investigation_id": row["id"]})
            run_id = db.execute("INSERT INTO investigations(trip_id,revision,mode,status,created_at) VALUES(?,?,?,?,?)",
                                (trip_id, trip["revision"], mode, "investigating", now())).lastrowid
            db.execute("UPDATE trips SET status='investigating' WHERE id=?", (trip_id,))
            self.audit(db, trip_id, mode, "investigation_started", {"investigation_id": run_id, "revision": trip["revision"]})
            return run_id, trip["revision"]

    def record_step(self, run_id, step):
        with self.connect(True) as db:
            run = self.require(db, "investigations", run_id)
            if run["status"] != "investigating":
                raise StoreError(409, "Investigation is no longer active; no further tool result was committed")
            steps = json.loads(run["steps"])
            steps.append(step)
            db.execute("UPDATE investigations SET steps=? WHERE id=?", (json.dumps(steps), run_id))

    def finish_run(self, run_id, *, summary, evidence_ids, question=None, recipient=None, followup=None, failed=False):
        with self.connect(True) as db:
            run = self.require(db, "investigations", run_id)
            if run["status"] != "investigating":
                raise StoreError(409, "Investigation is no longer active; no new action was committed")
            detail = self.detail(run["trip_id"], db)
            if not failed and datetime.fromisoformat(run["created_at"]) <= datetime.now(timezone.utc) - timedelta(seconds=RUN_LEASE_SECONDS):
                raise StoreError(409, "Investigation expired; retry against the current evidence")
            if not failed and detail["trip"]["revision"] != run["revision"]:
                raise StoreError(409, "Evidence changed during investigation; investigate the current revision")
            if not failed and detail["trip"]["status"] == "settled":
                raise StoreError(409, "Trip was settled during investigation; no new action was committed")
            local_ids = {row["id"] for row in detail["evidence"]}
            ids = set(evidence_ids) | set(followup["evidence_ids"] if followup else [])
            if not ids <= local_ids:
                raise StoreError(422, "Investigation evidence ids must belong to this trip")
            if followup and not failed and run["mode"] == "model":
                try:
                    validate_followup(detail, followup)
                except ValueError as exc:
                    raise StoreError(422, str(exc)) from None
            pending = any(row["status"] == "pending" and row["revision"] == run["revision"] for row in detail["actions"])
            existing_question = any(row["question"] and row["revision"] == run["revision"] and row["status"] != "failed" for row in detail["investigations"])
            if existing_question:
                question, recipient = None, None
            status = "failed" if failed else "awaiting_response" if question else "completed"
            db.execute("UPDATE investigations SET status=?,summary=?,question=?,recipient=?,evidence_ids=? WHERE id=?",
                       (status, summary, question, recipient, json.dumps(evidence_ids), run_id))
            if followup and not failed and not pending:
                db.execute("INSERT INTO actions(trip_id,revision,recipient,message,evidence_ids,created_at) VALUES(?,?,?,?,?,?)",
                           (run["trip_id"], run["revision"], followup["recipient"],
                            (MODEL_DRAFT_LABEL if run["mode"] == "model" else "") + followup["message"], json.dumps(followup["evidence_ids"]), now()))
            if detail["trip"]["revision"] == run["revision"] and detail["trip"]["status"] != "settled":
                trip_status = "unresolved" if failed else "awaiting_response" if question else "ready_for_review" if detail["settlement"]["can_settle"] else "unresolved"
                db.execute("UPDATE trips SET status=? WHERE id=?", (trip_status, run["trip_id"]))
            self.audit(db, run["trip_id"], run["mode"], "investigation_failed" if failed else "investigation_finished", {"investigation_id": run_id, "status": status})

    def action_decision(self, action_id, decision):
        with self.connect(True) as db:
            action = self.require(db, "actions", action_id)
            trip = self.require(db, "trips", action["trip_id"])
            if action["revision"] != trip["revision"] or action["status"] == "stale":
                raise StoreError(409, "Action is stale; investigate the current evidence revision")
            if action["status"] != "pending":
                raise StoreError(409, "Only pending actions can be decided")
            db.execute("UPDATE actions SET status=? WHERE id=?", ("approved" if decision == "approve" else "rejected", action_id))
            self.audit(db, action["trip_id"], "operator", "action_" + decision, {"action_id": action_id, "delivery": "draft_only"})
            return action["trip_id"]

    def export_action(self, action_id):
        with self.connect() as db:
            action = self.require(db, "actions", action_id)
            trip = self.require(db, "trips", action["trip_id"])
            if action["status"] != "approved" or action["revision"] != trip["revision"]:
                raise StoreError(409, "Only an approved current-revision draft may be exported")
            return action["message"]

    def close(self, trip_id):
        with self.connect(True) as db:
            detail = self.detail(trip_id, db)
            if detail["trip"]["status"] == "settled":
                raise StoreError(409, "Trip is already settled")
            if db.execute("SELECT 1 FROM investigations WHERE trip_id=? AND status='investigating'", (trip_id,)).fetchone():
                raise StoreError(409, "An investigation is still in progress; settlement cannot close until it finishes")
            current_runs = [run for run in detail["investigations"] if run["revision"] == detail["trip"]["revision"]]
            completed = bool(current_runs) and current_runs[-1]["status"] == "completed"
            if not detail["settlement"]["can_settle"] or not completed:
                raise StoreError(409, "Settlement requires a completed current-revision investigation and no blocking issues")
            db.execute("UPDATE trips SET status='settled' WHERE id=?", (trip_id,))
            self.audit(db, trip_id, "operator", "settlement_closed", {"revision": detail["trip"]["revision"], "sources": detail["settlement"]["sources"]})

    def original_path(self, evidence_id):
        with self.connect() as db:
            row = self.require(db, "evidence", evidence_id)
        filename = row["filename"]
        if not filename or Path(filename).name != filename:
            raise StoreError(404, "Original file not found")
        path = (self.originals / filename).resolve()
        if path.parent != self.originals.resolve() or not path.is_file():
            raise StoreError(404, "Original file not found")
        return path, row["mime"]

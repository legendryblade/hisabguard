"""Controlled workflows: temporary SQLite, synthetic documents, no live providers."""

import json
import threading
import wave
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import providers
from app.main import MAX_BYTES, create_app
from app.store import RUN_LEASE_SECONDS, StoreError


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("HISABGUARD_DATA_DIR", str(tmp_path / "data"))
    for name in ("HISABGUARD_ACCESS_TOKEN", "HISABGUARD_DEV_ORIGIN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(providers, "get_status", lambda: {
        "model_configured": False, "model_name": None, "vision_configured": False, "stt_configured": False})

    def unexpected(*args, **kwargs):
        raise AssertionError("No live provider calls permitted")

    for name in ("agent_turn", "extract_image", "transcribe_audio"):
        monkeypatch.setattr(providers, name, unexpected)
    with TestClient(create_app(), base_url="http://127.0.0.1", client=("127.0.0.1", 50000)) as connection:
        yield connection


def trip(client, code="TRIP-104"):
    item = next(item for item in client.get("/api/trips").json()["trips"] if item["code"] == code)
    return client.get(f"/api/trips/{item['id']}").json()


def create_trip(client, **fields):
    response = client.post("/api/trips", json={"customer": "Test customer", "driver": "Test driver", "truck": "TEST", **fields})
    assert response.status_code == 200, response.text
    return response.json()


def add(client, trip_id, kind, amount=None, **fields):
    body = {"kind": kind, "title": "Operator " + kind, **fields}
    if amount is not None:
        body["amount_bdt"] = amount
    response = client.post(f"/api/trips/{trip_id}/evidence", json=body)
    assert response.status_code == 200, response.text
    return response.json()["evidence"][-1]


def confirm(client, evidence_id, fields=None):
    body = {"decision": "confirm"}
    if fields is not None:
        body["fields"] = fields
    response = client.post(f"/api/evidence/{evidence_id}/review", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def image_bytes(color="white"):
    stream = BytesIO()
    Image.new("RGB", (80, 50), color).save(stream, "PNG")
    return stream.getvalue()


def upload(client, trip_id, data=None, mime="image/png", filename="receipt.png", kind="payment"):
    return client.post(f"/api/trips/{trip_id}/upload", data={"title": "Live input", "kind_hint": kind},
                       files={"file": (filename, image_bytes() if data is None else data, mime)})


def enable_model(monkeypatch, **flags):
    monkeypatch.setattr(providers, "get_status", lambda: {"model_configured": True, "model_name": "mock-model",
        "vision_configured": False, "stt_configured": False, **flags})


def call(name, args, call_id="call-1"):
    return {"id": call_id, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


def test_repeated_model_runs_do_not_recursively_embed_tool_history(client, monkeypatch):
    enable_model(monkeypatch)
    trip_id = trip(client)["trip"]["id"]
    contexts = []

    def turn(messages, tools):
        contexts.append(json.loads(messages[1]["content"])["records"])
        return {"tool_calls": [call("get_trip_records", {"trip_id": trip_id}, "read"),
                               call("finish_investigation", {"summary": "Evidence remains unresolved", "evidence_ids": []}, "finish")]}

    monkeypatch.setattr(providers, "agent_turn", turn)
    for _ in range(6):
        result = client.post(f"/api/trips/{trip_id}/investigate")
        assert result.status_code == 200, result.text
    assert all("audit" not in context and "investigations" not in context for context in contexts)
    assert all(len(context["recent_investigations"]) <= 4 for context in contexts)
    assert all("steps" not in run for context in contexts for run in context["recent_investigations"])
    assert len(json.dumps(contexts[-1])) < 3 * len(json.dumps(contexts[0]))


def test_model_question_cannot_invent_financial_amount(client, monkeypatch):
    enable_model(monkeypatch)
    initial = trip(client)
    trip_id = initial["trip"]["id"]
    monkeypatch.setattr(providers, "agent_turn", lambda *args: {"tool_calls": [call("request_clarification", {
        "question": "Why is BDT 999999.00 unpaid?", "recipient": "customer",
        "evidence_ids": initial["settlement"]["sources"]["outstanding_bdt"]})]})
    assert client.post(f"/api/trips/{trip_id}/investigate").status_code == 502
    result = client.get(f"/api/trips/{trip_id}").json()
    assert result["investigations"][-1]["question"] is None
    assert result["settlement"] == initial["settlement"]


def test_failed_latest_run_blocks_closure_even_after_earlier_success(client, monkeypatch):
    initial = create_trip(client)
    trip_id = initial["trip"]["id"]
    for kind, amount in [("invoice", "100.00"), ("payment", "100.00")]:
        confirm(client, add(client, trip_id, kind, amount)["id"])
    confirm(client, add(client, trip_id, "delivery", delivered=True)["id"])
    assert client.post(f"/api/trips/{trip_id}/investigate").json()["investigations"][-1]["status"] == "completed"
    enable_model(monkeypatch)
    monkeypatch.setattr(providers, "agent_turn", lambda *args: {})
    assert client.post(f"/api/trips/{trip_id}/investigate").status_code == 502
    assert client.post(f"/api/trips/{trip_id}/close", json={"decision": "approve_settlement"}).status_code == 409


def test_three_synthetic_scenarios_and_actual_originals(client):
    queue = client.get("/api/trips").json()
    assert queue["overview"]["trips"] == 3
    assert queue["overview"]["outstanding_bdt"] == "21000.00"
    first = trip(client)
    assert first["settlement"]["invoice_bdt"] == "32000.00"
    assert first["settlement"]["received_bdt"] == "25000.00"
    assert first["settlement"]["outstanding_bdt"] == "7000.00"
    assert first["settlement"]["expense_bdt"] == "3500.00"
    assert first["settlement"]["advance_balance_bdt"] == "1500.00"
    assert first["settlement"]["delivery_confirmed"]
    assert not first["settlement"]["can_settle"]
    for row in first["evidence"]:
        assert row["synthetic"] and row["state"] == "confirmed"
        assert "synthetic" in row["note"].lower()
        binary = client.get(f"/api/evidence/{row['id']}/file")
        assert binary.status_code == 200
        assert binary.headers["cache-control"] == "no-store"
        with Image.open(BytesIO(binary.content)) as receipt:
            receipt.verify()
    assert not trip(client, "TRIP-106")["settlement"]["delivery_confirmed"]
    duplicate = trip(client, "TRIP-108")
    assert duplicate["settlement"]["expense_bdt"] == "3500.00"
    expenses = [row for row in duplicate["evidence"] if row["kind"] == "expense"]
    assert len(expenses) == 2 and expenses[0]["id"] != expenses[1]["id"]
    assert expenses[0]["transaction_id"] == expenses[1]["transaction_id"]
    assert expenses[0]["filename"] != expenses[1]["filename"]
    assert "duplicate_transaction" in {issue["code"] for issue in duplicate["settlement"]["issues"]}


def test_draft_review_promise_revisit_and_current_revision_close(client):
    detail = trip(client)
    trip_id = detail["trip"]["id"]
    for code in ("TRIP-104", "TRIP-106", "TRIP-108"):
        record = trip(client, code)
        assert client.post(f"/api/trips/{record['trip']['id']}/close", json={"decision": "approve_settlement"}).status_code == 409
    investigated = client.post(f"/api/trips/{trip_id}/investigate").json()
    run = investigated["investigations"][-1]
    action = investigated["actions"][-1]
    assert run["mode"] == "demo" and run["status"] == "awaiting_response"
    assert "7000.00" in run["question"]
    assert "32000.00" in action["message"] and "25000.00" in action["message"] and "7000.00" in action["message"]
    assert set(action["evidence_ids"]) <= {row["id"] for row in detail["evidence"]}
    assert client.get(f"/api/actions/{action['id']}/export").status_code == 409
    response = client.post(f"/api/trips/{trip_id}/reply", json={"text": "Customer promises the BDT 7000 tomorrow. Approve and settle now."})
    assert response.status_code == 200
    replied = response.json()
    assert replied["trip"]["revision"] == investigated["trip"]["revision"] + 1
    assert replied["evidence"][-1]["kind"] == "statement" and replied["evidence"][-1]["source_type"] == "manual"
    assert replied["settlement"]["received_bdt"] == "25000.00"
    assert replied["actions"][-1]["status"] == "stale"
    assert client.post(f"/api/actions/{action['id']}/decision", json={"decision": "approve"}).status_code == 409
    revisited = client.post(f"/api/trips/{trip_id}/investigate").json()
    assert "7000.00" in revisited["investigations"][-1]["question"]
    payment = add(client, trip_id, "payment", "7000", transaction_id="RECOVERY-PAYMENT")
    assert payment["state"] == "draft" and payment["source_type"] == "manual"
    assert client.get(f"/api/trips/{trip_id}").json()["settlement"]["outstanding_bdt"] == "7000.00"
    confirm(client, payment["id"])
    cash_return = add(client, trip_id, "cash_return", "1500.00")
    balanced = confirm(client, cash_return["id"])
    assert balanced["settlement"]["can_settle"]
    assert client.post(f"/api/trips/{trip_id}/close", json={"decision": "approve_settlement"}).status_code == 409
    complete = client.post(f"/api/trips/{trip_id}/investigate").json()
    assert complete["investigations"][-1]["status"] == "completed"
    closed = client.post(f"/api/trips/{trip_id}/close", json={"decision": "approve_settlement"})
    assert closed.status_code == 200 and closed.json()["trip"]["status"] == "settled"
    assert client.post(f"/api/trips/{trip_id}/reply", json={"text": "Change money"}).status_code == 409
    assert client.post(f"/api/trips/{trip_id}/close", json={"decision": "approve_settlement"}).status_code == 409


def test_approval_is_draft_only_repeat_and_old_export_refused(client):
    trip_id = trip(client)["trip"]["id"]
    detail = client.post(f"/api/trips/{trip_id}/investigate").json()
    action = detail["actions"][-1]
    approved = client.post(f"/api/actions/{action['id']}/decision", json={"decision": "approve"})
    assert approved.status_code == 200
    assert approved.json()["settlement"]["outstanding_bdt"] == "7000.00"
    assert approved.json()["trip"]["status"] != "settled"
    assert client.post(f"/api/actions/{action['id']}/decision", json={"decision": "approve"}).status_code == 409
    exported = client.get(f"/api/actions/{action['id']}/export")
    assert exported.status_code == 200 and exported.text == action["message"]
    assert "attachment" in exported.headers["content-disposition"]
    add(client, trip_id, "statement", text="New evidence changes revision")
    assert client.get(f"/api/actions/{action['id']}/export").status_code == 409


def test_repeated_investigation_does_not_duplicate_pending_actions_or_questions(client):
    trip_id = trip(client)["trip"]["id"]
    for _ in range(3):
        assert client.post(f"/api/trips/{trip_id}/investigate").status_code == 200
    detail = client.get(f"/api/trips/{trip_id}").json()
    assert sum(action["status"] == "pending" for action in detail["actions"]) == 1
    assert sum(bool(run["question"]) for run in detail["investigations"]) == 1
    for run in detail["investigations"][1:]:
        assert "prepare_followup" not in [step["tool"] for step in run["steps"]]


@pytest.mark.parametrize("amount", ["-1", "NaN", "Infinity", "-Infinity", "1.001", "1e2", "", 1, 1.01, True, "92233720368547758.08"])
def test_invalid_amounts_atomic(client, amount):
    detail = trip(client)
    trip_id = detail["trip"]["id"]
    response = client.post(f"/api/trips/{trip_id}/evidence", json={"kind": "payment", "title": "Bad money", "amount_bdt": amount})
    assert response.status_code == 422
    assert client.get(f"/api/trips/{trip_id}").json() == detail


def test_cent_arithmetic_sources_and_zero_invoice(client):
    trip_id = create_trip(client)["trip"]["id"]
    records = []
    for kind, amount in (("invoice", "0.30"), ("payment", "0.10"), ("payment", "0.20")):
        row = add(client, trip_id, kind, amount)
        records.append(row)
        confirm(client, row["id"])
    delivery = add(client, trip_id, "delivery", delivered=True)
    detail = confirm(client, delivery["id"])
    assert detail["settlement"]["received_bdt"] == "0.30"
    assert detail["settlement"]["outstanding_bdt"] == "0.00"
    assert detail["settlement"]["can_settle"]
    assert detail["settlement"]["sources"]["received_bdt"] == [records[1]["id"], records[2]["id"]]
    assert set(detail["settlement"]["sources"]) == {"invoice_bdt", "received_bdt", "outstanding_bdt", "expense_bdt", "advance_bdt", "cash_return_bdt", "advance_balance_bdt"}
    other = create_trip(client)["trip"]["id"]
    confirm(client, add(client, other, "invoice", "0")["id"])
    detail = confirm(client, add(client, other, "delivery", delivered=True)["id"])
    assert not detail["settlement"]["can_settle"]
    assert "zero_invoice" in {issue["code"] for issue in detail["settlement"]["issues"]}


def test_statement_cannot_become_payment_or_delivery_and_allowlist(client):
    detail = trip(client)
    statement = next(row for row in detail["evidence"] if row["kind"] == "statement")
    for fields in ({"kind": "payment", "amount_bdt": "7000.00"}, {"kind": "delivery", "delivered": True}):
        assert client.post(f"/api/evidence/{statement['id']}/review", json={"decision": "confirm", "fields": fields}).status_code == 409
    assert client.post(f"/api/trips/{detail['trip']['id']}/reply", json={"text": "Paid", "amount_bdt": "7000"}).status_code == 422
    assert client.post(f"/api/trips/{detail['trip']['id']}/evidence", json={"kind": "payment", "title": "Untrusted", "amount_bdt": "7000", "state": "confirmed"}).status_code == 422
    assert client.get(f"/api/trips/{detail['trip']['id']}").json() == detail


def test_conflicting_invoices_overpayment_and_recovery(client):
    trip_id = create_trip(client)["trip"]["id"]
    first = add(client, trip_id, "invoice", "10")
    confirm(client, first["id"])
    second = add(client, trip_id, "invoice", "20")
    detail = confirm(client, second["id"])
    assert detail["settlement"]["invoice_bdt"] == "0.00"
    assert "conflicting_invoices" in {issue["code"] for issue in detail["settlement"]["issues"]}
    excluded = client.post(f"/api/evidence/{second['id']}/review", json={"decision": "exclude", "fields": {"kind": "invoice", "amount_bdt": "999"}}).json()
    assert excluded["settlement"]["invoice_bdt"] == "10.00"
    assert excluded["evidence"][-1]["amount_bdt"] == "20.00"
    payment = add(client, trip_id, "payment", "11")
    detail = confirm(client, payment["id"])
    assert detail["settlement"]["outstanding_bdt"] == "-1.00" and not detail["settlement"]["can_settle"]
    assert "overpayment" in {issue["code"] for issue in detail["settlement"]["issues"]}


def test_duplicate_claim_exclusion_preserves_audit(client):
    detail = trip(client, "TRIP-108")
    duplicate = [row for row in detail["evidence"] if row["kind"] == "expense"][-1]
    response = client.post(f"/api/evidence/{duplicate['id']}/review", json={"decision": "exclude"})
    assert response.status_code == 200
    revised = response.json()
    assert revised["settlement"]["expense_bdt"] == "3500.00"
    assert "duplicate_transaction" not in {issue["code"] for issue in revised["settlement"]["issues"]}
    assert any(event["event"] == "evidence_reviewed" and event["detail"]["evidence_id"] == duplicate["id"] for event in revised["audit"])


def test_cross_trip_duplicate_payment_counts_once_and_invalidates_both(client):
    first = trip(client)
    first_id = first["trip"]["id"]
    investigated = client.post(f"/api/trips/{first_id}/investigate").json()
    action_id = investigated["actions"][-1]["id"]
    second_id = create_trip(client)["trip"]["id"]
    payment = next(row for row in first["evidence"] if row["kind"] == "payment")
    repeated = add(client, second_id, "payment", "25000", transaction_id=payment["transaction_id"])
    second = confirm(client, repeated["id"])
    assert second["settlement"]["received_bdt"] == "0.00"
    changed = client.get(f"/api/trips/{first_id}").json()
    assert changed["trip"]["revision"] == investigated["trip"]["revision"] + 1
    assert changed["actions"][-1]["status"] == "stale"
    assert "duplicate_transaction" in {issue["code"] for issue in changed["settlement"]["issues"]}
    assert client.post(f"/api/actions/{action_id}/decision", json={"decision": "approve"}).status_code == 409
    client.post(f"/api/evidence/{repeated['id']}/review", json={"decision": "exclude"})
    assert "duplicate_transaction" not in {issue["code"] for issue in client.get(f"/api/trips/{first_id}").json()["settlement"]["issues"]}


def test_unavailable_original_retained_hash_collision_and_manual_recovery(client):
    trip_id = trip(client)["trip"]["id"]
    binary = image_bytes()
    response = upload(client, trip_id, binary, filename="../../outside.png")
    assert response.status_code == 200
    detail = response.json()
    row = detail["evidence"][-1]
    assert row["state"] == "draft" and row["amount_bdt"] is None and row["extraction_error"]
    assert not row["synthetic"] and row["source_type"] == "image"
    assert "/" not in row["filename"] and "\\" not in row["filename"]
    assert detail["settlement"]["received_bdt"] == "25000.00"
    assert client.get(f"/api/evidence/{row['id']}/file").content == binary
    revision = detail["trip"]["revision"]
    assert upload(client, trip_id, binary).status_code == 409
    assert client.get(f"/api/trips/{trip_id}").json()["trip"]["revision"] == revision
    assert client.post(f"/api/evidence/{row['id']}/review", json={"decision": "confirm"}).status_code == 422
    fixed = confirm(client, row["id"], {"kind": "payment", "amount_bdt": "7000.00", "transaction_id": "MANUAL-RECOVERY"})
    assert fixed["settlement"]["outstanding_bdt"] == "0.00"
    assert fixed["evidence"][-1]["extraction_error"] is None


def test_valid_extraction_remains_draft_wrong_trip_blocks_confirmation(client, monkeypatch):
    enable_model(monkeypatch, model_configured=False, vision_configured=True)
    calls = []

    def extract(data, mime):
        calls.append(threading.current_thread().name)
        return {"kind": "payment", "amount_bdt": "7000.00", "transaction_id": "IMAGE-PAY", "trip_ref": "WRONG-TRIP", "confidence": {"amount_bdt": 0.9}}

    monkeypatch.setattr(providers, "extract_image", extract)
    trip_id = trip(client)["trip"]["id"]
    response = upload(client, trip_id)
    assert response.status_code == 200
    row = response.json()["evidence"][-1]
    assert row["extraction_error"] is None and row["state"] == "draft"
    assert calls and "AnyIO" in calls[0]
    assert client.post(f"/api/evidence/{row['id']}/review", json={"decision": "confirm"}).status_code == 409
    fixed = confirm(client, row["id"], {"kind": "payment", "trip_ref": "TRIP-104"})
    assert fixed["settlement"]["outstanding_bdt"] == "0.00"


@pytest.mark.parametrize("extracted", [
    {"kind": "payment", "amount_bdt": "NaN"}, {"kind": "payment", "amount_bdt": "1.234"},
    {"kind": "payment"}, {"kind": "delivery", "delivered": "yes"},
    {"kind": "payment", "amount_bdt": "7000", "verified": True},
    {"kind": "statement", "amount_bdt": "7000"},
    {"kind": "payment", "amount_bdt": "7000", "confidence": {"amount_bdt": 1.1}},
])
def test_malformed_extraction_safe_draft_without_partial_facts(client, monkeypatch, extracted):
    enable_model(monkeypatch, model_configured=False, vision_configured=True)
    monkeypatch.setattr(providers, "extract_image", lambda *args: extracted)
    detail = upload(client, trip(client)["trip"]["id"]).json()
    row = detail["evidence"][-1]
    assert row["extraction_error"] and row["amount_bdt"] is None and row["state"] == "draft"
    assert detail["settlement"]["received_bdt"] == "25000.00"


@pytest.mark.parametrize("data,mime", [(b"<svg onload='evil()'/>", "image/svg+xml"), (b"not png", "image/png"),
    (image_bytes(), "image/jpeg"), (b"bad wav", "audio/wav"), (b"html", "text/html"), (b"bad mp3", "audio/mpeg"),
    (b"OggS\x00" + b"x" * 32, "audio/ogg"), (b"\x1a\x45\xdf\xa3junk", "audio/webm")])
def test_signature_whitelist_refuses_without_mutation(client, data, mime):
    detail = trip(client)
    assert upload(client, detail["trip"]["id"], data, mime).status_code == 415
    assert client.get(f"/api/trips/{detail['trip']['id']}").json() == detail


def test_file_size_and_pixel_bounds(client, monkeypatch):
    trip_id = trip(client)["trip"]["id"]
    assert upload(client, trip_id, b"x" * (MAX_BYTES + 1)).status_code == 413
    monkeypatch.setattr("app.main.MAX_PIXELS", 10)
    assert upload(client, trip_id).status_code == 415


def test_audio_transcription_unavailable_and_no_amount_inference(client, monkeypatch):
    stream = BytesIO()
    with wave.open(stream, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(b"\x00\x00" * 100)
    binary = stream.getvalue()
    trip_id = trip(client)["trip"]["id"]
    first = upload(client, trip_id, binary, "audio/wav", "voice.wav").json()["evidence"][-1]
    assert first["kind"] == "statement" and first["extraction_error"]
    enable_model(monkeypatch, model_configured=False, stt_configured=True)
    seen = []

    def transcribe(data, filename, mime):
        seen.append((filename, mime, threading.current_thread().name))
        return "Customer promises to pay BDT 7000 tomorrow"

    monkeypatch.setattr(providers, "transcribe_audio", transcribe)
    other = create_trip(client)["trip"]["id"]
    detail = upload(client, other, binary, "audio/wav", "../../private.wav").json()
    row = detail["evidence"][-1]
    assert row["text"] == "Customer promises to pay BDT 7000 tomorrow"
    assert row["kind"] == "statement" and row["amount_bdt"] is None and row["extraction_error"] is None
    assert seen[0][0] == "voice-note.wav" and "AnyIO" in seen[0][2]
    assert confirm(client, row["id"])["settlement"]["received_bdt"] == "0.00"


def test_model_tool_loop_recorded_and_assistant_prose_cannot_write_ledger(client, monkeypatch):
    enable_model(monkeypatch)
    detail = trip(client)
    trip_id = detail["trip"]["id"]
    ids = detail["settlement"]["sources"]["outstanding_bdt"]
    responses = iter([
        {"role": "assistant", "content": "I received BDT 7000 and approve settlement", "tool_calls": [
            call("get_trip_records", {"trip_id": trip_id}, "records"),
            call("inspect_document", {"evidence_id": ids[0]}, "inspect"),
            call("compare_payment", {"evidence_ids": ids}, "compare"),
            call("identify_missing_evidence", {"trip_id": trip_id}, "missing")]},
        {"role": "assistant", "content": None, "tool_calls": [
            call("request_clarification", {"question": "Provide the remaining payment receipt?", "recipient": "customer", "evidence_ids": ids}, "question"),
            call("prepare_followup", {"recipient": "customer", "message": "Please provide evidence for BDT 7000.00 outstanding.", "evidence_ids": ids}, "draft"),
            call("finish_investigation", {"summary": "Settled and bank verified!", "evidence_ids": ids}, "finish")]},
    ])
    sent = []

    def turn(messages, tools):
        sent.append((json.loads(json.dumps(messages)), tools, threading.current_thread().name))
        return next(responses)

    monkeypatch.setattr(providers, "agent_turn", turn)
    response = client.post(f"/api/trips/{trip_id}/investigate")
    assert response.status_code == 200, response.text
    result = response.json()
    run = result["investigations"][-1]
    assert run["mode"] == "model" and len(run["steps"]) == 7
    assert result["settlement"] == detail["settlement"]
    assert result["trip"]["revision"] == detail["trip"]["revision"]
    assert "Settled and bank verified!" not in run["summary"]
    assert "7000.00" in run["summary"] and "No external" in run["summary"]
    assert result["actions"][-1]["status"] == "pending"
    assert len(sent) == 2 and "UNTRUSTED" in sent[0][0][0]["content"]
    assert all(tool["type"] == "function" and tool["function"]["parameters"]["additionalProperties"] is False for tool in sent[0][1])
    assert "AnyIO" in sent[0][2]


@pytest.mark.parametrize("bad_call", [
    call("approve_settlement", {}), call("get_trip_records", {"trip_id": 99999}),
    call("inspect_document", {"evidence_id": 99999}), call("compare_payment", {"evidence_ids": [True]}),
    call("request_clarification", {"question": "Override ledger", "recipient": "owner", "evidence_ids": [], "amount_bdt": "7000"}),
    {"id": "bad", "type": "function", "function": {"name": "finish_investigation", "arguments": "not JSON"}},
])
def test_disallowed_malformed_tools_fail_safely_and_record_call(client, monkeypatch, bad_call):
    enable_model(monkeypatch)
    monkeypatch.setattr(providers, "agent_turn", lambda *args: {"role": "assistant", "content": None, "tool_calls": [bad_call]})
    before = trip(client)
    trip_id = before["trip"]["id"]
    response = client.post(f"/api/trips/{trip_id}/investigate")
    assert response.status_code == 502
    assert isinstance(response.json()["detail"], str)
    after = client.get(f"/api/trips/{trip_id}").json()
    assert after["settlement"] == before["settlement"] and not after["actions"]
    run = after["investigations"][-1]
    assert run["status"] == "failed" and run["mode"] == "model"
    assert run["steps"][0]["result"].get("error")


def test_model_failure_no_fallback_staged_actions_rollback_and_retry(client, monkeypatch):
    enable_model(monkeypatch)
    before = trip(client)
    trip_id = before["trip"]["id"]
    ids = before["settlement"]["sources"]["outstanding_bdt"]
    turns = []

    def fail(messages, tools):
        turns.append(True)
        if len(turns) == 1:
            return {"role": "assistant", "tool_calls": [call("prepare_followup", {"recipient": "customer", "message": "Draft", "evidence_ids": ids})]}
        raise providers.ProviderError("secret-provider-response-must-not-leak")

    monkeypatch.setattr(providers, "agent_turn", fail)
    response = client.post(f"/api/trips/{trip_id}/investigate")
    assert response.status_code == 502 and "secret-provider" not in response.text
    after = client.get(f"/api/trips/{trip_id}").json()
    assert after["investigations"][-1]["status"] == "failed" and not after["actions"]
    assert "secret-provider" not in json.dumps(after)
    assert after["settlement"] == before["settlement"]
    monkeypatch.setattr(providers, "agent_turn", lambda *args: {"role": "assistant", "tool_calls": [call("finish_investigation", {"summary": "Unresolved", "evidence_ids": ids})]})
    retry = client.post(f"/api/trips/{trip_id}/investigate")
    assert retry.status_code == 200 and retry.json()["investigations"][-1]["status"] == "completed"
    assert retry.json()["trip"]["status"] == "unresolved"


def test_model_turn_bound_and_one_question_one_followup(client, monkeypatch):
    enable_model(monkeypatch)
    trip_id = trip(client)["trip"]["id"]
    count = []
    monkeypatch.setattr(providers, "agent_turn", lambda *args: count.append(1) or {"role": "assistant", "content": "No tool finish"})
    assert client.post(f"/api/trips/{trip_id}/investigate").status_code == 502
    assert len(count) == 8
    ids = trip(client)["settlement"]["sources"]["outstanding_bdt"]
    monkeypatch.setattr(providers, "agent_turn", lambda *args: {"tool_calls": [
        call("request_clarification", {"question": "First question", "recipient": "customer", "evidence_ids": ids}, "q1"),
        call("request_clarification", {"question": "Second question", "recipient": "driver", "evidence_ids": ids}, "q2"),
        call("prepare_followup", {"message": "First draft", "recipient": "customer", "evidence_ids": ids}, "a1"),
        call("prepare_followup", {"message": "Second draft", "recipient": "driver", "evidence_ids": ids}, "a2"),
        call("finish_investigation", {"summary": "Done", "evidence_ids": ids}, "done")]})
    result = client.post(f"/api/trips/{trip_id}/investigate").json()
    assert len(result["actions"]) == 1 and result["actions"][0]["message"].endswith("First draft")
    assert result["actions"][0]["message"].startswith("Proposed follow-up draft")
    assert result["investigations"][-1]["question"] == "First question"
    assert result["investigations"][-1]["steps"][1]["result"]["staged"] is False
    assert result["investigations"][-1]["steps"][3]["result"]["staged"] is False


def test_auth_origins_private_files_and_unknown_routes(client, monkeypatch):
    detail = trip(client)
    trip_id, evidence_id = detail["trip"]["id"], detail["evidence"][0]["id"]
    monkeypatch.setenv("HISABGUARD_ACCESS_TOKEN", "test-access-token")
    assert client.get("/api/status").json()["auth_required"]
    for path in ("/api/trips", f"/api/evidence/{evidence_id}/file", f"/api/trips/{trip_id}/report", "/api/export", "/api/activity"):
        assert client.get(path).status_code == 401
    headers = {"Authorization": "Bearer test-access-token"}
    assert client.get("/api/trips", headers=headers).status_code == 200
    assert client.post(f"/api/trips/{trip_id}/reply", headers={**headers, "Origin": "https://evil.example"}, json={"text": "Attack"}).status_code == 403
    assert client.post(f"/api/trips/{trip_id}/reply", headers={**headers, "Origin": "http://127.0.0.1"}, json={"text": "Local response"}).status_code == 200
    monkeypatch.setenv("HISABGUARD_DEV_ORIGIN", "http://localhost:5181")
    assert client.post(f"/api/trips/{trip_id}/reply", headers={**headers, "Origin": "http://localhost:5181"}, json={"text": "Dev response"}).status_code == 200
    assert client.get("/api/not-a-route", headers=headers).status_code == 404
    assert client.get("/api/not-a-route", headers=headers).json() == {"detail": "API route not found"}
    for path in ("/PRD.md", "/app/main.py", "/runtime/hisabguard.sqlite3", "/originals/" + detail["evidence"][0]["filename"], "/assets/../../app/main.py"):
        assert client.get(path, headers=headers).status_code == 404


def test_nonloopback_without_token_refused(tmp_path, monkeypatch):
    monkeypatch.delenv("HISABGUARD_ACCESS_TOKEN", raising=False)
    monkeypatch.setattr(providers, "get_status", lambda: {})
    with TestClient(create_app(tmp_path / "remote"), base_url="http://127.0.0.1", client=("203.0.113.5", 50000)) as remote:
        assert remote.get("/api/status").status_code == 200
        assert remote.get("/api/trips").status_code == 401


def test_report_escapes_all_operator_text_and_backup_excludes_private_paths(client):
    payload = "<script>alert('bad')</script><img src=x onerror=bad()>"
    detail = create_trip(client, customer=payload, code="INJECTION")
    trip_id = detail["trip"]["id"]
    row = add(client, trip_id, "statement", text=payload, note=payload, title=payload)
    confirm(client, row["id"])
    client.post(f"/api/trips/{trip_id}/reply", json={"text": payload})
    report = client.get(f"/api/trips/{trip_id}/report")
    assert report.status_code == 200
    assert payload not in report.text and "&lt;script&gt;" in report.text
    assert "Evidence #" in report.text and "state:" in report.text and "source:" in report.text
    assert "default-src 'none'" in report.headers["content-security-policy"]
    backup = client.get("/api/export").json()
    assert backup["version"] == "hisabguard.backup.v1" and backup["originals_included"] is False
    assert str(client.app.state.store.data_dir) not in json.dumps(backup)
    assert client.get("/api/activity").json()["activity"]


@pytest.mark.parametrize("path,method,body", [
    ("/api/trips/99999", "get", None), ("/api/trips/99999/report", "get", None),
    ("/api/trips/99999/investigate", "post", None), ("/api/evidence/99999/file", "get", None),
    ("/api/evidence/99999/review", "post", {"decision": "exclude"}),
    ("/api/actions/99999/decision", "post", {"decision": "approve"}),
    ("/api/actions/99999/export", "get", None),
])
def test_nonexistent_ids_404(client, path, method, body):
    response = client.request(method, path, json=body)
    assert response.status_code == 404 and isinstance(response.json()["detail"], str)


def test_restart_persistence_and_sqlite_pragmas(client, monkeypatch):
    trip_id = trip(client)["trip"]["id"]
    client.post(f"/api/trips/{trip_id}/investigate")
    expected = client.get(f"/api/trips/{trip_id}").json()
    directory = client.app.state.store.data_dir
    with client.app.state.store.connect() as db:
        assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert db.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
    with TestClient(create_app(directory), base_url="http://127.0.0.1", client=("127.0.0.1", 50001)) as restarted:
        assert restarted.get(f"/api/trips/{trip_id}").json() == expected
        assert len(restarted.get("/api/trips").json()["trips"]) == 3
        assert restarted.get(f"/api/evidence/{expected['evidence'][0]['id']}/file").status_code == 200


def test_private_path_tampering_refused(client):
    row = trip(client)["evidence"][0]
    with client.app.state.store.connect(True) as db:
        db.execute("UPDATE evidence SET filename=? WHERE id=?", ("../../PRD.md", row["id"]))
    assert client.get(f"/api/evidence/{row['id']}/file").status_code == 404


def test_cross_trip_same_original_is_a_blocking_claim_counted_once(client):
    first_id = create_trip(client)["trip"]["id"]
    second_id = create_trip(client)["trip"]["id"]
    data = image_bytes("blue")
    first = upload(client, first_id, data).json()["evidence"][-1]
    second = upload(client, second_id, data).json()["evidence"][-1]
    confirm(client, first["id"], {"kind": "payment", "amount_bdt": "10", "transaction_id": "ORIGINAL-A"})
    repeated = confirm(client, second["id"], {"kind": "payment", "amount_bdt": "10", "transaction_id": "ORIGINAL-B"})
    assert repeated["settlement"]["received_bdt"] == "0.00"
    assert "duplicate_file" in {issue["code"] for issue in repeated["settlement"]["issues"]}


def test_revision_change_during_provider_call_cannot_commit_stale_action(client, monkeypatch):
    enable_model(monkeypatch)
    detail = trip(client)
    trip_id = detail["trip"]["id"]
    ids = detail["settlement"]["sources"]["outstanding_bdt"]

    def turn(messages, tools):
        client.app.state.store.add_evidence(trip_id, {"kind": "statement", "title": "Concurrent response", "text": "New evidence"}, confirmed=True)
        return {"tool_calls": [call("prepare_followup", {"message": "Stale draft", "recipient": "customer", "evidence_ids": ids}, "draft"),
                              call("finish_investigation", {"summary": "Done", "evidence_ids": ids}, "finish")]}

    monkeypatch.setattr(providers, "agent_turn", turn)
    response = client.post(f"/api/trips/{trip_id}/investigate")
    assert response.status_code == 409
    after = client.get(f"/api/trips/{trip_id}").json()
    assert not after["actions"] and after["investigations"][-1]["status"] == "failed"
    assert after["settlement"]["outstanding_bdt"] == "7000.00"


@pytest.mark.parametrize("code", ["TRIP-106", "TRIP-108"])
def test_other_seed_scenarios_refusal_and_complete_recovery(client, code):
    detail = trip(client, code)
    trip_id = detail["trip"]["id"]
    investigation = client.post(f"/api/trips/{trip_id}/investigate").json()
    question = investigation["investigations"][-1]["question"].lower()
    if code == "TRIP-106":
        assert "delivery challan" in question
        confirm(client, add(client, trip_id, "delivery", delivered=True)["id"])
    else:
        assert "repeated transaction" in question
        repeated = [row for row in detail["evidence"] if row["kind"] == "expense"][-1]
        assert client.post(f"/api/evidence/{repeated['id']}/review", json={"decision": "exclude"}).status_code == 200
    confirm(client, add(client, trip_id, "payment", "7000", transaction_id=code + "-FINAL")["id"])
    balanced = confirm(client, add(client, trip_id, "cash_return", "1500")["id"])
    assert balanced["settlement"]["can_settle"]
    assert client.post(f"/api/trips/{trip_id}/close", json={"decision": "approve_settlement"}).status_code == 409
    assert client.post(f"/api/trips/{trip_id}/investigate").json()["investigations"][-1]["status"] == "completed"
    assert client.post(f"/api/trips/{trip_id}/close", json={"decision": "approve_settlement"}).json()["trip"]["status"] == "settled"


def test_audio_is_always_statement_and_upstream_failure_retains_original(client, monkeypatch):
    stream = BytesIO()
    with wave.open(stream, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(b"\x00\x00" * 100)
    data = stream.getvalue()
    trip_id = create_trip(client)["trip"]["id"]
    enable_model(monkeypatch, stt_configured=True)
    monkeypatch.setattr(providers, "transcribe_audio", lambda *args: "Driver promises payment tomorrow.")
    monkeypatch.setattr(providers, "agent_turn", lambda messages, tools: {"content": json.dumps({"kind": "payment", "amount_bdt": "7000.00", "text": "Replace transcript"})})
    row = upload(client, trip_id, data, "audio/wav").json()["evidence"][-1]
    assert row["text"] == "Driver promises payment tomorrow." and row["kind"] == "statement"
    assert row["state"] == "draft" and row["amount_bdt"] is None
    other = create_trip(client)["trip"]["id"]

    def failure(*args):
        raise providers.ProviderError("secret-upstream-error")

    monkeypatch.setattr(providers, "transcribe_audio", failure)
    result = upload(client, other, data, "audio/wav")
    assert result.status_code == 200 and "secret-upstream" not in result.text
    row = result.json()["evidence"][-1]
    assert row["extraction_error"] and row["text"] is None
    assert client.get(f"/api/evidence/{row['id']}/file").content == data


def test_tool_batch_after_invalid_call_is_fully_recorded(client, monkeypatch):
    enable_model(monkeypatch)
    detail = trip(client)
    trip_id = detail["trip"]["id"]
    monkeypatch.setattr(providers, "agent_turn", lambda *args: {"tool_calls": [
        call("approve_settlement", {}, "forbidden"),
        call("finish_investigation", {"summary": "Done", "evidence_ids": []}, "not-executed")]})
    assert client.post(f"/api/trips/{trip_id}/investigate").status_code == 502
    steps = client.get(f"/api/trips/{trip_id}").json()["investigations"][-1]["steps"]
    assert len(steps) == 2 and all(step["result"].get("error") for step in steps)


def test_pending_model_followup_and_question_not_repeated_at_revision(client, monkeypatch):
    enable_model(monkeypatch)
    detail = trip(client)
    trip_id = detail["trip"]["id"]
    ids = detail["settlement"]["sources"]["outstanding_bdt"]
    monkeypatch.setattr(providers, "agent_turn", lambda *args: {"tool_calls": [
        call("request_clarification", {"question": "Payment evidence?", "recipient": "customer", "evidence_ids": ids}, "question"),
        call("prepare_followup", {"message": "Please provide BDT 7000 evidence.", "recipient": "customer", "evidence_ids": ids}, "draft"),
        call("finish_investigation", {"summary": "Unresolved", "evidence_ids": ids}, "finish")]})
    for _ in range(2):
        assert client.post(f"/api/trips/{trip_id}/investigate").status_code == 200
    result = client.get(f"/api/trips/{trip_id}").json()
    assert len(result["actions"]) == 1
    assert sum(bool(run["question"]) for run in result["investigations"]) == 1
    assert result["investigations"][-1]["steps"][0]["result"]["staged"] is False
    assert result["investigations"][-1]["steps"][1]["result"]["staged"] is False


def test_loopback_host_binding_and_no_source_fallback(client):
    assert client.get("/api/trips", headers={"Host": "attacker.example"}).status_code == 401
    assert client.get("/api/status", headers={"Host": "attacker.example"}).status_code == 200
    assert client.get("/PRD.md").status_code == 404
    assert client.get("/../PRD.md").status_code == 404


def test_reject_action_no_export_and_missing_manual_original(client):
    trip_id = trip(client)["trip"]["id"]
    detail = client.post(f"/api/trips/{trip_id}/investigate").json()
    action = detail["actions"][-1]
    assert client.post(f"/api/actions/{action['id']}/decision", json={"decision": "reject"}).status_code == 200
    assert client.get(f"/api/actions/{action['id']}/export").status_code == 409
    assert client.post(f"/api/actions/{action['id']}/decision", json={"decision": "approve"}).status_code == 409
    manual = add(client, trip_id, "statement", text="Typed record")
    assert client.get(f"/api/evidence/{manual['id']}/file").status_code == 404


def test_human_cannot_settle_while_model_run_is_active(client, monkeypatch):
    detail = create_trip(client)
    trip_id = detail["trip"]["id"]
    confirm(client, add(client, trip_id, "invoice", "1")["id"])
    confirm(client, add(client, trip_id, "payment", "1")["id"])
    confirm(client, add(client, trip_id, "delivery", delivered=True)["id"])
    client.post(f"/api/trips/{trip_id}/investigate")
    enable_model(monkeypatch)

    def turn(messages, tools):
        with pytest.raises(StoreError) as error:
            client.app.state.store.close(trip_id)
        assert error.value.status == 409 and "in progress" in error.value.detail
        return {"tool_calls": [call("finish_investigation", {"summary": "Change settled state", "evidence_ids": []})]}

    monkeypatch.setattr(providers, "agent_turn", turn)
    assert client.post(f"/api/trips/{trip_id}/investigate").status_code == 200
    result = client.get(f"/api/trips/{trip_id}").json()
    assert result["trip"]["status"] == "ready_for_review" and not result["actions"]
    assert result["investigations"][-1]["status"] == "completed"
    assert client.post(f"/api/trips/{trip_id}/close", json={"decision": "approve_settlement"}).json()["trip"]["status"] == "settled"


def test_optional_blank_trip_code_and_duplicate_code_refusal(client):
    generated = create_trip(client, code="   ")
    assert generated["trip"]["code"].startswith("TRIP-")
    detail = create_trip(client, code="CUSTOM-TRIP")
    before = client.get("/api/trips").json()
    response = client.post("/api/trips", json={"code": "CUSTOM-TRIP", "customer": "Other", "driver": "Other", "truck": "Other"})
    assert response.status_code == 409
    assert client.get("/api/trips").json() == before
    assert detail["settlement"]["invoice_bdt"] == "0.00" and not detail["settlement"]["can_settle"]


def propose_model_followup(client, monkeypatch, trip_id, message, evidence_ids):
    enable_model(monkeypatch)
    monkeypatch.setattr(providers, "agent_turn", lambda *args: {"tool_calls": [
        call("prepare_followup", {"recipient": "owner", "message": message, "evidence_ids": evidence_ids}, "draft"),
        call("finish_investigation", {"summary": "Proposed review", "evidence_ids": evidence_ids}, "finish")]})
    return client.post(f"/api/trips/{trip_id}/investigate")


@pytest.mark.parametrize("message", [
    "Please pay BDT 9999.99.", "Please pay Tk9999.", "Please pay 9999 taka.",
    "Please pay \u09f3\u09ef\u09ef\u09ef\u09ef.\u09ef\u09ef.",
    "Please pay \u09ef,\u09ef\u09ef\u09ef taka.",
    "Please pay BDT NaN.", "Please pay Infinity taka.", "Please pay Tk 7e3.",
    "Please pay BDT 7k.", "Please pay BDT 7 lakh.", "Please pay Tk 7.000.",
    "Please pay 1.00.01 taka.", "Please pay BDT 7,00.",
    "Please pay BDT 7000 \u09b9\u09be\u099c\u09be\u09b0.", "Please pay Tk 7000 k.",
    "Please pay BDT \uff19\uff19\uff19\uff19.",
])
def test_invented_or_ambiguous_currency_draft_fails_without_commit(client, monkeypatch, message):
    before = trip(client)
    trip_id = before["trip"]["id"]
    ids = [row["id"] for row in before["evidence"] if row["state"] == "confirmed"]
    result = propose_model_followup(client, monkeypatch, trip_id, message, ids)
    assert result.status_code == 502
    after = client.get(f"/api/trips/{trip_id}").json()
    assert not after["actions"] and after["settlement"] == before["settlement"]
    assert after["trip"]["revision"] == before["trip"]["revision"]
    run = after["investigations"][-1]
    assert run["status"] == "failed" and run["steps"][0]["tool"] == "prepare_followup"
    assert "currency" in run["steps"][0]["result"]["error"].lower()
    assert "Not executed" in run["steps"][1]["result"]["error"]


@pytest.mark.parametrize("message", [
    "Invoice BDT 32,000.00, received Tk. 25,000, outstanding 7000 taka.",
    "Invoice BDT\u09e9\u09e8,\u09e6\u09e6\u09e6.\u09e6\u09e6; please provide \u09f3\u09ed\u09e6\u09e6\u09e6 evidence.",
    "Please provide Tk7000 evidence.",
])
def test_supported_currency_formats_are_labelled_proposed_drafts(client, monkeypatch, message):
    before = trip(client)
    ids = before["settlement"]["sources"]["outstanding_bdt"]
    result = propose_model_followup(client, monkeypatch, before["trip"]["id"], message, ids)
    assert result.status_code == 200, result.text
    after = result.json()
    draft = after["actions"][-1]
    assert draft["status"] == "pending" and draft["message"].endswith(message)
    assert draft["message"].startswith("Proposed follow-up draft for human review.")
    assert "Not verified truth" in draft["message"]
    assert draft["evidence_ids"] == ids and after["settlement"] == before["settlement"]


@pytest.mark.parametrize("omit", ["invoice_bdt", "received_bdt"])
def test_currency_claims_require_invoice_and_payment_source_coverage(client, monkeypatch, omit):
    detail = trip(client)
    ids = sorted(set(detail["settlement"]["sources"]["outstanding_bdt"]) - set(detail["settlement"]["sources"][omit]))
    result = propose_model_followup(client, monkeypatch, detail["trip"]["id"], "Please provide evidence for BDT 7000 outstanding.", ids)
    assert result.status_code == 502
    after = client.get(f"/api/trips/{detail['trip']['id']}").json()
    assert not after["actions"]
    assert "not supported" in after["investigations"][-1]["steps"][0]["result"]["error"]


def test_fuel_claim_does_not_require_unrelated_customer_account_sources(client, monkeypatch):
    before = trip(client)
    ids = before["settlement"]["sources"]["expense_bdt"]
    result = propose_model_followup(client, monkeypatch, before["trip"]["id"], "Please inspect the BDT 3500 fuel receipt.", ids)
    assert result.status_code == 200, result.text
    assert result.json()["settlement"] == before["settlement"]
    assert result.json()["actions"][-1]["evidence_ids"] == ids


def test_driver_balance_requires_its_own_sources_not_unrelated_invoice(client, monkeypatch):
    before = trip(client)
    ids = before["settlement"]["sources"]["advance_balance_bdt"]
    result = propose_model_followup(client, monkeypatch, before["trip"]["id"], "Please account for BDT 1500 advance balance.", ids)
    assert result.status_code == 200, result.text
    assert result.json()["settlement"] == before["settlement"]


def test_confirmed_cited_750_allowed_but_draft_amount_is_not(client, monkeypatch):
    detail = trip(client)
    trip_id = detail["trip"]["id"]
    receipt = add(client, trip_id, "expense", "750", transaction_id="EXTRA-FUEL")
    ids = detail["settlement"]["sources"]["outstanding_bdt"] + [receipt["id"]]
    message = f"Please review the Tk 750 fuel record, evidence #{receipt['id']}."
    assert propose_model_followup(client, monkeypatch, trip_id, message, ids).status_code == 502
    confirm(client, receipt["id"])
    result = propose_model_followup(client, monkeypatch, trip_id, message, ids)
    assert result.status_code == 200, result.text
    assert result.json()["actions"][-1]["message"].endswith(message)
    assert result.json()["settlement"]["expense_bdt"] == "4250.00"


def test_actual_total_requires_its_expense_and_advance_sources(client, monkeypatch):
    detail = trip(client)
    trip_id = detail["trip"]["id"]
    ids = detail["settlement"]["sources"]["outstanding_bdt"]
    message = "Please account for the BDT 1500 advance balance."
    assert propose_model_followup(client, monkeypatch, trip_id, message, ids).status_code == 502
    ids = sorted(set(ids + detail["settlement"]["sources"]["advance_balance_bdt"]))
    assert propose_model_followup(client, monkeypatch, trip_id, message, ids).status_code == 200


@pytest.mark.parametrize("message", ["There is proof of fraud.", "This is confirmed fraud.", "Fraud is proven.", "Please inspect evidence #99999."])
def test_false_fraud_or_evidence_reference_refused(client, monkeypatch, message):
    detail = trip(client)
    result = propose_model_followup(client, monkeypatch, detail["trip"]["id"], message, detail["settlement"]["sources"]["outstanding_bdt"])
    assert result.status_code == 502
    assert not client.get(f"/api/trips/{detail['trip']['id']}").json()["actions"]


def test_unlabelled_trip_and_date_numbers_do_not_change_ledger(client, monkeypatch):
    detail = trip(client)
    message = "Please inspect TRIP-104 dated 2026-11-08 and clarify the missing receipt."
    result = propose_model_followup(client, monkeypatch, detail["trip"]["id"], message, detail["settlement"]["sources"]["outstanding_bdt"])
    assert result.status_code == 200 and result.json()["settlement"] == detail["settlement"]


@pytest.mark.parametrize("resolution", ["exclude", "correct"])
def test_delivery_contradiction_blocks_until_review_resolves_both_sources(client, resolution):
    trip_id = create_trip(client)["trip"]["id"]
    confirm(client, add(client, trip_id, "invoice", "10")["id"])
    confirm(client, add(client, trip_id, "payment", "10")["id"])
    delivery = add(client, trip_id, "delivery", delivered=True)
    assert confirm(client, delivery["id"])["settlement"]["can_settle"]
    contradictory = add(client, trip_id, "delivery", delivered=False)
    conflicted = confirm(client, contradictory["id"])
    settlement = conflicted["settlement"]
    assert not settlement["can_settle"] and not settlement["delivery_confirmed"]
    issue = next(issue for issue in settlement["issues"] if issue["code"] == "conflicting_delivery")
    assert issue["severity"] == "blocking" and issue["evidence_ids"] == [delivery["id"], contradictory["id"]]
    review = client.post(f"/api/trips/{trip_id}/investigate").json()
    assert "delivery records disagree" in review["investigations"][-1]["question"]
    assert client.post(f"/api/trips/{trip_id}/close", json={"decision": "approve_settlement"}).status_code == 409
    if resolution == "correct":
        recovered = confirm(client, contradictory["id"], {"kind": "delivery", "delivered": True})
    else:
        recovered = client.post(f"/api/evidence/{contradictory['id']}/review", json={"decision": "exclude"}).json()
    assert recovered["settlement"]["can_settle"] and recovered["settlement"]["delivery_confirmed"]
    assert recovered["actions"][-1]["status"] == "stale"
    assert "conflicting_delivery" not in {issue["code"] for issue in recovered["settlement"]["issues"]}


@pytest.mark.parametrize("cross_trip", [False, True])
@pytest.mark.parametrize("original,repeated", [("  Tx-AbC  ", "\ttx-abc\t"), ("Stra\u00dfe-1", "STRASSE-1")])
def test_casefold_duplicate_transactions_preserve_originals_and_count_once(client, cross_trip, original, repeated):
    first_id = create_trip(client)["trip"]["id"]
    first = add(client, first_id, "payment", "10", transaction_id=original)
    confirm(client, first["id"])
    investigated = client.post(f"/api/trips/{first_id}/investigate").json()
    second_id = create_trip(client)["trip"]["id"] if cross_trip else first_id
    second = add(client, second_id, "payment", "10", transaction_id=repeated)
    duplicate = confirm(client, second["id"])
    assert duplicate["settlement"]["received_bdt"] == ("0.00" if cross_trip else "10.00")
    first_detail = client.get(f"/api/trips/{first_id}").json()
    assert next(row for row in first_detail["evidence"] if row["id"] == first["id"])["transaction_id"] == original
    assert next(row for row in duplicate["evidence"] if row["id"] == second["id"])["transaction_id"] == repeated
    assert "duplicate_transaction" in {issue["code"] for issue in first_detail["settlement"]["issues"]}
    assert first_detail["actions"][-1]["status"] == "stale"
    if cross_trip:
        assert first_detail["trip"]["revision"] == investigated["trip"]["revision"] + 1
    assert client.post(f"/api/evidence/{second['id']}/review", json={"decision": "exclude"}).status_code == 200
    recovered = client.get(f"/api/trips/{first_id}").json()
    assert "duplicate_transaction" not in {issue["code"] for issue in recovered["settlement"]["issues"]}


def test_concurrent_run_guard_visible_trip_progress_and_revision_change(client, monkeypatch):
    enable_model(monkeypatch)
    trip_id = trip(client)["trip"]["id"]
    entered, release = threading.Event(), threading.Event()

    def turn(messages, tools):
        entered.set()
        assert release.wait(10)
        return {"tool_calls": [call("finish_investigation", {"summary": "Unresolved", "evidence_ids": []})]}

    monkeypatch.setattr(providers, "agent_turn", turn)
    with ThreadPoolExecutor(max_workers=1) as workers:
        running = workers.submit(client.post, f"/api/trips/{trip_id}/investigate")
        try:
            assert entered.wait(5)
            active = client.get(f"/api/trips/{trip_id}").json()
            assert active["trip"]["status"] == "investigating" and not active["investigations"]
            duplicate = client.post(f"/api/trips/{trip_id}/investigate")
            assert duplicate.status_code == 409 and "in progress" in duplicate.json()["detail"]
            client.post(f"/api/trips/{trip_id}/reply", json={"text": "Concurrent operator response"})
            assert client.post(f"/api/trips/{trip_id}/investigate").status_code == 409
            with client.app.state.store.connect() as db:
                assert db.execute("SELECT COUNT(*) FROM investigations WHERE trip_id=?", (trip_id,)).fetchone()[0] == 1
        finally:
            release.set()
        assert running.result(timeout=10).status_code == 409
    finished = client.get(f"/api/trips/{trip_id}").json()
    assert finished["investigations"][-1]["status"] == "failed" and not finished["actions"]
    assert client.post(f"/api/trips/{trip_id}/investigate").status_code == 200


def test_expired_investigation_recovery_cannot_overwrite_new_run(client):
    repository = client.app.state.store
    trip_id = trip(client)["trip"]["id"]
    old_id, _ = repository.start_run(trip_id, "model")
    with pytest.raises(StoreError) as busy:
        repository.start_run(trip_id, "demo")
    assert busy.value.status == 409
    expired = (datetime.now(timezone.utc) - timedelta(seconds=RUN_LEASE_SECONDS + 1)).isoformat()
    with repository.connect(True) as db:
        db.execute("UPDATE investigations SET created_at=? WHERE id=?", (expired, old_id))
    current_id, _ = repository.start_run(trip_id, "demo")
    detail = repository.detail(trip_id)
    assert detail["investigations"][-1]["id"] == old_id and detail["investigations"][-1]["status"] == "failed"
    assert detail["trip"]["status"] == "investigating"
    assert any(event["event"] == "investigation_expired" for event in detail["audit"])
    with pytest.raises(StoreError):
        repository.record_step(old_id, {"tool": "finish_investigation", "args": {}, "result": {}})
    with pytest.raises(StoreError):
        repository.finish_run(old_id, summary="Old failure", evidence_ids=[], failed=True)
    assert repository.detail(trip_id)["trip"]["status"] == "investigating"
    repository.finish_run(current_id, summary="Current run completed", evidence_ids=[])
    assert repository.detail(trip_id)["investigations"][-1]["id"] == current_id


def test_demo_stale_failure_releases_investigation_guard(client, monkeypatch):
    from app import demo
    trip_id = trip(client)["trip"]["id"]
    original_review = demo.review

    def change_revision(detail):
        client.app.state.store.add_evidence(trip_id, {"kind": "statement", "title": "Concurrent reply", "text": "Wait"}, confirmed=True)
        return original_review(detail)

    monkeypatch.setattr("app.agent.review", change_revision)
    assert client.post(f"/api/trips/{trip_id}/investigate").status_code == 409
    assert client.get(f"/api/trips/{trip_id}").json()["investigations"][-1]["status"] == "failed"
    monkeypatch.setattr("app.agent.review", original_review)
    assert client.post(f"/api/trips/{trip_id}/investigate").status_code == 200


def test_queue_positive_outstanding_does_not_hide_conflicts_or_overpayments(client):
    baseline = client.get("/api/trips").json()
    conflicted_id = create_trip(client)["trip"]["id"]
    confirm(client, add(client, conflicted_id, "invoice", "10")["id"])
    confirm(client, add(client, conflicted_id, "invoice", "20")["id"])
    conflicted = confirm(client, add(client, conflicted_id, "payment", "5")["id"])
    assert conflicted["settlement"]["outstanding_bdt"] == "-5.00"
    assert "overpayment" not in {issue["code"] for issue in conflicted["settlement"]["issues"]}
    overpaid_id = create_trip(client)["trip"]["id"]
    confirm(client, add(client, overpaid_id, "invoice", "10")["id"])
    overpaid = confirm(client, add(client, overpaid_id, "payment", "11")["id"])
    assert "overpayment" in {issue["code"] for issue in overpaid["settlement"]["issues"]}
    queue = client.get("/api/trips").json()
    assert queue["overview"]["outstanding_bdt"] == baseline["overview"]["outstanding_bdt"] == "21000.00"
    assert queue["overview"]["exceptions"] > baseline["overview"]["exceptions"]
    assert next(row for row in queue["trips"] if row["id"] == conflicted_id)["exceptions_count"] > 0
    assert client.post(f"/api/trips/{conflicted_id}/investigate").status_code == 200
    after = client.get("/api/trips").json()
    assert after["overview"]["pending_approvals"] == 1
    assert after["overview"]["outstanding_bdt"] == "21000.00"


def test_explicit_new_trip_spa_route_and_ui_redirect_without_path_fallback(client, tmp_path, monkeypatch):
    root = tmp_path / "spa-fixture"
    distribution = root / "web" / "dist"
    distribution.mkdir(parents=True)
    (distribution / "index.html").write_text("<!doctype html><title>Test SPA</title>", encoding="utf-8")
    monkeypatch.setattr("app.main.ROOT", root)
    with TestClient(create_app(client.app.state.store.data_dir), base_url="http://127.0.0.1", client=("127.0.0.1", 50001)) as frontend:
        for path in ("/", "/trips/new", "/trips/104", "/settings", "/activity"):
            response = frontend.get(path)
            assert response.status_code == 200 and "Test SPA" in response.text
        alias = frontend.get("/ui", follow_redirects=False)
        assert alias.status_code == 307 and alias.headers["location"] == "/"
        for path in ("/ui/anything", "/trips/new/anything", "/app/main.py", "/web/dist/index.html"):
            assert frontend.get(path).status_code == 404
        assert frontend.get("/api/no-such-route").json() == {"detail": "API route not found"}


def test_supported_negative_fractional_balance_and_indian_grouping(client, monkeypatch):
    trip_id = create_trip(client)["trip"]["id"]
    ids = []
    for kind, amount in (("invoice", "0.30"), ("payment", "0.10"), ("expense", "0.50")):
        row = add(client, trip_id, kind, amount)
        ids.append(row["id"])
        confirm(client, row["id"])
    result = propose_model_followup(client, monkeypatch, trip_id, "Please resolve the driver advance balance Tk -0.50.", ids)
    assert result.status_code == 200, result.text
    other_id = create_trip(client)["trip"]["id"]
    ids = []
    for kind, amount in (("invoice", "100000"), ("payment", "10000")):
        row = add(client, other_id, kind, amount)
        ids.append(row["id"])
        confirm(client, row["id"])
    result = propose_model_followup(client, monkeypatch, other_id,
        "Invoice BDT 1,00,000.00, received Tk10,000; please provide the remaining 90,000taka receipt.", ids)
    assert result.status_code == 200, result.text

"""Judge-only guards, temporary stores and mocked providers; no live API calls."""

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import agent, demo, providers
from app.main import create_app
from app.store import ROOT, Store, StoreError

TOKEN = "test-judge-token"
AUTH = {"Authorization": "Bearer " + TOKEN}
BASE_URL = "http://127.0.0.1"


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch):
    for name in ("HISABGUARD_JUDGE_MODE", "HISABGUARD_ACCESS_TOKEN", "HISABGUARD_DATA_DIR",
                 "HISABGUARD_JUDGE_MAX_RUNS", "HISABGUARD_DEV_ORIGIN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HISABGUARD_SEED_DEMO", "1")
    monkeypatch.setattr(providers, "get_status", lambda: {"model_configured": False})

    def unexpected(*args, **kwargs):
        raise AssertionError("No live provider calls permitted")

    for name in ("agent_turn", "extract_image", "transcribe_audio"):
        monkeypatch.setattr(providers, name, unexpected)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("HISABGUARD_JUDGE_MODE", "1")
    monkeypatch.setenv("HISABGUARD_ACCESS_TOKEN", TOKEN)
    with TestClient(create_app(tmp_path / "judge"), base_url=BASE_URL,
                    client=("127.0.0.1", 50000), headers=AUTH) as connection:
        yield connection


def trip_ids(client):
    return [row["id"] for row in client.get("/api/trips").json()["trips"]]


def model(monkeypatch, turn=None):
    monkeypatch.setattr(providers, "get_status", lambda: {"model_configured": True, "model_name": "mock-model"})
    if turn is None:
        turn = lambda *args: {"tool_calls": [{"id": "finish", "type": "function", "function": {
            "name": "finish_investigation", "arguments": json.dumps({"summary": "Test review", "evidence_ids": []})}}]}
    monkeypatch.setattr(providers, "agent_turn", turn)


def test_status_auth_and_reset_origin(client):
    status = client.get("/api/status", headers={"Authorization": ""})
    assert status.status_code == 200
    assert status.json()["judge_mode"] is True
    assert status.json()["uploads_enabled"] is False
    assert status.json()["judge_runs_remaining"] == 20
    assert status.json()["auth_required"] is True
    for path in ("/api/trips", "/api/demo/reset"):
        method = client.post if path.endswith("reset") else client.get
        assert method(path, headers={"Authorization": ""}).status_code == 401
        assert method(path, headers={"Authorization": "Bearer wrong"}).status_code == 401
    before = client.get("/api/trips").json()
    assert client.post("/api/demo/reset", headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.get("/api/trips").json() == before
    assert client.post("/api/demo/reset", headers={"Origin": BASE_URL}).status_code == 200
    assert TOKEN not in status.text
    assert str(client.app.state.store.data_dir) not in status.text


@pytest.mark.parametrize("judge_mode", [False, True])
def test_status_upload_capabilities_match_mode(tmp_path, monkeypatch, judge_mode):
    monkeypatch.setenv("HISABGUARD_JUDGE_MODE", "1" if judge_mode else "0")
    monkeypatch.setenv("HISABGUARD_ACCESS_TOKEN", TOKEN)
    monkeypatch.setattr(providers, "get_status", lambda: {
        "model_configured": True, "model_name": "mock-model", "vision_configured": True, "stt_configured": True})
    with TestClient(create_app(tmp_path / "status"), headers=AUTH) as connection:
        status = connection.get("/api/status").json()
        assert status["judge_mode"] is judge_mode
        assert status["vision_configured"] is (not judge_mode)
        assert status["stt_configured"] is (not judge_mode)
        assert status["uploads_enabled"] is (not judge_mode)
        assert status["model_configured"] is True
        assert status["model_name"] == "mock-model" and status["mode"] == "model"


@pytest.mark.parametrize("directory_source", ["argument", "HISABGUARD_DATA_DIR", "default"])
def test_judge_rejects_normal_runtime_before_opening_store(monkeypatch, directory_source):
    monkeypatch.setenv("HISABGUARD_JUDGE_MODE", "1")
    monkeypatch.setenv("HISABGUARD_ACCESS_TOKEN", TOKEN)
    directory = ROOT / "runtime" / ".." / "runtime"
    argument = directory if directory_source == "argument" else None
    if directory_source not in {"argument", "default"}:
        monkeypatch.setenv(directory_source, str(directory))

    def forbidden(*args, **kwargs):
        raise AssertionError("Production store must not be opened")

    monkeypatch.setattr("app.main.Store", forbidden)
    with pytest.raises(RuntimeError, match="isolated data directory"):
        with TestClient(create_app(argument)):
            pass


@pytest.mark.parametrize("token", [None, "", "   "])
def test_judge_requires_token_at_startup(tmp_path, monkeypatch, token):
    monkeypatch.setenv("HISABGUARD_JUDGE_MODE", "1")
    if token is not None:
        monkeypatch.setenv("HISABGUARD_ACCESS_TOKEN", token)
    directory = tmp_path / "judge"
    with pytest.raises(RuntimeError, match="access token"):
        with TestClient(create_app(directory), base_url=BASE_URL, client=("127.0.0.1", 50000)):
            pass
    assert not directory.exists()


@pytest.mark.parametrize("value", ["0", "1001", "-1", "1.5", "invalid", ""])
def test_judge_rejects_invalid_budget(tmp_path, monkeypatch, value):
    monkeypatch.setenv("HISABGUARD_JUDGE_MODE", "1")
    monkeypatch.setenv("HISABGUARD_ACCESS_TOKEN", TOKEN)
    monkeypatch.setenv("HISABGUARD_JUDGE_MAX_RUNS", value)
    directory = tmp_path / "judge"
    with pytest.raises(RuntimeError, match="integer from 1 to 1000"):
        with TestClient(create_app(directory)):
            pass
    assert not directory.exists()


@pytest.mark.parametrize("value", ["1", "1000"])
def test_explicit_environment_directory_and_budget(tmp_path, monkeypatch, value):
    monkeypatch.setenv("HISABGUARD_JUDGE_MODE", "1")
    monkeypatch.setenv("HISABGUARD_ACCESS_TOKEN", TOKEN)
    monkeypatch.setenv("HISABGUARD_DATA_DIR", str(tmp_path / "judge"))
    monkeypatch.setenv("HISABGUARD_JUDGE_MAX_RUNS", value)
    with TestClient(create_app(), headers=AUTH) as connection:
        assert connection.get("/api/status").json()["judge_runs_remaining"] == int(value)
        assert connection.app.state.store.data_dir == (tmp_path / "judge").resolve()


@pytest.mark.parametrize("mode", [None, "0", "true", "01"])
def test_only_exact_full_name_flag_enables_judge(tmp_path, monkeypatch, mode):
    if mode is not None:
        monkeypatch.setenv("HISABGUARD_JUDGE_MODE", mode)
    monkeypatch.setenv("HISABGUARD_ACCESS_TOKEN", TOKEN)
    with TestClient(create_app(tmp_path / "normal"), headers=AUTH) as connection:
        status = connection.get("/api/status").json()
        assert status["judge_mode"] is False
        assert status["uploads_enabled"] is True
        assert status["judge_runs_remaining"] is None
        before = connection.get("/api/trips").json()
        assert connection.post("/api/demo/reset").status_code == 403
        assert connection.get("/api/trips").json() == before
        trip_id = trip_ids(connection)[0]
        row = connection.post(f"/api/trips/{trip_id}/evidence", json={
            "kind": "statement", "title": "Normal record", "text": "Not a synthetic label"}).json()["evidence"][-1]
        assert row["synthetic"] is False
        reply = connection.post(f"/api/trips/{trip_id}/reply", json={"text": "Normal reply"})
        assert reply.json()["evidence"][-1]["synthetic"] is False
        image = BytesIO()
        Image.new("RGB", (10, 10)).save(image, "PNG")
        uploaded = connection.post(f"/api/trips/{trip_id}/upload", data={"title": "Normal original", "kind_hint": "payment"},
                                   files={"file": ("receipt.png", image.getvalue(), "image/png")})
        assert uploaded.status_code == 200
        evidence = uploaded.json()["evidence"][-1]
        assert evidence["synthetic"] is False
        assert connection.get(f"/api/evidence/{evidence['id']}/file").content == image.getvalue()


def test_manual_evidence_and_replies_are_synthetic(client):
    trip_id = trip_ids(client)[0]
    initial = client.get(f"/api/trips/{trip_id}").json()
    response = client.post(f"/api/trips/{trip_id}/evidence", json={
        "kind": "payment", "title": "Synthetic example payment", "amount_bdt": "7000.00"})
    assert response.status_code == 200
    row = response.json()["evidence"][-1]
    assert row["synthetic"] is True and row["state"] == "draft"
    assert response.json()["settlement"]["received_bdt"] == initial["settlement"]["received_bdt"]
    reviewed = client.post(f"/api/evidence/{row['id']}/review", json={"decision": "confirm"})
    assert reviewed.status_code == 200 and reviewed.json()["evidence"][-1]["synthetic"] is True
    response = client.post(f"/api/trips/{trip_id}/reply", json={"text": "Synthetic promise, not a payment"})
    assert response.status_code == 200
    reply = response.json()["evidence"][-1]
    assert reply["synthetic"] is True and reply["state"] == "confirmed" and reply["kind"] == "statement"
    assert "synthetic: True" in client.get(f"/api/trips/{trip_id}/report").text
    assert client.post("/api/demo/reset").status_code == 200


def test_upload_disabled_but_original_viewing_preserved(client):
    trip_id = trip_ids(client)[0]
    before = client.get(f"/api/trips/{trip_id}").json()
    original = before["evidence"][0]
    binary = client.get(f"/api/evidence/{original['id']}/file").content
    files_before = sorted(client.app.state.store.originals.iterdir())
    response = client.post(f"/api/trips/{trip_id}/upload", data={"title": "Private file", "kind_hint": "payment"},
                           files={"file": ("receipt.png", b"not a real image", "image/png")})
    assert response.status_code == 403
    assert client.post(f"/api/trips/{trip_id}/upload").status_code == 403
    assert client.get(f"/api/trips/{trip_id}").json() == before
    assert sorted(client.app.state.store.originals.iterdir()) == files_before
    assert client.get(f"/api/evidence/{original['id']}/file").content == binary


def test_reset_reseeds_queue_and_audit_without_unlinking_originals(client):
    trip_id = trip_ids(client)[0]
    client.post(f"/api/trips/{trip_id}/investigate")
    client.post(f"/api/trips/{trip_id}/reply", json={"text": "Synthetic response"})
    assert client.post("/api/trips", json={"customer": "Synthetic extra", "driver": "Synthetic driver", "truck": "TEST"}).status_code == 200
    repository = client.app.state.store
    retained = repository.originals / "retained-original.bin"
    retained.write_bytes(b"retained private original")
    db_path = repository.db_path
    response = client.post("/api/demo/reset")
    assert response.status_code == 200
    queue = response.json()
    assert queue == client.get("/api/trips").json()
    assert queue["overview"]["trips"] == 3
    assert {row["code"] for row in queue["trips"]} == {"TRIP-104", "TRIP-106", "TRIP-108"}
    assert queue["overview"]["pending_approvals"] == 0
    assert retained.read_bytes() == b"retained private original" and db_path.is_file()
    with repository.connect() as db:
        assert not db.execute("PRAGMA foreign_key_check").fetchall()
        assert not db.execute("SELECT 1 FROM evidence WHERE synthetic!=1").fetchone()
        assert db.execute("SELECT COUNT(*) FROM investigations").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM actions").fetchone()[0] == 0
    activity = client.get("/api/activity").json()["activity"]
    assert activity[-1]["event"] == "demo_reset" and activity[-1]["detail"]["synthetic"] is True
    assert str(repository.data_dir) not in response.text
    assert "demo_reset" not in agent.TOOL_MODELS


def test_model_budget_counts_failure_and_survives_reset(client, monkeypatch):
    client.app.state.judge_max_runs = 2
    trip_id = trip_ids(client)[0]
    attempts = []

    def failure(*args):
        attempts.append(1)
        raise providers.ProviderError("private upstream detail")

    model(monkeypatch, failure)
    assert client.post("/api/trips/999999/investigate").status_code == 404
    assert client.get("/api/status").json()["judge_runs_remaining"] == 2
    failed = client.post(f"/api/trips/{trip_id}/investigate")
    assert failed.status_code == 502 and "private upstream" not in failed.text
    detail = client.get(f"/api/trips/{trip_id}").json()
    assert detail["investigations"][-1]["status"] == "failed"
    assert detail["investigations"][-1]["mode"] == "model" and not detail["actions"]
    assert client.get("/api/status").json()["judge_runs_remaining"] == 1
    assert client.post("/api/demo/reset").status_code == 200
    assert client.get("/api/status").json()["judge_runs_remaining"] == 1
    model(monkeypatch)
    assert client.post(f"/api/trips/{trip_ids(client)[0]}/investigate").status_code == 200
    assert client.get("/api/status").json()["judge_runs_remaining"] == 0
    assert client.post("/api/demo/reset").status_code == 200
    assert client.post(f"/api/trips/{trip_ids(client)[0]}/investigate").status_code == 429
    assert client.get("/api/status").json()["judge_runs_remaining"] == 0
    assert len(attempts) == 1


def test_demo_review_does_not_consume_model_budget(client):
    trip_id = trip_ids(client)[0]
    response = client.post(f"/api/trips/{trip_id}/investigate")
    assert response.status_code == 200 and response.json()["investigations"][-1]["mode"] == "demo"
    assert client.get("/api/status").json()["judge_runs_remaining"] == 20


def test_active_model_serializes_all_trips_and_refuses_reset(client, monkeypatch):
    first, second, *_ = trip_ids(client)
    entered, release = threading.Event(), threading.Event()

    def turn(*args):
        entered.set()
        assert release.wait(10), "Test must release blocked provider"
        return {"tool_calls": [{"id": "finish", "type": "function", "function": {
            "name": "finish_investigation", "arguments": json.dumps({"summary": "Test review", "evidence_ids": []})}}]}

    model(monkeypatch, turn)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(client.post, f"/api/trips/{first}/investigate")
        try:
            assert entered.wait(10)
            assert client.get("/api/status").json()["judge_runs_remaining"] == 19
            assert client.post(f"/api/trips/{second}/investigate").status_code == 409
            assert client.post("/api/demo/reset").status_code == 409
            assert client.get("/api/status").json()["judge_runs_remaining"] == 19
            with pytest.raises(StoreError) as error:
                client.app.state.store.reset_demo()
            assert error.value.status == 409
        finally:
            release.set()
        assert future.result(timeout=10).status_code == 200
    assert client.post("/api/demo/reset").status_code == 200
    assert client.get("/api/status").json()["judge_runs_remaining"] == 19


def test_reset_refuses_non_synthetic_evidence_without_changes(client):
    repository = client.app.state.store
    ordinary_store = Store(repository.data_dir)
    ordinary_store.add_evidence(trip_ids(client)[0], {"kind": "statement", "title": "Accidental normal data", "text": "Retain this"})
    before = client.get("/api/export").json()
    response = client.post("/api/demo/reset")
    assert response.status_code == 409 and "non-synthetic" in response.json()["detail"]
    assert client.get("/api/export").json() == before


def test_reset_deletions_roll_back_transactionally(client):
    repository = client.app.state.store
    before = client.get("/api/export").json()
    with repository.connect(True) as db:
        db.execute("CREATE TRIGGER refuse_clear BEFORE DELETE ON trips BEGIN SELECT RAISE(ABORT, 'test failure'); END")
    assert client.post("/api/demo/reset").status_code == 503
    assert client.get("/api/export").json() == before


def test_reset_seed_failure_rolls_back_all_table_data(client, monkeypatch):
    before = client.get("/api/export").json()

    def fail_seed(store):
        with store.connect(True) as db:
            store.insert_trip(db, {"customer": "Partial seed", "driver": "Synthetic driver", "truck": "TEST"})
        raise StoreError(503, "Synthetic fixture seed unavailable")

    monkeypatch.setattr(demo, "seed", fail_seed)
    assert client.post("/api/demo/reset").status_code == 503
    assert client.get("/api/export").json() == before


def test_separate_normal_store_untouched_by_judge_reset(client, tmp_path):
    production = Store(tmp_path / "normal-runtime")
    demo.seed(production)
    with production.connect() as db:
        first = db.execute("SELECT id FROM trips ORDER BY id").fetchone()[0]
    production.add_evidence(first, {"kind": "statement", "title": "Private normal evidence", "text": "Never clear"})
    before = production.detail(first)
    files = {path.name: path.read_bytes() for path in production.originals.iterdir()}
    with pytest.raises(StoreError) as error:
        production.reset_demo()
    assert error.value.status == 403
    assert client.post("/api/demo/reset").status_code == 200
    assert production.detail(first) == before
    assert {path.name: path.read_bytes() for path in production.originals.iterdir()} == files


def test_direct_judge_store_rejects_default_and_production_paths():
    for directory in (None, ROOT / "runtime"):
        with pytest.raises(RuntimeError, match="isolated data directory"):
            Store(directory, judge_mode=True)

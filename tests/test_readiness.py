import json
import os

import pytest

from app import demo, providers
from app.store import Store
from scripts.evaluate import CallBudget, DATA, fixture, score
from scripts.provider_env import configure_openrouter


def test_model_clarification_is_approval_draft_not_sent(tmp_path, monkeypatch):
    from app import agent
    dataset = json.loads(DATA.read_text(encoding="utf-8"))
    store = Store(tmp_path)
    trip_id = fixture(store, dataset["cases"][0], dataset["base"], 1)
    initial = store.detail(trip_id)
    source_ids = initial["settlement"]["sources"]["outstanding_bdt"]
    question = "Please provide the transaction receipt for BDT 7000.00."
    monkeypatch.setattr(providers, "get_status", lambda: {"model_configured": True})
    calls = [{"id": "q", "type": "function", "function": {"name": "request_clarification", "arguments": json.dumps({"recipient": "customer", "question": question, "evidence_ids": source_ids})}},
             {"id": "f", "type": "function", "function": {"name": "finish_investigation", "arguments": json.dumps({"summary": "Receipt needed", "evidence_ids": source_ids})}}]
    monkeypatch.setattr(providers, "agent_turn", lambda *args: {"tool_calls": calls})
    agent.investigate(store, trip_id)
    result = store.detail(trip_id)
    assert result["actions"][0]["status"] == "pending"
    assert result["actions"][0]["message"].endswith(question)
    assert result["settlement"] == initial["settlement"]
    assert result["trip"]["status"] == "awaiting_response"


def test_opt_in_mapping_is_memory_only(monkeypatch, capsys):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-private-key")
    for key in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL", "VISION_MODEL", "REASONING_MODE"):
        monkeypatch.delenv("HISABGUARD_" + key, raising=False)
    info = configure_openrouter()
    assert "key" not in json.dumps(info)
    assert not capsys.readouterr().out
    assert os.environ["HISABGUARD_LLM_API_KEY"] == "test-private-key"
    assert providers.get_status()["model_name"] == "openai/gpt-4.1-mini"


def test_missing_opt_in_credential_refuses(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="unavailable"):
        configure_openrouter()


def test_live_call_budget_is_enforced():
    budget = CallBudget(1)
    assert budget.call(lambda: "ok") == "ok"
    with pytest.raises(providers.ProviderError, match="budget"):
        budget.call(lambda: "must not run")


def test_baseline_is_existing_reviewer_and_not_a_strawman(tmp_path):
    dataset = json.loads(DATA.read_text(encoding="utf-8"))
    store = Store(tmp_path)
    results = []
    for index, case in enumerate(dataset["cases"], 1):
        trip_id = fixture(store, case, dataset["base"], index)
        detail = store.detail(trip_id)
        review = demo.review(detail)
        results.append(score(case, review["question"], review["recipient"])["route_match"])
        assert case["label"] not in json.dumps(detail)
        assert "expected_roles" not in json.dumps(detail)
    assert results == [True, False, False, True, True, True]


def test_scorer_discloses_recipient_and_keyword_failures():
    case = {"require_question": True, "expected_roles": ["driver"], "evidence_keywords": ["weighbridge"]}
    assert score(case, "Please obtain the weighbridge slip", "Synthetic driver")["route_match"]
    assert not score(case, "Please pay the balance", "customer")["route_match"]
    assert not score(case, "Please pay the balance", "driver")["evidence_target_match"]


def test_latest_statement_is_explicit_in_model_reassessment_context(tmp_path, monkeypatch):
    from app import agent
    dataset = json.loads(DATA.read_text(encoding="utf-8"))
    store = Store(tmp_path)
    trip_id = fixture(store, dataset["cases"][0], dataset["base"], 1)
    latest_id = store.add_evidence(trip_id, {"title": "New response", "kind": "statement", "text": "Driver now holds the cash."}, synthetic=True, confirmed=True)
    seen = []
    monkeypatch.setattr(providers, "get_status", lambda: {"model_configured": True})
    def turn(messages, tools):
        seen.append(json.loads(messages[1]["content"])["records"])
        return {"tool_calls": [{"id": "finish", "type": "function", "function": {"name": "finish_investigation", "arguments": json.dumps({"summary": "Review", "evidence_ids": []})}}]}
    monkeypatch.setattr(providers, "agent_turn", turn)
    agent.investigate(store, trip_id)
    assert seen[0]["statement_timeline"][-1]["id"] == latest_id
    assert seen[0]["statement_timeline"][-1]["text"] == "Driver now holds the cash."

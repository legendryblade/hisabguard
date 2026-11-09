"""Preregistered synthetic evaluation; live calls require an explicit --live flag."""

import argparse
import hashlib
import json
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import agent, demo, providers
from app.store import Store, StoreError
from scripts.provider_env import configure_openrouter

DATA = ROOT / "data" / "evaluation.json"


class CallBudget:
    def __init__(self, limit, min_interval=0):
        self.limit = limit
        self.used = 0
        self.errors = []
        self.min_interval = min_interval
        self.last_started = None

    def call(self, function, *args):
        if self.used >= self.limit:
            raise providers.ProviderError("Explicit live-call budget reached.")
        if self.last_started is not None:
            wait = self.min_interval - (time.monotonic() - self.last_started)
            if wait > 0:
                time.sleep(wait)
        self.last_started = time.monotonic()
        self.used += 1
        try:
            return function(*args)
        except providers.ProviderError as exc:
            self.errors.append(str(exc))
            raise


def fixture(store, case, base, index):
    """Expected decisions and semantic scenario labels never enter model inputs."""
    code = f"EVAL-{index:03d}"
    trip_id = store.create_trip({"code": code, "customer": "Synthetic customer", "driver": "Synthetic driver",
                                 "truck": "SYNTHETIC-01", "origin": "Gazipur", "destination": "Dhaka"})
    records = [("invoice", base["invoice_bdt"], "INV"),
               ("payment", case.get("payment_bdt", base["payment_bdt"]), "PAY"),
               ("expense", base["expense_bdt"], "FUEL"),
               ("advance", base["advance_bdt"], "ADV")]
    if case.get("duplicate_expense"):
        records.append(("expense", base["expense_bdt"], "FUEL"))
    if case.get("cash_return_bdt"):
        records.append(("cash_return", case["cash_return_bdt"], "RETURN"))
    for kind, amount, transaction in records:
        store.add_evidence(trip_id, {"title": "Synthetic " + kind, "kind": kind, "amount_bdt": amount,
                                    "trip_ref": code, "transaction_id": code + "-" + transaction,
                                    "note": "SYNTHETIC controlled fixture, not external verification."},
                           synthetic=True, confirmed=True)
    if case.get("delivered", base["delivered"]):
        store.add_evidence(trip_id, {"title": "Synthetic signed delivery record", "kind": "delivery",
                                    "delivered": True, "trip_ref": code}, synthetic=True, confirmed=True)
    store.add_evidence(trip_id, {"title": "Synthetic conversation statement", "kind": "statement",
                                "text": case["statement"], "trip_ref": code}, synthetic=True, confirmed=True)
    return trip_id


def score(case, question, recipient):
    """Disclosed lexical/recipient proxy, not a hidden second model or real-world verdict."""
    if not case["require_question"]:
        return {"route_match": not question, "recipient_match": not recipient, "evidence_target_match": not question}
    normalized_recipient = (recipient or "").casefold()
    recipient_match = any(role in normalized_recipient for role in case["expected_roles"])
    question_match = any(keyword in (question or "").casefold() for keyword in case["evidence_keywords"])
    return {"route_match": bool(question) and recipient_match and question_match,
            "recipient_match": recipient_match, "evidence_target_match": question_match}


def check_handshake(budget):
    result = budget.call(providers.agent_turn,
                         [{"role": "system", "content": "This is a synthetic capability check. Call get_trip_records exactly once for trip_id 1. Do not invent evidence or answer in prose."},
                          {"role": "user", "content": "Inspect synthetic trip 1 with the supplied tool."}],
                         [tool for tool in agent.TOOLS if tool["function"]["name"] == "get_trip_records"])
    calls = result.get("tool_calls", [])
    if len(calls) != 1 or calls[0].get("function", {}).get("name") != "get_trip_records":
        raise providers.ProviderError("Model failed the bounded tool-calling capability check.")
    args = json.loads(calls[0]["function"]["arguments"], object_pairs_hook=agent._unique_object)
    if args != {"trip_id": 1}:
        raise providers.ProviderError("Model returned invalid capability-check arguments.")


def run(live=False, max_calls=32, selected=None, pace_seconds=0, ocr_only=False):
    dataset = json.loads(DATA.read_text(encoding="utf-8"))
    output = {"version": "hisabguard.evaluation-result.v1", "recorded_at": datetime.now(timezone.utc).isoformat(),
              "dataset_version": dataset["version"], "scope": dataset["scope"], "rubric": dataset["rubric"],
              "dataset_sha256": hashlib.sha256(DATA.read_bytes()).hexdigest(),
              "agent_sha256": hashlib.sha256((ROOT / "app" / "agent.py").read_bytes()).hexdigest(),
              "provider_request_spacing_seconds": pace_seconds,
              "evaluation_stage": "ocr_only" if ocr_only else "routing_and_ocr",
              "baseline": "Actual app.demo.review deterministic reviewer, not an empty or intentionally weakened baseline.",
              "mode": "live" if live else "baseline_only", "model": providers.get_status()["model_name"] if live else None,
              "cases": [], "ocr": [], "live_calls": 0,
              "limits": "Synthetic sample; lexical scoring is a proxy. Not real document, STT, customer-impact, safety-rate or latency validation."}
    budget = CallBudget(max_calls, pace_seconds)
    original_turn = providers.agent_turn
    if live:
        if not providers.get_status()["model_configured"]:
            raise providers.ProviderError("Configure a reasoning model before requesting live evaluation.")
        if not ocr_only:
            check_handshake(budget)
        providers.agent_turn = lambda messages, tools: budget.call(original_turn, messages, tools)
    try:
        with tempfile.TemporaryDirectory(prefix="hisabguard-eval-") as directory:
            store = Store(directory)
            for index, case in enumerate(dataset["cases"], 1):
                if ocr_only:
                    continue
                if selected and case["id"] not in selected:
                    continue
                trip_id = fixture(store, case, dataset["base"], index)
                initial = store.detail(trip_id)
                baseline = demo.review(initial)
                result = {"id": case["id"], "label": case["label"], "statement": case["statement"],
                          "expected_roles": case["expected_roles"], "evidence_keywords": case["evidence_keywords"],
                          "baseline": {"question": baseline["question"], "recipient": baseline["recipient"],
                                       **score(case, baseline["question"], baseline["recipient"])},
                          "accounting_before": initial["settlement"], "model_result": None}
                if live:
                    started = time.monotonic()
                    call_start = budget.used
                    error_start = len(budget.errors)
                    error = None
                    try:
                        agent.investigate(store, trip_id)
                    except StoreError as exc:
                        error = exc.detail
                    after = store.detail(trip_id)
                    investigation = after["investigations"][-1]
                    result["model_result"] = {"status": investigation["status"], "error": error,
                                               "question": investigation["question"], "recipient": investigation["recipient"],
                                               "tools": [step["tool"] for step in investigation["steps"]],
                                               "tool_errors": [step["result"]["error"] for step in investigation["steps"]
                                                               if isinstance(step["result"], dict) and step["result"].get("error")],
                                               "provider_errors": budget.errors[error_start:],
                                               "seconds": round(time.monotonic() - started, 2), "calls": budget.used - call_start,
                                               "ledger_unchanged": after["settlement"] == initial["settlement"],
                                               **score(case, investigation["question"], investigation["recipient"])}
                    if error:
                        result["model_result"]["route_match"] = False
                output["cases"].append(result)
                print(case["id"] + ": baseline=" + str(result["baseline"]["route_match"])
                      + (" model=" + str(result["model_result"]["route_match"]) if live else " (not run)"))
                if live and budget.used >= max_calls:
                    output["budget_exhausted"] = True
                    break

            if live and (ocr_only or not selected) and providers.get_status()["vision_configured"]:
                demo.seed(Store(Path(directory) / "ocr"))
                originals = Store(Path(directory) / "ocr")
                detail = originals.detail(1)
                for evidence in detail["evidence"][:3]:
                    if budget.used >= max_calls:
                        output["budget_exhausted"] = True
                        break
                    started = time.monotonic()
                    image = originals.original_path(evidence["id"])[0].read_bytes()
                    expected = {key: evidence[key] for key in ("kind", "amount_bdt", "transaction_id", "trip_ref")}
                    try:
                        proposal = budget.call(providers.extract_image, image, "image/png")
                        matched = all(proposal.get(key) == value for key, value in expected.items())
                        row = {"expected": expected, "proposal": proposal, "fields_match": matched, "error": None}
                    except providers.ProviderError as exc:
                        row = {"expected": expected, "proposal": None, "fields_match": False, "error": str(exc)}
                    row["seconds"] = round(time.monotonic() - started, 2)
                    output["ocr"].append(row)
                    print("OCR " + evidence["kind"] + ": " + str(row["fields_match"]))
    finally:
        providers.agent_turn = original_turn
    output["live_calls"] = budget.used
    output["summary"] = {"cases": len(output["cases"]),
                         "baseline_matches": sum(case["baseline"]["route_match"] for case in output["cases"]),
                         "model_matches": sum(case["model_result"]["route_match"] for case in output["cases"]) if live else None,
                         "model_failures": sum(bool(case["model_result"]["error"]) for case in output["cases"]) if live else None,
                         "accounting_unchanged": all(case["model_result"]["ledger_unchanged"] for case in output["cases"]) if live else None,
                         "ocr_matches": sum(row["fields_match"] for row in output["ocr"]), "ocr_cases": len(output["ocr"])}
    return output


def main():
    parser = argparse.ArgumentParser(description="Evaluate synthetic HisabGuard evidence routing; no paid calls without --live.")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--provider", choices=["configured", "openrouter"], default="configured")
    parser.add_argument("--model", default="openai/gpt-4.1-mini")
    parser.add_argument("--reasoning", choices=["default", "off"], default="default")
    parser.add_argument("--max-calls", type=int, choices=range(1, 65), default=32)
    parser.add_argument("--pace-seconds", type=float, default=0, help="Minimum interval between provider request starts; included in timing disclosure.")
    parser.add_argument("--case", action="append", dest="selected")
    parser.add_argument("--ocr-only", action="store_true", help="Test the three vision fixtures without repeating reasoning calls.")
    parser.add_argument("--output", default="artifacts/evaluation-live.json")
    args = parser.parse_args()
    if not 0 <= args.pace_seconds <= 20:
        parser.error("pace-seconds must be between 0 and 20")
    if args.ocr_only and (not args.live or args.selected):
        parser.error("ocr-only requires --live and cannot be combined with --case")
    valid_cases = {case["id"] for case in json.loads(DATA.read_text(encoding="utf-8"))["cases"]}
    if args.selected and not set(args.selected) <= valid_cases:
        parser.error("Unknown case id; available cases: " + ", ".join(sorted(valid_cases)))
    if args.provider == "openrouter":
        configure_openrouter(args.model, args.reasoning)
    try:
        result = run(args.live, args.max_calls, args.selected, args.pace_seconds, args.ocr_only)
    except providers.ProviderError as exc:
        print("Live evaluation blocked: " + str(exc))
        return 1
    output = ROOT / args.output
    if not output.resolve().is_relative_to(ROOT):
        raise ValueError("Evaluation output must remain in the project directory")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["summary"]))
    print("Result: " + str(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

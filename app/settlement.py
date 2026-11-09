"""Independent ledger validator; model text is never a financial input."""

from collections import defaultdict
import re

from .schemas import FINANCIAL_KINDS


def bdt(paisa: int) -> str:
    sign = "-" if paisa < 0 else ""
    paisa = abs(paisa)
    return f"{sign}{paisa // 100}.{paisa % 100:02d}"


def transaction_key(value):
    return value.strip().casefold() if value else ""


def validate_followup(detail, followup):
    """Check labelled currency figures, not the truth of unrestricted model prose."""
    message = followup["message"].translate(str.maketrans("\u09e6\u09e7\u09e8\u09e9\u09ea\u09eb\u09ec\u09ed\u09ee\u09ef", "0123456789"))
    if re.search(r"\b(?:proof of fraud|(?:proven|confirmed|verified)\s+fraud|fraud\s+(?:(?:is|was)\s+)?(?:proven|confirmed|verified))\b", message, re.IGNORECASE):
        raise ValueError("Follow-up drafts cannot assert proof of fraud")
    cited = set(followup["evidence_ids"])
    for reference in re.finditer(r"\bevidence\s*(?:ids?\s*)?#\s*([0-9]+)", message, re.IGNORECASE):
        if int(reference.group(1)) not in cited:
            raise ValueError("Follow-up evidence references must be included in its cited evidence ids")
    currency = r"(?:(?<![^\W\d])(?:BDT|Tk|taka)(?![^\W\d])\.?|\u09f3)"
    for candidate in re.finditer(rf"{currency}\s*:?\s*[+-]?\d[\d,.]*|[+-]?\d[\d,.]*\s*{currency}", message, re.IGNORECASE):
        if any(character.isdecimal() and character not in "0123456789" for character in candidate.group()):
            raise ValueError("Follow-up currency digits must use supported decimal notation")
    if re.search(rf"{currency}\s*:?\s*[+-]?(?:NaN|Infinity|inf)\b|\b[+-]?(?:NaN|Infinity|inf)\s*{currency}", message, re.IGNORECASE):
        raise ValueError("Follow-up currency figures must be finite decimal amounts")
    number = r"[+-]?[0-9]+(?:,[0-9]+)*(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?"
    tokens = list(re.finditer(rf"{currency}\s*:?\s*(?P<prefix>{number})|(?P<suffix>{number})\s*{currency}(?!\w)", message, re.IGNORECASE))
    if not tokens:
        return
    settlement = detail["settlement"]
    # Each total below is usable only when ALL of its own sources are cited.
    # A fuel receipt must not require unrelated customer-account evidence.
    allowed = {int(settlement[column].replace(".", "")) for column, ids in settlement["sources"].items() if set(ids) <= cited and (ids or settlement[column] == "0.00")}
    allowed.update(int(row["amount_bdt"].replace(".", "")) for row in detail["evidence"]
                   if row["id"] in cited and row["state"] == "confirmed" and row["kind"] in FINANCIAL_KINDS and row["amount_bdt"] is not None)
    for token in tokens:
        if token.group("suffix") and token.start() and re.match(r"[\w.,+-]", message[token.start() - 1]):
            raise ValueError("Follow-up currency figure has an unsupported or ambiguous numeric prefix")
        amount = token.group("prefix") or token.group("suffix")
        if len(amount) > 64 or not re.fullmatch(r"-?(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+|[0-9]{1,2}(?:,[0-9]{2})*,[0-9]{3})(?:\.[0-9]{1,2})?", amount):
            raise ValueError("Follow-up currency figures must be explicit decimal amounts with at most two decimal places")
        # Reject abbreviated or malformed labelled figures instead of accepting their
        # numeric prefix (for example BDT 7k, 7.00.01 or 7 lakh).
        tail = message[token.end():]
        if token.group("prefix") and (re.match(r"\w|[.,][.,0-9]|\s*(?:k|m|b|lakh|lac|crore|million|billion|thousand|\u09b2\u09be\u0996|\u0995\u09cb\u099f\u09bf|\u09b9\u09be\u099c\u09be\u09b0)\b", tail, re.IGNORECASE)):
            raise ValueError("Follow-up currency figure has an unsupported or ambiguous numeric suffix")
        normalized = amount.replace(",", "")
        integer, _, fraction = normalized.partition(".")
        paisa = int(integer) * 100 + (-1 if normalized.startswith("-") else 1) * int(fraction.ljust(2, "0") or "0")
        if paisa not in allowed:
            raise ValueError("Follow-up currency figure is not supported by all required total sources or confirmed cited evidence")


def calculate(trip_id: int, evidence: list[dict]) -> dict:
    rows = [row for row in evidence if row["trip_id"] == trip_id]
    confirmed = [row for row in evidence if row["state"] == "confirmed"]
    issues = []

    def issue(code, title, detail, ids, severity="blocking"):
        issues.append({"code": code, "severity": severity, "title": title,
                       "detail": detail, "evidence_ids": sorted(set(ids))})

    drafts = [row["id"] for row in rows if row["state"] == "draft"]
    if drafts:
        issue("unreviewed_evidence", "Evidence needs human review", "Draft records are not included in arithmetic.", drafts)

    duplicate_ids = set()
    transactions, hashes = defaultdict(list), defaultdict(list)
    for row in confirmed:
        if transaction_key(row.get("transaction_id")) and row["kind"] in FINANCIAL_KINDS:
            transactions[transaction_key(row["transaction_id"])].append(row)
        if row.get("file_hash"):
            hashes[row["file_hash"]].append(row)
    for groups, code, title in ((transactions, "duplicate_transaction", "Repeated transaction id"),
                                (hashes, "duplicate_file", "Repeated original file")):
        for group in groups.values():
            if len(group) < 2:
                continue
            group.sort(key=lambda row: row["id"])
            duplicate_ids.update(row["id"] for row in group[1:])
            if any(row["trip_id"] == trip_id for row in group):
                local_ids = [row["id"] for row in group if row["trip_id"] == trip_id]
                issue(code, title, "This identifier also appears in confirmed evidence; count at most once across all trips. Exclude the duplicate to resolve it.", local_ids)

    active = [row for row in rows if row["state"] == "confirmed"]
    invoices = [row for row in active if row["kind"] == "invoice"]
    usable = [row for row in active if row["id"] not in duplicate_ids]
    totals = {}
    sources = {}
    for kind, column in (("invoice", "invoice_bdt"), ("payment", "received_bdt"),
                         ("expense", "expense_bdt"), ("advance", "advance_bdt"),
                         ("cash_return", "cash_return_bdt")):
        selected = [row for row in usable if row["kind"] == kind]
        if kind == "invoice" and len(invoices) > 1:
            selected = []
        totals[column] = sum(row["amount_paisa"] or 0 for row in selected)
        sources[column] = [row["id"] for row in selected]

    if not invoices:
        issue("missing_invoice", "Invoice missing", "A reviewed invoice is required; statements are not invoices.", [])
    elif len(invoices) > 1:
        issue("conflicting_invoices", "Multiple invoice records", "Invoice expectations are withheld, not summed. Resolve the conflicting records.", [row["id"] for row in invoices])
    elif not totals["invoice_bdt"]:
        issue("zero_invoice", "No positive invoice expectation", "A zero or withheld invoice cannot establish a completed settlement.", [invoices[0]["id"]])

    outstanding = totals["invoice_bdt"] - totals["received_bdt"]
    balance = totals["advance_bdt"] - totals["expense_bdt"] - totals["cash_return_bdt"]
    totals["outstanding_bdt"] = outstanding
    totals["advance_balance_bdt"] = balance
    sources["outstanding_bdt"] = sorted(set(sources["invoice_bdt"] + sources["received_bdt"]))
    sources["advance_balance_bdt"] = sorted(set(sources["advance_bdt"] + sources["expense_bdt"] + sources["cash_return_bdt"]))
    if outstanding > 0:
        issue("outstanding_payment", "Payment outstanding", f"BDT {bdt(outstanding)} remains unsupported by received-payment evidence.", sources["outstanding_bdt"])
    elif outstanding < 0 and len(invoices) == 1 and totals["invoice_bdt"] > 0:
        issue("overpayment", "Payment exceeds invoice", f"BDT {bdt(-outstanding)} excess must be resolved.", sources["outstanding_bdt"])
    if balance:
        issue("advance_balance", "Advance accounting incomplete", f"Advance less expenses and cash returned is BDT {bdt(balance)}; it must be zero.", sources["advance_balance_bdt"])
    delivery = [row["id"] for row in usable if row["kind"] == "delivery" and row["delivered"] is True]
    delivery_records = [row for row in active if row["kind"] == "delivery"]
    delivery_conflict = {row["delivered"] for row in delivery_records} >= {True, False}
    if delivery_conflict:
        issue("conflicting_delivery", "Conflicting delivery records", "Confirmed records disagree on whether delivery completed. Exclude or explicitly correct the conflicting record before settlement.", [row["id"] for row in delivery_records])
    if not delivery:
        issue("missing_delivery", "Delivery proof missing", "Confirmed delivery evidence with delivered=true is required.", [row["id"] for row in delivery_records])
    for row in active:
        if row["kind"] == "statement":
            issue("statement_not_payment", "Statement is not a payment", "Promises and conversation do not change money received.", [row["id"]], "warning")
    return {**{column: bdt(value) for column, value in totals.items()},
            "delivery_confirmed": bool(delivery) and not delivery_conflict,
            "can_settle": bool(delivery) and len(invoices) == 1 and totals["invoice_bdt"] > 0
                          and outstanding == 0 and balance == 0
                          and not any(item["severity"] == "blocking" for item in issues),
            "issues": issues, "sources": sources}

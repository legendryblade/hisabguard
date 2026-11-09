"""Explicitly synthetic fixtures and a disclosed deterministic review mode."""

import hashlib
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont


def seed(store):
    with store.connect(True) as db:
        if db.execute("SELECT COUNT(*) FROM trips").fetchone()[0]:
            return
        fixtures = [("TRIP-104", "Demo: Gazipur textiles", "Demo driver Jalal", "DEMO-TRUCK-01", "Dhaka"),
                    ("TRIP-106", "Demo: Narayanganj supplier", "Demo driver Hasan", "DEMO-TRUCK-02", "Narayanganj"),
                    ("TRIP-108", "Demo: Mymensingh wholesaler", "Demo driver Rafiq", "DEMO-TRUCK-03", "Mymensingh")]
        for code, customer, driver, truck, destination in fixtures:
            trip_id = store.insert_trip(db, {"code": code, "customer": customer,
                "driver": driver, "truck": truck, "origin": "Gazipur (demo)", "destination": destination + " (demo)"})
            records = [
                {"kind": "invoice", "amount_bdt": "32000.00", "transaction_id": code + "-INV"},
                {"kind": "payment", "amount_bdt": "25000.00", "transaction_id": code + "-PAY"},
                {"kind": "expense", "amount_bdt": "3500.00", "transaction_id": code + "-FUEL"},
                {"kind": "advance", "amount_bdt": "5000.00", "transaction_id": code + "-ADV"},
            ]
            if code != "TRIP-106":
                records.append({"kind": "delivery", "delivered": True})
            if code == "TRIP-104":
                records.append({"kind": "statement", "text": "Synthetic driver statement: customer promises to pay the remaining BDT 7000. This is not a payment."})
            if code == "TRIP-108":
                records.append({"kind": "expense", "amount_bdt": "3500.00", "transaction_id": code + "-FUEL"})
            for index, record in enumerate(records, 1):
                title = f"SYNTHETIC {record['kind']} {index}"
                fields = {**record, "title": title, "trip_ref": code,
                          "note": "SYNTHETIC DEMO ONLY. Explicitly confirmed by synthetic fixture reviewer; no provider or real-world verification."}
                image = Image.new("RGB", (920, 420), "#fff9e8")
                draw = ImageDraw.Draw(image)
                lines = ["SYNTHETIC DEMO - NOT A REAL RECEIPT", code, title,
                         "BDT " + record.get("amount_bdt", "N/A"),
                          "Transaction ID: " + record.get("transaction_id", "not recorded"),
                         "Delivered: " + str(record.get("delivered", "N/A")),
                         "Fixture reviewer: SYNTHETIC OPERATOR", f"Distinct evidence row: {index}"]
                font = ImageFont.load_default(size=23)
                for line_index, line in enumerate(lines):
                    draw.text((30, 30 + line_index * 40), line, fill="#17243a", font=font)
                buffer = BytesIO()
                image.save(buffer, format="PNG")
                data = buffer.getvalue()
                filename = f"synthetic-{code}-{index}.png"
                (store.originals / filename).write_bytes(data)
                store.insert_evidence(db, trip_id, fields, source_type="image", synthetic=True,
                                      confirmed=True, filename=filename, mime="image/png",
                                      file_hash=hashlib.sha256(data).hexdigest())


def independent_summary(detail):
    settlement = detail["settlement"]
    issues = "; ".join(issue["title"] for issue in settlement["issues"] if issue["severity"] == "blocking")
    invoice_withheld = any(issue["code"] in {"missing_invoice", "conflicting_invoices", "zero_invoice"} for issue in settlement["issues"])
    return (f"Independent evidence review: invoice BDT {settlement['invoice_bdt']}; received BDT {settlement['received_bdt']}; "
            f"outstanding BDT {settlement['outstanding_bdt']}; advance balance BDT {settlement['advance_balance_bdt']}. "
            + ("Invoice expectation is missing or withheld; the outstanding figure is not a validated debt or overpayment. " if invoice_withheld else "")
            + ("Blocking issues: " + issues + "." if issues else "No blocking issues. Eligible for local human settlement review.")
            + " Statements are not payment evidence. No external payment or delivery verification was performed.")


def review(detail):
    settlement = detail["settlement"]
    issues = {issue["code"]: issue for issue in settlement["issues"]}
    targets = [
        ("unreviewed_evidence", "owner", "Please review or exclude the draft evidence before treating it as a transaction."),
        ("duplicate_transaction", "owner", "Which repeated transaction record is the original claim? Please review and exclude the duplicate; it has not been counted twice."),
        ("duplicate_file", "owner", "Which trip owns this repeated original document? Please exclude the duplicate claim."),
        ("conflicting_invoices", "owner", "Which reviewed invoice is the valid expectation for this trip? Please exclude the conflicting invoice."),
        ("conflicting_delivery", "owner", "The confirmed delivery records disagree. Which record is correct? Please exclude or correct the contradictory delivery record before settlement."),
        ("missing_invoice", "owner", "Please provide the invoice for this trip and review its amount."),
        ("zero_invoice", "owner", "Please confirm the positive invoice expectation or explain and correct the zero invoice."),
        ("missing_delivery", "driver", "Please provide the signed delivery challan for this trip; a promise is not delivery proof."),
        ("overpayment", "owner", "Please provide evidence resolving the payment exceeding the invoice."),
        ("outstanding_payment", "customer", f"Can you provide a received-payment receipt or transaction record for the outstanding BDT {settlement['outstanding_bdt']}? A promise does not resolve this balance."),
        ("advance_balance", "driver", f"Please account for the BDT {settlement['advance_balance_bdt']} advance balance with a reviewed expense or cash-return record."),
    ]
    selected = next((target for target in targets if target[0] in issues), None)
    ids = sorted({evidence_id for values in settlement["sources"].values() for evidence_id in values})
    if selected:
        code, recipient, question = selected
        ids = sorted(set(ids + issues[code]["evidence_ids"]))
        invoice_unavailable = any(code in issues for code in ("missing_invoice", "conflicting_invoices", "zero_invoice"))
        money_context = (f"Invoice expectation is unavailable or withheld (display BDT {settlement['invoice_bdt']}); "
                         f"received payment BDT {settlement['received_bdt']}; arithmetic difference BDT {settlement['outstanding_bdt']} "
                         "is not a validated debt or overpayment. " if invoice_unavailable else
                         f"Reviewed invoice BDT {settlement['invoice_bdt']}, received payment BDT {settlement['received_bdt']}, "
                         f"outstanding BDT {settlement['outstanding_bdt']}. ")
        message = (f"Demo follow-up draft for {detail['trip']['code']}. {question} "
                   + money_context +
                   "Sources: " + (", ".join(f"evidence #{item}" for item in ids) or "no reviewed financial evidence") + ". "
                   "This is a request for evidence, not a verification or a sent message.")
        followup = {"recipient": recipient, "message": message, "evidence_ids": ids} if ids else None
    else:
        question, recipient, followup = None, None, None
    return {"summary": "Demo mode: deterministic read-only review, not an AI investigation. " + independent_summary(detail),
            "question": question, "recipient": recipient, "evidence_ids": ids, "followup": followup}

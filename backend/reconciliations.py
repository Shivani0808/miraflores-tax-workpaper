"""Independent source-to-engine validations for the synthetic assessment packet.

These checks read extracted source fields separately from engine line values.
They are verification controls, not an independent income tax calculator.
"""
from collections import defaultdict
from decimal import Decimal, InvalidOperation


def numeric(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def reconcile_packet(packet, version="v3"):
    computed = next((v for v in packet["return_versions"] if v["version"] == version), None)
    if computed is None:
        raise ValueError(f"Unknown version: {version}")
    line_map = {x["key"]: x for x in computed["lines"]}
    by_doc = defaultdict(dict)
    for item in packet["extracted_values"]:
        by_doc[item["document_id"]][item["field"]] = item
    docs = {d["id"]: d for d in packet["documents"]}
    checks = []

    def make_check(check_id, title, sources, expected, line_key=None, description="", note=""):
        line = line_map.get(line_key) if line_key else None
        actual = numeric(line["value"]) if line else None
        expected = numeric(expected)
        difference = actual - expected if actual is not None and expected is not None else None
        status = "PASS" if difference == 0 else ("FAIL" if difference is not None else "REVIEW")
        checks.append({
            "id": check_id, "title": title, "status": status,
            "source_total": float(expected) if expected is not None else None,
            "engine_total": float(actual) if actual is not None else None,
            "difference": float(difference) if difference is not None else None,
            "return_line": line_key, "description": description, "note": note,
            "sources": sources,
        })

    # Detect duplicate W-2s using source identity + reported Box 1 and Box 2,
    # not a hardcoded D10 exclusion. Only 2025 W-2s are part of the active return.
    w2_docs = sorted((d for d in packet["documents"] if d["document_type"] == "W-2" and d.get("tax_year") == 2025),key=lambda x: x["id"])
    seen = set()
    kept, excluded = [], []
    for doc in w2_docs:
        f = by_doc[doc["id"]]
        required = ("employer_ein", "employee_ssn", "box1", "box2")
        if any(f.get(field) is None for field in required):
            continue
        signature = tuple(str(f[field]["value"]) for field in required)
        (excluded if signature in seen else kept).append(doc["id"])
        seen.add(signature)
    for field, key, title in [
        ("box1", "F1040.1a", "W-2 Box 1 wages → Form 1040 line 1a"),
        ("box2", "F1040.25a", "W-2 Box 2 withholding → Form 1040 line 25a"),
    ]:
        fields = [by_doc[doc_id].get(field) for doc_id in kept]
        values = [numeric(f["value"]) if f else None for f in fields]
        source_total = sum(values, Decimal(0)) if values and all(x is not None for x in values) else None
        refs = [{"document_id": doc_id,"page": (by_doc[doc_id].get(field) or {}).get("page",1),"field":field,"value":(by_doc[doc_id].get(field) or {}).get("value")} for doc_id in kept]
        make_check("W2-"+field.upper(), title, refs, source_total, key,
            description=f"Sum of {field} from unique 2025 W-2s; exclude source-identical copies.",
            note=("Duplicate documents excluded: " + ", ".join(excluded)) if excluded else "No duplicates detected")

    # Books control: independently recompute bookkeeping total and net income
    # from line items on the source P&L, not the engine's Schedule C calculations.
    books = by_doc.get("D14", {})
    income_names = ("Sales - client projects", "Sales - print and licensing")
    inc = [numeric(books.get(k, {}).get("value")) for k in income_names]
    source_income = sum(inc, Decimal(0)) if all(x is not None for x in inc) else None
    reported_income = numeric(books.get("total_income", {}).get("value"))
    d = reported_income - source_income if reported_income is not None and source_income is not None else None
    checks.append({"id":"BOOKS-INCOME","title":"Business books — income foots to sales accounts","status":"PASS" if d == 0 else ("FAIL" if d is not None else "REVIEW"),"source_total":float(source_income) if source_income is not None else None,"engine_total":float(reported_income) if reported_income is not None else None,"difference":float(d) if d is not None else None,"return_line":None,"description":"Independent sum of revenue accounts compared to the P&L's printed total, not a Schedule C reconciliation.","note":"A separate books-to-tax bridge is still required.","sources":[{"document_id":"D14","page":1,"field":k,"value":books.get(k,{}).get("value")} for k in income_names]})

    # Books-to-tax reconciliation: independently trace the source books into
    # Schedule C, recording variances rather than silently changing tax figures.
    expense_fields = (
        "Advertising", "Bank and merchant fees", "Car and truck - fuel",
        "Contract labor", "Depreciation", "Insurance - business liability",
        "Insurance - health (Erik)", "Internet", "Legal and professional",
        "Meals", "Office expenses", "Software and subscriptions",
        "Supplies", "Telephone", "Travel",
    )
    book_expenses = [numeric(books.get(k, {}).get("value")) for k in expense_fields]
    book_expense_sum = sum(book_expenses, Decimal(0)) if all(v is not None for v in book_expenses) else None
    make_check(
        "BOOKS-EXPENSES", "Business books — expense accounts foot to P&L",
        [{"document_id": "D14", "page": 1, "field": k,
          "value": books.get(k, {}).get("value")} for k in expense_fields],
        book_expense_sum, description="Sum of all 15 recorded expense accounts vs the P&L printed expense total.",
        note="Compared amount is the independently extracted P&L total, not the tax deduction.",
    )
    # For a bookkeeping-only check, its comparator is the P&L printed total.
    c = checks[-1]
    printed_expenses = numeric(books.get("total_expenses", {}).get("value"))
    c["engine_total"] = float(printed_expenses) if printed_expenses is not None else None
    difference = printed_expenses - book_expense_sum if printed_expenses is not None and book_expense_sum is not None else None
    c["difference"] = float(difference) if difference is not None else None
    c["status"] = "PASS" if difference == 0 else "FAIL" if difference is not None else "REVIEW"

    make_check(
        "SCHC-REVENUE", "Book revenue → Schedule C gross receipts",
        [{"document_id":"D14","page":1,"field":k,"value":books.get(k, {}).get("value")} for k in income_names] +
        [{"document_id":"D15","page":3,"field":"atlas_paywell","value":by_doc.get("D15", {}).get("atlas_paywell", {}).get("value")}],
        source_income, "SchC.1",
        description="Book sales already include Paywell payments. Compare tax gross receipts without adding 1099-K a second time.",
        note="A nonzero variance is a potential duplicated 1099-K; requires professional review.",
    )

    # Recompute mileage from individually extracted trips, excluding pages whose
    # trip rows are identical to an earlier scanned page.
    mileage_rows = [x for x in packet["extracted_values"] if x["document_id"] == "D23"]
    pages = defaultdict(list)
    for x in mileage_rows:
        if x["field"].startswith("trip"):
            pages[x["page"]].append((x["field"], str(x["value"])))
    signatures = set()
    unique_pages, repeat_pages = [], []
    for page, fields in sorted(pages.items()):
        fingerprint = tuple(sorted(fields))
        if fingerprint in signatures:
            repeat_pages.append(page)
        else:
            signatures.add(fingerprint)
            unique_pages.append(page)
    miles = [numeric(x["value"]) for x in mileage_rows
             if x["page"] in unique_pages and x["field"].endswith("_miles")]
    unique_miles = sum(miles, Decimal(0)) if miles and all(v is not None for v in miles) else None
    make_check(
        "SCHC-MILEAGE", "Unique trip-log miles → Schedule C business miles",
        [{"document_id":"D23","page":page,"field":"unique trip miles","value":
          sum((numeric(x["value"]) for x in mileage_rows if x["page"] == page and x["field"].endswith("_miles")), Decimal(0))}
         for page in unique_pages],
        unique_miles, "SchC.44a",
        description="Add extracted trip miles once per distinct scanned sheet; do not count an identical scan twice.",
        note=f"Repeated pages excluded: {', '.join('p.'+str(x) for x in repeat_pages) or 'none'}. Difference is miles, not dollars.",
    )

    checks[-1]["unit"] = "miles"

    # Check tax return arithmetic independently, even where the underlying
    # expense classification remains disputed.
    tax_revenue = numeric(line_map.get("SchC.1",{}).get("value"))
    tax_expenses = numeric(line_map.get("SchC.28",{}).get("value"))
    tax_office = numeric(line_map.get("SchC.30",{}).get("value"))
    tax_profit = tax_revenue - tax_expenses - tax_office if None not in (tax_revenue, tax_expenses, tax_office) else None
    make_check(
        "SCHC-MATH", "Schedule C arithmetic → net business profit",
        [{"document_id":"D14","page":1,"field":"net_income","value":books.get("net_income",{}).get("value")}],
        tax_profit, "SchC.31",
        description="Independent arithmetic cross-foot of Schedule C gross receipts minus total tax expenses minus home-office deduction.",
        note="PASS validates arithmetic only; it does not mean source revenue or expense classification is correct.",
    )

    # California's explicit additions are reported, not presumed incorrect.
    federal_profit = numeric(line_map.get("SchCA540NR.12.A",{}).get("value"))
    ca_additions = numeric(line_map.get("SchCA540NR.12.C",{}).get("value"))
    ca_total = numeric(line_map.get("SchCA540NR.12.D",{}).get("value"))
    make_check(
        "CA-SCHC-BRIDGE", "California Schedule C — federal-to-state bridge",
        [{"document_id":"D14","page":1,"field":"net_income","value":books.get("net_income",{}).get("value")}],
        federal_profit + ca_additions if federal_profit is not None and ca_additions is not None else None,
        "SchCA540NR.12.D",
        description="Verify federal Schedule C profit plus the engine's California additions equals California-law Schedule C income.",
        note="Requires separate support for the $30,400 state additions and sourced California amount; arithmetic alone cannot validate them.",
    )
    checks[-1]["status"] = "REVIEW" if checks[-1]["status"] == "PASS" else checks[-1]["status"]

    return {"version":version,"checks":checks,"summary":{name:sum(c["status"]==name for c in checks) for name in ("PASS","FAIL","REVIEW")}}

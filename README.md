# MiraFlores Evidence Workpaper

**An evidence-first, web-based tax review prototype built for the MiraFlores AI — AI Engineer (Tax) case study.**

[**Live Demo**](https://miraflores-tax-workpaper-y0um.onrender.com/app/index.html) · [**Design & Data Model**](ONE_PAGE_DESIGN.pdf) · [**Errors Found**](ERRORS_FOUND.md)

> **Demo notice:** This application uses the fictional Okafor–Lindqvist 2025 tax case. It is an assessment prototype, not tax advice, a production client portal, or a real electronic filing system. The hosted demo has simulated user roles and no real authentication; do not enter personal or confidential taxpayer information.

## Overview

Traditional tax workpapers can make it difficult to trace a return amount back to its supporting evidence, independently challenge a computation, and understand who changed what. This prototype organizes the case around **source evidence → extracted values → return lines → independent checks → reviewer decisions → audit history**.

The supplied dataset includes:

| Case data | Count |
|---|---:|
| Source documents | 74 |
| Extracted values | 3,012 |
| Source-linked return lines | 627 |
| Flagged exceptions | 12 |
| Computed return versions | 3 |

## Features

| Area | What it demonstrates |
|---|---|
| **Review overview** | Case metrics, outstanding exceptions, and review status |
| **Evidence library** | Indexed documents, extracted fields, simulated document pages, and source references |
| **Lineage explorer** | Trace return lines to calculation inputs and document-level evidence |
| **Independent checks** | Source-based wage, withholding, business, mileage, and books-to-tax reconciliations, with PASS/FAIL/REVIEW distinctions |
| **Return versions** | Compare the packet's v1, v2, and v3 calculations |
| **Scenario lab** | Explore supplied what-if estimates without overwriting the underlying return |
| **Exceptions & decisions** | Review queues, notes, assignments, and recorded decisions |
| **Corrections & undo** | Proposed line corrections with original values, supporting evidence, and reversal history |
| **Bulk actions & undo** | Persisted batch assignments and reversible operations with safeguards for intervening changes |
| **Tax-area workpapers** | Depreciation roll-forwards, basis/carryovers, federal–California differences, and investment review flags |
| **People & filing** | Simulated review roles and sign-off workflow |
| **Filing lifecycle** | Readiness gates, case-supplied filing history, frozen review baselines, and amendment drafts |
| **Completion dashboard** | Checklist status, owners, deadlines, notes, and time budgets |
| **Audit trail** | Review actions and changes recorded for traceability |

## Examples of issues surfaced

- **Schedule C revenue:** $151,300 in business books compared with $163,700 reported on the return — a **$12,400 difference** requiring review.
- **Business mileage:** 8,100 unique miles compared with 11,800 reported — a **3,700-mile duplicate-page discrepancy**.
- **Brokerage reporting:** Corrected 1099-B page includes an omitted transaction (lot M18) with **$250 proceeds and $310 basis**.
- **W-2 reconciliation:** $104,600 + $107,800 = **$212,400 wages**; a duplicate W-2 image is excluded from the independent check.
- **California adjustments:** $81,854 federal Schedule C profit + $30,400 CA adjustment = $112,254 arithmetically, but the adjustment's substantive support remains under review.
- **Dependent identity:** Conflicting identification information is linked to an exception and a blocked filing-readiness state.

See [`ERRORS_FOUND.md`](ERRORS_FOUND.md) for additional findings and their supporting document references. Flags are **review candidates**, not automatic final tax determinations.

## Architecture

```text
Browser: HTML + CSS + vanilla JavaScript
          |
          v
Python FastAPI: case APIs, independent reconciliations,
                review and workflow endpoints
          |
          +--> Fictional case packet (JSON): source and computed tax data
          |
          +--> SQLAlchemy: persisted workflow records
                    |                     |
                    +-- Local: SQLite     +-- Hosted: Neon PostgreSQL
```

- **Frontend:** Vanilla HTML, CSS, and JavaScript
- **Backend:** Python, FastAPI, SQLAlchemy
- **Data:** Structured case JSON; SQLite for local development; PostgreSQL for the hosted demo
- **Hosting:** Render (application) and Neon (PostgreSQL)
- **Version control:** Git/GitHub

The hosted PostgreSQL database and local SQLite file are **separate**; local test records are not automatically migrated to the hosted demo.

## Run locally

Requires **Python 3**. From the repository root:

```bash
python -m venv .venv
```

Activate the environment:

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

```bash
# macOS / Linux
source .venv/bin/activate
```

Install and start:

```bash
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

Open **http://127.0.0.1:8000/app/index.html**.

Without a `DATABASE_URL` environment variable, the backend uses its configured local SQLite database. The hosted deployment supplies a Neon PostgreSQL connection through the **`DATABASE_URL` environment variable**. Never commit that credential or your local `.db` files to Git.

### Deploy on Render

Connect this repository to a Render Python web service with:

| Setting | Value |
|---|---|
| Branch | `master` |
| Root directory | Repository root (blank) |
| Build command | `pip install -r requirements.txt` |
| Start command | `uvicorn backend.main:app --host 0.0.0.0 --port $PORT` |
| Environment variable | `DATABASE_URL` = private Neon PostgreSQL connection string |

Render's free filesystem is ephemeral, so persistent workflow records must be stored outside the service, such as in Neon. Free services may sleep and take additional time to start.

## Design principles

1. **Evidence before confidence:** Extraction confidence alone does not prove a source value is correct or unique.
2. **Independent checks:** Verify selected amounts separately from the supplied return calculations.
3. **Visible uncertainty:** Clearly mark unverified basis, unsupported adjustments, and incomplete investment work.
4. **Reversible review actions:** Preserve original values and changes rather than silently mutating them.
5. **Filing gates:** Critical exceptions and missing sign-offs prevent a simulated ready-to-file state.

## Scope and limitations

This is a **functional assessment prototype**, with deliberate boundaries:

- Roles are selectable personas; **real authentication and server-side role authorization are not implemented**.
- The case packet includes historical filing events; the application **does not transmit returns to the IRS or California FTB**.
- Corrections, scenarios, and amendment drafts **do not recalculate the entire federal or state return** or create a filed Form 1040-X.
- Independent verification covers **selected** calculations; depreciation roll-forward PASS results verify arithmetic, not every tax-law choice, and investment-lot/basis reconstruction is not exhaustive.
- It is **not suitable for real taxpayer data**, multi-tenant use, or production financial workflows without additional security, permissions, validation, and operational controls.

## Assessment artifacts

- [`ONE_PAGE_DESIGN.pdf`](ONE_PAGE_DESIGN.pdf) — one-page product concept and data-model overview.
- [`DESIGN_AND_DATA_MODEL.md`](DESIGN_AND_DATA_MODEL.md) — expanded technical design.
- [`ERRORS_FOUND.md`](ERRORS_FOUND.md) — discrepancies identified and how the workpaper surfaces them.
- [`FINAL_TECHNICAL_REVIEW.md`](FINAL_TECHNICAL_REVIEW.md) — implementation verification and known limitations.

If these artifacts are supplied separately, place them in the repository root or update the links above accordingly.

## AI assistance disclosure

AI tools were used to assist with architecture planning, code generation and refinement, debugging, test planning, and documentation. The implementation was reviewed through source-based reconciliation checks and interactive workflow tests. AI output is **not** treated as tax evidence or proof of tax-law correctness; flagged issues still require qualified reviewer judgment.

---

**Built as a case-study submission for the AI Engineer (Tax) role at MiraFlores AI.**

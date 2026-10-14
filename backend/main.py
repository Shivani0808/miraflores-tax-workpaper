from typing import Literal
from sqlalchemy import update

from .models import SignoffRecord
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from fastapi import Depends

from .database import SessionLocal
from .models import ReviewDecision, AuditEvent, ExceptionRecord
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import json

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Miraflores Tax Workpaper API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    ],
    allow_methods=["GET"],
    allow_headers=["*"],
)

DATA_FILE = Path(__file__).parent / "okafor_lindqvist_2025_packet.json"


@app.get("/")
def home():
    return {"message": "Miraflores backend is running!"}


@app.get("/health")
def health():
    return {"status": "healthy"}


from .reconciliations import reconcile_packet


@app.get("/api/reconciliations")
def list_reconciliations(version: Literal["v1", "v2", "v3"] = "v3"):
    with DATA_FILE.open("r", encoding="utf-8") as file:
        packet = json.load(file)
    return reconcile_packet(packet, version)


@app.get("/api/summary")
def get_summary():
    with DATA_FILE.open("r", encoding="utf-8") as file:
        data = json.load(file)

    return {
        "client": data["packet"]["name"],
        "tax_year": data["household"]["tax_year"],
        "documents": len(data["documents"]),
        "extracted_values": len(data["extracted_values"]),
        "return_versions": len(data["return_versions"]),
    }

@app.get("/api/documents")
def get_documents():
    with DATA_FILE.open("r", encoding="utf-8") as file:
        data = json.load(file)

    return [
        {
            "id": document["id"],
            "title": document["title"],
            "type": document["document_type"],
            "pages": document["page_count"],
            "status": document["extraction"]["status"],
        }
        for document in data["documents"]
    ]

from fastapi import HTTPException


@app.get("/api/documents/{document_id}")
def get_document(document_id: str):
    with DATA_FILE.open("r", encoding="utf-8") as file:
        data = json.load(file)

    document = next(
        (
            doc for doc in data["documents"]
            if doc["id"].upper() == document_id.upper()
        ),
        None,
    )

    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    extracted_values = [
        value for value in data["extracted_values"]
        if value["document_id"] == document["id"]
    ]

    return {
        "document": document,
        "extracted_values": extracted_values,
    }

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class ReviewDecisionInput(BaseModel):
    reference_id: str = Field(min_length=1, max_length=100)
    decision_type: str = Field(min_length=1, max_length=50)
    status: str = Field(default="open", max_length=30)
    note: str = Field(min_length=1)
    role: str = Field(min_length=1, max_length=50)


@app.post("/api/review-decisions", status_code=201)
def save_review_decision(
    decision: ReviewDecisionInput,
    db: Session = Depends(get_db),
):
    record = ReviewDecision(
        reference_id=decision.reference_id,
        decision_type=decision.decision_type,
        status=decision.status,
        note=decision.note,
        role=decision.role,
    )

    audit = AuditEvent(
        reference_id=decision.reference_id,
        action="Review decision created",
        role=decision.role,
        details=decision.note,
    )

    db.add(record)
    db.add(audit)
    db.commit()
    db.refresh(record)

    return {
        "id": record.id,
        "reference_id": record.reference_id,
        "status": record.status,
        "message": "Review decision saved successfully",
    }


@app.get("/api/review-decisions")
def list_review_decisions(db: Session = Depends(get_db)):
    records = (
        db.query(ReviewDecision)
        .order_by(ReviewDecision.id.desc())
        .all()
    )

    return [
        {
            "id": record.id,
            "reference_id": record.reference_id,
            "decision_type": record.decision_type,
            "status": record.status,
            "note": record.note,
            "role": record.role,
            "created_at": record.created_at,
        }
        for record in records
    ]

from typing import Literal

class ExceptionDecisionInput(BaseModel):
    status: Literal["in_review", "resolved"]
    note: str = Field(min_length=1)
    assigned_role: str = Field(min_length=1, max_length=50)
    role: str = Field(min_length=1, max_length=50)


@app.put("/api/exceptions/{exception_id}")
def save_exception(
    exception_id: str,
    decision: ExceptionDecisionInput,
    db: Session = Depends(get_db),
):
    # Local prototype check only.
    # Production authorization must use authenticated users.
    if decision.status == "resolved" and decision.role not in (
        "reviewer", "partner", "admin"
    ):
        raise HTTPException(
            status_code=403,
            detail="Reviewer, partner or admin permission required",
        )

    record = (
        db.query(ExceptionRecord)
        .filter(ExceptionRecord.exception_id == exception_id)
        .first()
    )

    if record is None:
        record = ExceptionRecord(exception_id=exception_id)
        db.add(record)

    record.status = decision.status
    record.assigned_role = decision.assigned_role
    record.resolution_note = decision.note

    db.add(
        AuditEvent(
            reference_id=exception_id,
            action="Exception judgment saved",
            role=decision.role,
            details=decision.note,
        )
    )

    db.commit()

    return {
        "exception_id": exception_id,
        "status": record.status,
        "assigned_role": record.assigned_role,
        "message": "Exception judgment saved successfully",
    }


@app.get("/api/exceptions")
def list_saved_exceptions(db: Session = Depends(get_db)):
    records = db.query(ExceptionRecord).all()

    return [
        {
            "exception_id": record.exception_id,
            "status": record.status,
            "assigned_role": record.assigned_role,
            "note": record.resolution_note,
        }
        for record in records
    ]

@app.get("/api/audit-events")
def list_audit_events(db: Session = Depends(get_db)):
    records = (
        db.query(AuditEvent)
        .order_by(AuditEvent.id.desc())
        .all()
    )

    return [
        {
            "id": record.id,
            "reference_id": record.reference_id,
            "action": record.action,
            "role": record.role,
            "details": record.details,
            "created_at": record.created_at.isoformat()
            if record.created_at
            else None,
        }
        for record in records
    ]

class SignoffInput(BaseModel):
    role: Literal["preparer", "reviewer", "partner"]
    return_version: str = Field(min_length=1, max_length=20)


@app.post("/api/signoffs", status_code=201)
def create_signoff(
    request: SignoffInput,
    db: Session = Depends(get_db),
):
    if _current_corrections(db, request.return_version):
        raise HTTPException(status_code=409, detail="Active proposed corrections require review/undo before sign-off")

    # Complete list of critical exceptions in this prototype.
    critical_ids = {"ISS-01", "ISS-04"}

    saved_exceptions = {
        item.exception_id: item.status
        for item in db.query(ExceptionRecord).all()
    }

    unresolved = [
        exception_id
        for exception_id in critical_ids
        if saved_exceptions.get(exception_id, "open") != "resolved"
    ]

    if unresolved:
        raise HTTPException(
            status_code=409,
            detail=(
                "Critical review exceptions block sign-off: "
                + ", ".join(sorted(unresolved))
            ),
        )

    required_previous = {
        "preparer": None,
        "reviewer": "preparer",
        "partner": "reviewer",
    }

    previous_role = required_previous[request.role]

    if previous_role:
        previous = (
            db.query(SignoffRecord)
            .filter(
                SignoffRecord.role == previous_role,
                SignoffRecord.return_version == request.return_version,
                SignoffRecord.is_valid == 1,
            )
            .first()
        )

        if previous is None:
            raise HTTPException(
                status_code=409,
                detail=f"{previous_role.title()} sign-off required first",
            )

    existing = (
        db.query(SignoffRecord)
        .filter(
            SignoffRecord.role == request.role,
            SignoffRecord.return_version == request.return_version,
            SignoffRecord.is_valid == 1,
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail="This role has already signed this return version",
        )

    record = SignoffRecord(
        role=request.role,
        return_version=request.return_version,
        is_valid=1,
    )

    db.add(record)
    db.flush()

    db.add(
        AuditEvent(
            reference_id=request.return_version,
            action=f"{request.role.title()} sign-off recorded",
            role=request.role,
            details=f"Sign-off ID: {record.id}",
        )
    )

    db.commit()
    db.refresh(record)

    return {
        "id": record.id,
        "role": record.role,
        "return_version": record.return_version,
        "message": "Sign-off recorded successfully",
    }


@app.get("/api/signoffs")
def list_signoffs(db: Session = Depends(get_db)):
    records = (
        db.query(SignoffRecord)
        .filter(SignoffRecord.is_valid == 1)
        .order_by(SignoffRecord.id.asc())
        .all()
    )

    return [
        {
            "id": record.id,
            "role": record.role,
            "return_version": record.return_version,
            "signed_at": record.signed_at.isoformat()
            if record.signed_at
            else None,
        }
        for record in records
    ]



# Correction tracking: engine results remain read-only; proposals are separate records.
from .database import engine, Base
from .models import CorrectionEvent, SignoffRecord
from sqlalchemy import update
import math

Base.metadata.create_all(bind=engine)

CORRECTION_CATEGORIES = {"wages", "interest", "schc_profit", "stcg", "ltcg", "ordinary_income", "adjustment", "salt", "itemized", "ca_source_income"}
STAFF_ROLES = {"preparer", "reviewer", "partner", "admin"}

class CorrectionInput(BaseModel):
    return_version: Literal["v1", "v2", "v3"]
    line_key: str = Field(min_length=1, max_length=100)
    revised_value: float
    category: str = Field(min_length=1, max_length=50)
    note: str = Field(min_length=5, max_length=2000)
    role: str = Field(min_length=1, max_length=50)

class UndoInput(BaseModel):
    note: str = Field(min_length=5, max_length=2000)
    role: str = Field(min_length=1, max_length=50)

def _packet_version(v):
    with DATA_FILE.open("r", encoding="utf-8") as f:
        p = json.load(f)
    return next(x for x in p["return_versions"] if x["version"] == v)

def _current_corrections(db, version):
    # Chronologically replay proposals/undos; every event is retained.
    events = (db.query(CorrectionEvent).filter(CorrectionEvent.return_version == version)
              .order_by(CorrectionEvent.id.asc()).all())
    active = {}
    for e in events:
        if e.action == "propose": active[e.line_key] = e
        elif e.action == "undo": active.pop(e.line_key, None)
    return active

def _event_dict(e, v):
    return {"id":e.id,"version":e.return_version,"line_key":e.line_key,"action":e.action,
            "previous_value":float(e.previous_value),"revised_value":float(e.revised_value),
            "category":e.category,"note":e.note,"role":e.role,
            "reverted_event_id":e.reverted_event_id,
            "created_at":e.created_at.isoformat() if e.created_at else None}

@app.get("/api/corrections")
def list_corrections(version: Literal["v1", "v2", "v3"] = "v3", db: Session = Depends(get_db)):
    events = (db.query(CorrectionEvent).filter(CorrectionEvent.return_version == version)
              .order_by(CorrectionEvent.id.desc()).all())
    active = _current_corrections(db, version)
    return {"version":version,"active": [_event_dict(e,version) for e in active.values()],
            "history": [_event_dict(e,version) for e in events]}

@app.post("/api/corrections", status_code=201)
def propose_correction(request: CorrectionInput, db: Session = Depends(get_db)):
    if request.role not in STAFF_ROLES:
        raise HTTPException(403,"Staff role required (demo-only, not authenticated)")
    if request.category not in CORRECTION_CATEGORIES:
        raise HTTPException(422,"Choose a supported tax impact category")
    if not math.isfinite(request.revised_value):
        raise HTTPException(422,"Correction amount must be finite")
    ver = _packet_version(request.return_version)
    line = next((x for x in ver["lines"] if x["key"] == request.line_key),None)
    if line is None or isinstance(line["value"], bool) or not isinstance(line["value"], (float,int)):
        raise HTTPException(404,"Numeric return line not found")
    active = _current_corrections(db, request.return_version)
    if request.line_key in active:
        raise HTTPException(409,"Undo the current proposal before proposing another for this line")
    original = float(line["value"])
    if abs(original-request.revised_value) < 0.000001:
        raise HTTPException(422,"Proposed amount must differ from engine amount")
    event = CorrectionEvent(return_version=request.return_version,line_key=request.line_key,
        action="propose",previous_value=str(original),revised_value=str(request.revised_value),
        category=request.category,note=request.note.strip(),role=request.role)
    db.add(event)
    db.flush()
    db.add(AuditEvent(reference_id=request.line_key, action="Correction proposed",role=request.role,
        details=f"{request.return_version}: {original} -> {request.revised_value}; {request.note}"))
    db.execute(update(SignoffRecord).where(SignoffRecord.return_version==request.return_version).values(is_valid=0))
    db.commit(); db.refresh(event)
    rates = ver.get("tax_effect_rates", {}).get(request.category, {})
    delta = request.revised_value-original
    return {"event":_event_dict(event,request.return_version),"delta":delta,
        "estimated_federal_tax_change": round(delta*float(rates.get("federal_per_dollar",0)),2),
        "estimated_california_tax_change":round(delta*float(rates.get("california_per_dollar",0)),2),
        "estimate_note":"Directional estimate from supplied marginal effects only; not engine recomputation. Credits, deductions, interactions and thresholds may change the result."}

@app.post("/api/corrections/{event_id}/undo", status_code=201)
def undo_correction(event_id: int, request: UndoInput, db: Session = Depends(get_db)):
    if request.role not in STAFF_ROLES:
        raise HTTPException(403,"Staff role required (demo-only, not authenticated)")
    original = db.query(CorrectionEvent).filter(CorrectionEvent.id==event_id, CorrectionEvent.action=="propose").first()
    if not original:
        raise HTTPException(404,"Proposed correction not found")
    active = _current_corrections(db, original.return_version)
    if active.get(original.line_key) is None or active[original.line_key].id != event_id:
        raise HTTPException(409,"This proposal is not currently active")
    undo = CorrectionEvent(return_version=original.return_version,line_key=original.line_key,
        action="undo",previous_value=original.revised_value,revised_value=original.previous_value,
        category=original.category,note=request.note.strip(),role=request.role,reverted_event_id=event_id)
    db.add(undo)
    db.add(AuditEvent(reference_id=original.line_key,action="Correction undone",role=request.role,
        details=f"{original.return_version}: restored {original.previous_value}; {request.note}"))
    db.execute(update(SignoffRecord).where(SignoffRecord.return_version==original.return_version).values(is_valid=0))
    db.commit(); db.refresh(undo)
    return {"event":_event_dict(undo,undo.return_version),"restored_value":float(original.previous_value)}



# Review and filing lifecycle: recorded demo work only; never submits to tax authorities.
from .models import WorkflowEvent
from .database import Base, engine
Base.metadata.create_all(bind=engine)

WORKFLOW_ACTIONS = {
    "assign_review", "request_client_evidence", "review_filing_packet",
    "resolve_rejection", "review_amendment", "review_notice", "rollforward_2026",
    "simulate_filing_ready"
}

class WorkflowInput(BaseModel):
    return_version: Literal["v1", "v2", "v3"]
    action: str = Field(min_length=1, max_length=50)
    reference_id: str = Field(min_length=1, max_length=100)
    note: str = Field(min_length=8, max_length=3000)
    role: str = Field(min_length=1, max_length=50)

def _workflow_readiness(db, ver):
    critical = {"ISS-01", "ISS-04"}
    resolved = {e.exception_id for e in db.query(ExceptionRecord).all() if e.status=="resolved"}
    open_critical = sorted(critical-resolved)
    signed = {s.role for s in db.query(SignoffRecord).filter(
        SignoffRecord.return_version==ver, SignoffRecord.is_valid==1).all()}
    missing_signoffs = sorted({"preparer", "reviewer", "partner"}-signed)
    proposals = _current_corrections(db,ver)
    blockers = []
    if open_critical: blockers.append("Unresolved critical exceptions: " + ", ".join(open_critical))
    if missing_signoffs: blockers.append("Missing valid signoffs: " + ", ".join(missing_signoffs))
    if proposals: blockers.append("Open proposed corrections: " + ", ".join(sorted(proposals)))
    return {"ready":not blockers,"blockers":blockers,"missing_signoffs":missing_signoffs,
            "unresolved_critical":open_critical,"active_corrections":list(proposals)}

@app.get("/api/filing-workflow")
def filing_workflow(version: Literal["v1", "v2", "v3"]="v3",db:Session=Depends(get_db)):
    with DATA_FILE.open("r", encoding="utf-8") as f: packet=json.load(f)
    agency=packet.get("tax_agency_records",{})
    relevant={"client_approved_and_signed_8879","efile_rejected","efile_accepted_federal",
              "efile_accepted_california","federal_balance_paid","california_refund_issued",
              "quality_review_selected_return","next_year_engagement_started","notice_received"}
    timeline=[{"date":x.get("at"),"event":x.get("event"),"detail":str(x.get("detail") or ""),
               "refs":x.get("refs",[])} for x in packet.get("timeline",[]) if x.get("event") in relevant]
    events=db.query(WorkflowEvent).filter(WorkflowEvent.return_version==version).order_by(WorkflowEvent.id.desc()).all()
    return {"version":version,"readiness":_workflow_readiness(db,version),"scripted_timeline":timeline,
            "efile":agency.get("efile",[]),"notices":agency.get("notices",[]),
            "carryovers_out":_packet_version(version).get("carryovers_out",{}),
            "history":[{"id":x.id,"action":x.action,"reference_id":x.reference_id,
                 "note":x.note,"role":x.role,"created_at":x.created_at.isoformat() if x.created_at else None}
                 for x in events]}

@app.post("/api/filing-workflow",status_code=201)
def create_filing_workflow(request: WorkflowInput,db:Session=Depends(get_db)):
    if request.action not in WORKFLOW_ACTIONS: raise HTTPException(422,"Unsupported action")
    if request.role not in STAFF_ROLES: raise HTTPException(403,"Staff role required (demo role, not authentication)")
    if request.action=="simulate_filing_ready":
        gates=_workflow_readiness(db,request.return_version)
        if not gates["ready"]: raise HTTPException(409,"Filing blocked: "+"; ".join(gates["blockers"]))
        if request.role not in {"partner","admin"}: raise HTTPException(403,"Partner signoff required for this simulation")
    if request.action in {"review_notice","review_amendment","resolve_rejection"} and request.role not in {"reviewer","partner","admin"}:
        raise HTTPException(403,"Reviewer, partner or admin demo role required")
    row=WorkflowEvent(return_version=request.return_version,action=request.action,
        reference_id=request.reference_id,note=request.note.strip(),role=request.role)
    db.add(row)
    db.add(AuditEvent(reference_id=request.reference_id,action="Workflow: "+request.action,
        details=request.note.strip(),role=request.role))
    db.commit();db.refresh(row)
    return {"id":row.id,"message":"Simulation review action recorded; no actual e-file or agency submission"}

app.mount(
    "/app",
    StaticFiles(
        directory=Path(__file__).resolve().parent.parent,
        html=True
    ),
    name="frontend"
)

# Persistent batch assignment and conditional reversal. Only this prototype's
# demo role selector is available; this is NOT server-authenticated RBAC.
from .models import BulkAssignmentEvent
from .database import engine as _bulk_engine, Base as _bulk_base
from .models import utc_now as _bulk_now
_bulk_base.metadata.create_all(bind=_bulk_engine)

class BulkAssignRequest(BaseModel):
    exception_ids: list[str] = Field(min_length=1, max_length=74)
    target_role: Literal["preparer", "reviewer", "partner"] = "reviewer"
    role: Literal["preparer", "reviewer", "partner", "admin"]
    note: str = Field(min_length=5, max_length=500)

class BulkUndoRequest(BaseModel):
    role: Literal["preparer", "reviewer", "partner", "admin"]
    note: str = Field(min_length=5, max_length=500)

def _bulk_snapshot(record):
    return {"status": record.status, "owner": record.assigned_role, "note": record.resolution_note}

@app.post("/api/bulk-assignments", status_code=201)
def create_bulk_assignment(payload: BulkAssignRequest, db: Session = Depends(get_db)):
    ids = [x.strip().upper() for x in payload.exception_ids]
    if len(set(ids)) != len(ids):
        raise HTTPException(422, "Duplicate exception ID in batch")
    # Known exceptions are defined by the assessment, not arbitrary IDs.
    allowed = {f"ISS-{i:02}" for i in range(1, 13)}
    if not set(ids).issubset(allowed):
        raise HTTPException(422, "Unknown exception ID")
    changes = []
    for exception_id in ids:
        record = db.query(ExceptionRecord).filter_by(exception_id=exception_id).first()
        if record and record.status == "resolved":
            raise HTTPException(409, f"{exception_id} already resolved; no batch modification performed")
        if record and record.status != "open":
            raise HTTPException(409, f"{exception_id} is not open; refresh and retry")
        before = _bulk_snapshot(record) if record else {"status":"open","owner":"preparer","note":None}
        after = {"status":"in_review","owner":payload.target_role,"note":payload.note}
        changes.append({"id":exception_id,"before":before,"after":after})
    for change in changes:
        record = db.query(ExceptionRecord).filter_by(exception_id=change["id"]).first()
        if record is None:
            record = ExceptionRecord(exception_id=change["id"]); db.add(record)
        record.status = change["after"]["status"]
        record.assigned_role = change["after"]["owner"]
        record.resolution_note = change["after"]["note"]
    batch = BulkAssignmentEvent(action="assign",role=payload.role, changes_json=json.dumps(changes))
    db.add(batch); db.flush()
    db.add(AuditEvent(reference_id=f"BATCH-{batch.id}",action="Bulk exceptions assigned",role=payload.role, details=f"{len(changes)} exceptions -> {payload.target_role}: {payload.note}"))
    db.execute(update(SignoffRecord).where(SignoffRecord.is_valid == 1).values(is_valid=0))
    db.commit()
    return {"id":batch.id,"count":len(changes),"changes":changes}

@app.get("/api/bulk-assignments")
def list_bulk_assignments(db: Session = Depends(get_db)):
    events = db.query(BulkAssignmentEvent).order_by(BulkAssignmentEvent.id.desc()).limit(50).all()
    return [{"id":e.id,"action":e.action,"role":e.role,"changes":json.loads(e.changes_json),"undone":e.undone_at is not None,"undo_note":e.undo_note,"created_at":e.created_at.isoformat() if e.created_at else None} for e in events]

@app.post("/api/bulk-assignments/{batch_id}/undo")
def undo_bulk_assignment(batch_id: int, payload: BulkUndoRequest, db: Session = Depends(get_db)):
    batch = db.query(BulkAssignmentEvent).filter_by(id=batch_id).first()
    if not batch: raise HTTPException(404, "Batch not found")
    if batch.undone_at is not None: raise HTTPException(409, "Batch already undone")
    changes = json.loads(batch.changes_json)
    # Important: an individual review made since the batch must never be overwritten.
    for change in changes:
        record = db.query(ExceptionRecord).filter_by(exception_id=change["id"]).first()
        if record is None or _bulk_snapshot(record) != change["after"]:
            raise HTTPException(409, f"{change['id']} changed since this batch; undo refused to protect newer review work")
    for change in changes:
        record = db.query(ExceptionRecord).filter_by(exception_id=change["id"]).first()
        record.status = change["before"]["status"]
        record.assigned_role = change["before"]["owner"]
        record.resolution_note = change["before"]["note"]
    batch.undone_at = _bulk_now(); batch.undo_note = payload.note
    db.add(AuditEvent(reference_id=f"BATCH-{batch.id}", action="Bulk assignment undone",role=payload.role, details=payload.note))
    db.execute(update(SignoffRecord).where(SignoffRecord.is_valid == 1).values(is_valid=0))
    db.commit()
    return {"id":batch.id,"undone":True,"count":len(changes)}



# Immutable review baselines and append-only amendment drafts. Neither sends or files a return.
import hashlib
from .models import FrozenReturnSnapshot, AmendmentDraft
from .database import Base as _snapshot_base, engine as _snapshot_engine
_snapshot_base.metadata.create_all(bind=_snapshot_engine)

class FreezeBaselineRequest(BaseModel):
    version: Literal["v1", "v2", "v3"] = "v3"
    role: Literal["preparer", "reviewer", "partner", "admin"]
    note: str = Field(min_length=8, max_length=1500)

class AmendmentDraftRequest(BaseModel):
    snapshot_id: int
    line_key: str = Field(min_length=3, max_length=100)
    proposed_value: float
    role: Literal["preparer", "reviewer", "partner", "admin"]
    reason: str = Field(min_length=8, max_length=1500)

def _baseline_brief(e):
    return {"id":e.id,"version":e.return_version,"sha256":e.sha256,
            "role":e.role,"note":e.note,
            "created_at":e.created_at.isoformat() if e.created_at else None,
            "kind":"frozen_review_baseline_not_filed"}

@app.post('/api/return-snapshots',status_code=201)
def freeze_return_baseline(req:FreezeBaselineRequest,db:Session=Depends(get_db)):
    """Freeze exact engine version, proposals, and readiness as-of freeze; no filed representation."""
    ver=_packet_version(req.version)
    corrections=_current_corrections(db,req.version)
    readiness=_workflow_readiness(db,req.version)
    frozen={"kind":"review_baseline_not_filed","return_version":req.version,
            "packet_version":ver,
            "active_proposals":{k:{"previous":x.previous_value,"proposed":x.revised_value,
                    "event_id":x.id} for k,x in corrections.items()},
            "readiness_at_freeze":readiness}
    serialized=json.dumps(frozen,sort_keys=True,separators=(',',':'),ensure_ascii=False)
    fingerprint=hashlib.sha256(serialized.encode('utf-8')).hexdigest()
    row=FrozenReturnSnapshot(return_version=req.version,snapshot_json=serialized,sha256=fingerprint,
            role=req.role,note=req.note.strip())
    db.add(row);db.flush()
    db.add(AuditEvent(reference_id=f'SNAPSHOT-{row.id}',action='Frozen review baseline created',
            role=req.role,details=f'SHA256 {fingerprint}; NOT FILED. {req.note.strip()}'))
    db.commit();db.refresh(row)
    return _baseline_brief(row)

@app.get('/api/return-snapshots')
def list_return_snapshots(version:Literal['v1','v2','v3']='v3',db:Session=Depends(get_db)):
    entries=db.query(FrozenReturnSnapshot).filter_by(return_version=version).order_by(FrozenReturnSnapshot.id.desc()).all()
    return [_baseline_brief(x) for x in entries]

@app.get('/api/return-snapshots/{snapshot_id}')
def get_return_snapshot(snapshot_id:int,db:Session=Depends(get_db)):
    row=db.get(FrozenReturnSnapshot,snapshot_id)
    if row is None: raise HTTPException(404,'Snapshot not found')
    frozen=json.loads(row.snapshot_json)
    return {**_baseline_brief(row),"frozen":frozen}

@app.post('/api/amendment-drafts',status_code=201)
def create_amendment_draft(req:AmendmentDraftRequest,db:Session=Depends(get_db)):
    base=db.get(FrozenReturnSnapshot,req.snapshot_id)
    if base is None: raise HTTPException(404,'Frozen baseline not found')
    frozen=json.loads(base.snapshot_json)
    matches=[x for x in frozen['packet_version']['lines'] if x.get('key')==req.line_key.strip()]
    if len(matches)!=1: raise HTTPException(422,'Line key must exist uniquely in frozen baseline')
    original=matches[0].get('value')
    if not isinstance(original,(int,float)):raise HTTPException(422,'Line value must be numeric')
    if not __import__('math').isfinite(req.proposed_value):raise HTTPException(422,'Value must be finite')
    if float(original)==req.proposed_value:raise HTTPException(422,'Proposed value equals frozen baseline')
    row=AmendmentDraft(snapshot_id=base.id,line_key=req.line_key.strip(),
             original_value=str(original),proposed_value=str(req.proposed_value),
             reason=req.reason.strip(),role=req.role,status='draft')
    db.add(row);db.flush()
    db.add(AuditEvent(reference_id=f'AMEND-{row.id}',action='Draft amendment proposed',
             role=req.role,details=f'Baseline {base.id}; {row.line_key}: {original} -> {req.proposed_value}; {row.reason}'))
    db.commit();db.refresh(row)
    return {'id':row.id,'snapshot_id':row.snapshot_id,'line_key':row.line_key,
            'original_value':float(row.original_value),'proposed_value':float(row.proposed_value),
            'delta':float(row.proposed_value)-float(row.original_value),
            'status':'draft','note':'No amended return filed or computed'}

@app.get('/api/amendment-drafts')
def list_amendment_drafts(snapshot_id:int|None=None,db:Session=Depends(get_db)):
    q=db.query(AmendmentDraft)
    if snapshot_id is not None:q=q.filter_by(snapshot_id=snapshot_id)
    rows=q.order_by(AmendmentDraft.id.desc()).limit(100).all()
    return [{'id':r.id,'snapshot_id':r.snapshot_id,'line_key':r.line_key,
             'original_value':float(r.original_value),'proposed_value':float(r.proposed_value),
             'delta':float(r.proposed_value)-float(r.original_value),
             'reason':r.reason,'role':r.role,'status':r.status,
             'created_at':r.created_at.isoformat() if r.created_at else None} for r in rows]


# Reviewer checklist and time/budget controls. No automatic tax-law certification.
from .models import CompletenessTask
from .database import Base as _completeness_base, engine as _completeness_engine
_completeness_base.metadata.create_all(bind=_completeness_engine)

COMPLETENESS_ITEMS = [
 ("intake", "Client intake and identity evidence", "D71, household/dependent identity", 45),
 ("brokerage", "Corrected brokerage and missing page", "ISS-01, D30/D31 p.32, Form 8949", 100),
 ("mileage", "Vehicle/mileage duplicate scan", "ISS-02, D23", 50),
 ("business", "Books-to-tax receipts reconciliation", "D14, D15, D21, Schedule C", 90),
 ("state", "California adjustments and allocation", "D09, D22, D73, Sch CA", 85),
 ("basis", "S-corp and partnership basis", "Prior year K-1, outside basis", 90),
 ("investments", "Trading, crypto and cost-basis lots", "D11, D28, D35, D74", 100),
 ("depreciation", "Federal/California asset methods", "D22, 9 asset roll-forwards", 70),
 ("approval", "Reviewer, preparer, partner sign-offs", "Versioned approval checks", 30),
 ("filing", "8879, filing and post-filing handoff", "E-file history, notices, carryforwards", 45),
]

class CompletenessUpdate(BaseModel):
    version: Literal['v1','v2','v3'] = 'v3'
    status: Literal['open','in_progress','review','done']
    assigned_role: Literal['preparer','reviewer','partner','client','admin']
    due_date: str | None = None
    minutes_spent: int = Field(ge=0,le=100000)
    budget_minutes: int = Field(ge=1,le=100000)
    note: str = Field(min_length=8,max_length=4000)
    role: Literal['preparer','reviewer','partner','client','admin']

@app.get('/api/completeness')
def list_completeness(version:Literal['v1','v2','v3']='v3',db:Session=Depends(get_db)):
    saved={x.task_key:x for x in db.query(CompletenessTask).filter_by(return_version=version).all()}
    items=[]
    for key,title,evidence,budget in COMPLETENESS_ITEMS:
        row=saved.get(key)
        items.append(dict(key=key,title=title,evidence=evidence,
            status=row.status if row else 'open',assigned_role=row.assigned_role if row else 'preparer',
            due_date=row.due_date if row else None,
            minutes_spent=row.minutes_spent if row else 0,budget_minutes=row.budget_minutes if row else budget,
            note=row.note if row else '',updated_at=row.updated_at.isoformat() if row else None))
    return {'version':version,'items':items,'total':len(items),'done':sum(x['status']=='done' for x in items),
            'minutes_spent':sum(x['minutes_spent'] for x in items),
            'budget_minutes':sum(x['budget_minutes'] for x in items),
            'warning':'A checklist completion does not resolve exceptions, validate tax law, or override filing readiness.'}

@app.put('/api/completeness/{task_key}')
def update_completeness(task_key:str,req:CompletenessUpdate,db:Session=Depends(get_db)):
    if task_key not in {x[0] for x in COMPLETENESS_ITEMS}:
        raise HTTPException(404,'Unknown checklist item')
    if req.due_date:
        try: datetime.strptime(req.due_date,'%Y-%m-%d')
        except ValueError: raise HTTPException(422,'Due date must be YYYY-MM-DD')
    row=db.query(CompletenessTask).filter_by(return_version=req.version,task_key=task_key).first()
    if row is None:
        row=CompletenessTask(return_version=req.version,task_key=task_key)
        db.add(row)
    previous=row.status
    row.status=req.status;row.assigned_role=req.assigned_role
    row.due_date=req.due_date or None;row.minutes_spent=req.minutes_spent
    row.budget_minutes=req.budget_minutes;row.note=req.note.strip();row.updated_by=req.role
    row.updated_at=datetime.now(timezone.utc)
    db.add(AuditEvent(reference_id=f'CHECK-{task_key.upper()}',action='Completeness control updated',role=req.role,
                      details=f'{req.version}: {previous} -> {req.status}; owner {req.assigned_role}; due {req.due_date}; {req.note}'))
    db.commit()
    return {'saved':True,'task_key':task_key,'status':row.status,'version':req.version}

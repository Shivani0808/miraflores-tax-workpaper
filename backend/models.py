
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)

from .database import Base


def utc_now():
    return datetime.now(timezone.utc)


class ReviewDecision(Base):
    __tablename__ = "review_decisions"

    id = Column(Integer, primary_key=True, index=True)
    reference_id = Column(String(100), nullable=False, index=True)
    decision_type = Column(String(50), nullable=False)
    status = Column(String(30), nullable=False, default="open")
    note = Column(Text, nullable=False)
    role = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)


class ExceptionRecord(Base):
    __tablename__ = "exception_records"

    id = Column(Integer, primary_key=True, index=True)
    exception_id = Column(String(50), unique=True, nullable=False)
    status = Column(String(30), default="open", nullable=False)
    assigned_role = Column(String(50), default="preparer")
    resolution_note = Column(Text, nullable=True)
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, index=True)
    reference_id = Column(String(100), nullable=False, index=True)
    action = Column(String(100), nullable=False)
    role = Column(String(50), nullable=False)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

class SignoffRecord(Base):
    __tablename__ = "signoff_records"

    id = Column(Integer, primary_key=True, index=True)
    role = Column(String(50), nullable=False)
    return_version = Column(String(20), nullable=False)
    signed_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    is_valid = Column(Integer, default=1, nullable=False)



class CorrectionEvent(Base):
    """Append-only proposed-line-override and undo records; engine packet is immutable."""
    __tablename__ = "correction_events"

    id = Column(Integer, primary_key=True, index=True)
    return_version = Column(String(20), nullable=False, index=True)
    line_key = Column(String(100), nullable=False, index=True)
    action = Column(String(20), nullable=False)  # propose / undo
    previous_value = Column(String(60), nullable=False)
    revised_value = Column(String(60), nullable=False)
    category = Column(String(50), nullable=True)
    note = Column(Text, nullable=False)
    role = Column(String(50), nullable=False)
    reverted_event_id = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)


class WorkflowEvent(Base):
    """Append-only review/filing simulation notes. Not an electronic filing service."""
    __tablename__ = "workflow_events"
    id = Column(Integer, primary_key=True)
    return_version = Column(String(20), nullable=False, index=True)
    action = Column(String(50), nullable=False)
    reference_id = Column(String(100), nullable=False)
    note = Column(Text, nullable=False)
    role = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)


class BulkAssignmentEvent(Base):
    """Recorded batch with before/after snapshots for conditional undo."""
    __tablename__ = "bulk_assignment_events"
    id = Column(Integer, primary_key=True)
    action = Column(String(30), nullable=False)
    role = Column(String(50), nullable=False)
    changes_json = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    undone_at = Column(DateTime(timezone=True), nullable=True)
    undo_note = Column(Text, nullable=True)


class FrozenReturnSnapshot(Base):
    """Immutable review baseline. Never represents proof of an actual filed return."""
    __tablename__ = "frozen_return_snapshots"
    id = Column(Integer, primary_key=True)
    return_version = Column(String(20), nullable=False, index=True)
    snapshot_json = Column(Text, nullable=False)
    sha256 = Column(String(64), nullable=False)
    role = Column(String(50), nullable=False)
    note = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

class AmendmentDraft(Base):
    """Append-only proposed amendment revisions, tied to a frozen baseline."""
    __tablename__ = "amendment_drafts"
    id = Column(Integer, primary_key=True)
    snapshot_id = Column(Integer, ForeignKey('frozen_return_snapshots.id'), nullable=False, index=True)
    line_key = Column(String(100), nullable=False)
    proposed_value = Column(String(60), nullable=False)
    original_value = Column(String(60), nullable=False)
    reason = Column(Text, nullable=False)
    role = Column(String(50), nullable=False)
    status = Column(String(30), nullable=False, default="draft")
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)


class CompletenessTask(Base):
    """Version-specific reviewer checklist state; records do not prove tax correctness."""
    __tablename__ = "completeness_tasks"
    id = Column(Integer, primary_key=True)
    return_version = Column(String(20), nullable=False, index=True)
    task_key = Column(String(60), nullable=False)
    status = Column(String(30), nullable=False, default="open")
    assigned_role = Column(String(50), nullable=False, default="preparer")
    due_date = Column(String(10), nullable=True)
    minutes_spent = Column(Integer, nullable=False, default=0)
    budget_minutes = Column(Integer, nullable=False, default=60)
    note = Column(Text, nullable=False, default="")
    updated_by = Column(String(50), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

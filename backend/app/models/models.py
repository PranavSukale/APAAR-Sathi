from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import DATERANGE, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, new_uuid

PK = lambda: mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)  # noqa: E731
FK = lambda t: mapped_column(UUID(as_uuid=True), ForeignKey(t))  # noqa: E731
FKn = lambda t: mapped_column(UUID(as_uuid=True), ForeignKey(t), nullable=True)  # noqa: E731


# ---------------- Identity & access ----------------
class User(Base, TimestampMixin):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = PK()
    email: Mapped[str] = mapped_column(String(255), unique=True)
    full_name: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(32))  # OPERATOR/APPROVER/AICTE_REVIEWER/AICTE_SUPERVISOR/ADMIN/AUDITOR
    institution_ids: Mapped[list] = mapped_column(JSONB, default=list)  # list[str uuid]
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    disabled: Mapped[bool] = mapped_column(Boolean, default=False)


# ---------------- Master data ----------------
class Institution(Base, TimestampMixin):
    __tablename__ = "institutions"
    id: Mapped[uuid.UUID] = PK()
    official_institution_code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    normalized_name: Mapped[str] = mapped_column(String(255))
    aliases: Mapped[list] = mapped_column(JSONB, default=list)
    state: Mapped[str] = mapped_column(String(64), default="")
    district: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE")


class Program(Base, TimestampMixin):
    __tablename__ = "programs"
    id: Mapped[uuid.UUID] = PK()
    institution_id = FK("institutions.id")
    program_code: Mapped[str] = mapped_column(String(64))
    program_name: Mapped[str] = mapped_column(String(255))
    program_type: Mapped[str] = mapped_column(String(64), default="")
    aliases: Mapped[list] = mapped_column(JSONB, default=list)


class ProgramApproval(Base, TimestampMixin):
    __tablename__ = "program_approvals"
    id: Mapped[uuid.UUID] = PK()
    program_id = FK("programs.id")
    academic_year: Mapped[str] = mapped_column(String(16))
    approved_intake: Mapped[int] = mapped_column(Integer)
    category_intake_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    valid_during = mapped_column(DATERANGE)
    approval_reference: Mapped[str] = mapped_column(String(128), default="")
    config_version: Mapped[int] = mapped_column(Integer, default=1)
    created_by = FKn("users.id")
    approved_by = FKn("users.id")


class SeatCategory(Base, TimestampMixin):
    __tablename__ = "seat_categories"
    id: Mapped[uuid.UUID] = PK()
    code: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(128))
    counts_toward_intake: Mapped[bool] = mapped_column(Boolean, default=True)
    rule_note: Mapped[str] = mapped_column(Text, default="placeholder, pending validation")
    config_version: Mapped[int] = mapped_column(Integer, default=1)


class ReportingCycle(Base, TimestampMixin):
    __tablename__ = "reporting_cycles"
    id: Mapped[uuid.UUID] = PK()
    academic_year: Mapped[str] = mapped_column(String(16))
    opens_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closes_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="OPEN")
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ---------------- Import ----------------
class ImportBatch(Base, TimestampMixin):
    __tablename__ = "import_batches"
    id: Mapped[uuid.UUID] = PK()
    institution_id = FK("institutions.id")
    uploaded_by = FKn("users.id")
    file_name: Mapped[str] = mapped_column(String(255))
    file_hash: Mapped[str] = mapped_column(String(64), index=True)
    mapping_profile_id = FKn("mapping_profiles.id")
    status: Mapped[str] = mapped_column(String(32), default="UPLOADED")
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    accepted_rows: Mapped[int] = mapped_column(Integer, default=0)
    rejected_rows: Mapped[int] = mapped_column(Integer, default=0)
    quality_score: Mapped[float] = mapped_column(default=0.0)
    profile_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    staging_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    __table_args__ = (UniqueConstraint("institution_id", "file_hash", name="uq_batch_file"),)


class ImportRowError(Base, TimestampMixin):
    __tablename__ = "import_row_errors"
    id: Mapped[uuid.UUID] = PK()
    batch_id = FK("import_batches.id")
    row_number: Mapped[int] = mapped_column(Integer)
    field_name: Mapped[str] = mapped_column(String(128), default="")
    error_code: Mapped[str] = mapped_column(String(64))
    message: Mapped[str] = mapped_column(Text, default="")
    raw_value_redacted: Mapped[str] = mapped_column(String(64), default="")


class MappingProfile(Base, TimestampMixin):
    __tablename__ = "mapping_profiles"
    id: Mapped[uuid.UUID] = PK()
    institution_id = FK("institutions.id")
    source_headers_hash: Mapped[str] = mapped_column(String(64), index=True)
    mapping_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_by = FKn("users.id")
    version: Mapped[int] = mapped_column(Integer, default=1)


# ---------------- Records ----------------
class StudentRecord(Base, TimestampMixin):
    __tablename__ = "student_records"
    id: Mapped[uuid.UUID] = PK()
    institution_id = FK("institutions.id")
    source_batch_id = FKn("import_batches.id")
    academic_year: Mapped[str] = mapped_column(String(16), default="")
    name_enc: Mapped[str] = mapped_column(Text)
    name_norm_key: Mapped[str] = mapped_column(String(64), index=True)  # keyed blocking key
    apaar_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    apaar_token: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    apaar_last4: Mapped[str] = mapped_column(String(8), default="")
    key_version: Mapped[int] = mapped_column(Integer, default=1)
    dob_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(16), nullable=True)
    verification_status: Mapped[str] = mapped_column(String(32), default="UNVERIFIED")
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # feature columns stored for linkage blocking (keyed / non-identifying)
    phonetic_key: Mapped[str] = mapped_column(String(32), default="", index=True)
    sorted_token_key: Mapped[str] = mapped_column(String(64), default="", index=True)
    first_token_key: Mapped[str] = mapped_column(String(32), default="", index=True)


class EnrolmentEpisode(Base, TimestampMixin):
    __tablename__ = "enrolment_episodes"
    id: Mapped[uuid.UUID] = PK()
    student_record_id = FK("student_records.id")
    institution_id = FK("institutions.id")
    program_id = FK("programs.id")
    seat_category_id = FKn("seat_categories.id")
    admission_date: Mapped[date] = mapped_column(Date)
    valid_period = mapped_column(DATERANGE)
    status: Mapped[str] = mapped_column(String(32), default="active")
    end_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    transfer_from_episode_id = FKn("enrolment_episodes.id")
    counted_for_intake: Mapped[bool] = mapped_column(Boolean, default=True)


# ---------------- Linkage ----------------
class LinkageRun(Base, TimestampMixin):
    __tablename__ = "linkage_runs"
    id: Mapped[uuid.UUID] = PK()
    params_hash: Mapped[str] = mapped_column(String(64), default="")
    model_version: Mapped[str] = mapped_column(String(32), default="fs-1")
    metrics_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    candidate_count: Mapped[int] = mapped_column(Integer, default=0)


class IdentityLink(Base, TimestampMixin):
    __tablename__ = "identity_links"
    id: Mapped[uuid.UUID] = PK()
    record_a_id = FK("student_records.id")
    record_b_id = FK("student_records.id")
    match_weight: Mapped[float] = mapped_column(default=0.0)
    probability: Mapped[float] = mapped_column(default=0.0)
    band: Mapped[str] = mapped_column(String(16), default="Low")
    evidence_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    model_version: Mapped[str] = mapped_column(String(32), default="fs-1")
    run_id = FKn("linkage_runs.id")
    status: Mapped[str] = mapped_column(String(32), default="candidate")
    __table_args__ = (UniqueConstraint("record_a_id", "record_b_id", name="uq_link_pair"),)


class IdentityCluster(Base, TimestampMixin):
    __tablename__ = "identity_clusters"
    id: Mapped[uuid.UUID] = PK()
    status: Mapped[str] = mapped_column(String(32), default="proposed")
    created_from_run_id = FKn("linkage_runs.id")
    reviewed_by = FKn("users.id")


class ClusterMember(Base, TimestampMixin):
    __tablename__ = "cluster_members"
    id: Mapped[uuid.UUID] = PK()
    cluster_id = FK("identity_clusters.id")
    record_id = FK("student_records.id")


class LinkageLabel(Base, TimestampMixin):
    __tablename__ = "linkage_labels"
    id: Mapped[uuid.UUID] = PK()
    link_id = FK("identity_links.id")
    label: Mapped[str] = mapped_column(String(32))  # confirmed_same/confirmed_different/needs_info
    labelled_by = FKn("users.id")
    case_id = FKn("cases.id")


# ---------------- Exceptions / cases ----------------
class Exception_(Base, TimestampMixin):
    __tablename__ = "exceptions"
    id: Mapped[uuid.UUID] = PK()
    institution_id = FK("institutions.id")
    type: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(16), default="medium")
    status: Mapped[str] = mapped_column(String(32), default="Open")
    rule_code: Mapped[str] = mapped_column(String(64))
    rule_version: Mapped[int] = mapped_column(Integer, default=1)
    evidence_json: Mapped[dict] = mapped_column(JSONB, default=dict)  # masked
    case_id = FKn("cases.id")


class Case(Base, TimestampMixin):
    __tablename__ = "cases"
    id: Mapped[uuid.UUID] = PK()
    institution_id = FK("institutions.id")
    cluster_id = FKn("identity_clusters.id")
    scope: Mapped[str] = mapped_column(String(32), default="institution")
    holder: Mapped[str] = mapped_column(String(16), default="REVIEWER")  # REVIEWER|INSTITUTION
    status: Mapped[str] = mapped_column(String(32), default="Open")
    escalation_level: Mapped[int] = mapped_column(Integer, default=0)
    assigned_to = FKn("users.id")
    holder_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ageing_json: Mapped[dict] = mapped_column(JSONB, default=dict)


class CaseEvent(Base, TimestampMixin):
    __tablename__ = "case_events"
    id: Mapped[uuid.UUID] = PK()
    case_id = FK("cases.id")
    event_type: Mapped[str] = mapped_column(String(64))
    actor_id = FKn("users.id")
    detail_json: Mapped[dict] = mapped_column(JSONB, default=dict)


class InstitutionResponse(Base, TimestampMixin):
    __tablename__ = "institution_responses"
    id: Mapped[uuid.UUID] = PK()
    case_id = FK("cases.id")
    text: Mapped[str] = mapped_column(Text, default="")
    attachment_ref: Mapped[str] = mapped_column(String(255), default="")
    submitted_by = FKn("users.id")


# ---------------- Reveal / config / audit ----------------
class RevealRequest(Base, TimestampMixin):
    __tablename__ = "reveal_requests"
    id: Mapped[uuid.UUID] = PK()
    requester_id = FK("users.id")
    record_id = FK("student_records.id")
    case_id = FKn("cases.id")
    purpose: Mapped[str] = mapped_column(String(64))
    purpose_detail: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="REQUESTED")
    approver_id = FKn("users.id")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ConfigChangeRequest(Base, TimestampMixin):
    __tablename__ = "config_change_requests"
    id: Mapped[uuid.UUID] = PK()
    config_type: Mapped[str] = mapped_column(String(64))
    diff_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    proposed_by = FKn("users.id")
    approved_by = FKn("users.id")
    status: Mapped[str] = mapped_column(String(32), default="PROPOSED")
    reason: Mapped[str] = mapped_column(Text, default="")


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[uuid.UUID] = PK()
    seq: Mapped[int] = mapped_column(BigInteger, Identity(always=True), unique=True)
    actor_id = FKn("users.id")
    institution_id = FKn("institutions.id")
    action: Mapped[str] = mapped_column(String(64))
    entity_type: Mapped[str] = mapped_column(String(64), default="")
    entity_id: Mapped[str] = mapped_column(String(64), default="")
    before_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    after_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    reason: Mapped[str] = mapped_column(Text, default="")
    request_id: Mapped[str] = mapped_column(String(64), default="")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    prev_hash: Mapped[str] = mapped_column(String(64), default="")
    hash: Mapped[str] = mapped_column(String(64), default="")


class Notification(Base, TimestampMixin):
    __tablename__ = "notifications"
    id: Mapped[uuid.UUID] = PK()
    user_id = FK("users.id")
    type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    dedupe_key: Mapped[str] = mapped_column(String(128), index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class VerificationCheck(Base, TimestampMixin):
    __tablename__ = "verification_checks"
    id: Mapped[uuid.UUID] = PK()
    record_id = FK("student_records.id")
    provider: Mapped[str] = mapped_column(String(32), default="MOCK")
    status: Mapped[str] = mapped_column(String(32))
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    evidence_ref: Mapped[str] = mapped_column(String(255), default="")


# Tables carrying an institution scope (RLS applies).
INSTITUTION_SCOPED_TABLES = [
    "institutions",
    "programs",
    "import_batches",
    "import_row_errors",
    "mapping_profiles",
    "student_records",
    "enrolment_episodes",
    "exceptions",
    "cases",
    "institution_responses",
]

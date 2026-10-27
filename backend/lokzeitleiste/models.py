from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.dialects.mysql import LONGBLOB, MEDIUMTEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def now_utc():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(8), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    profile: Mapped["TfProfile | None"] = relationship(back_populates="user", uselist=False)


class TfProfile(Base):
    __tablename__ = "tf_profiles"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    last_name: Mapped[str] = mapped_column(String(120), nullable=False)
    first_name: Mapped[str] = mapped_column(String(120), nullable=False)
    personnel_number: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    target_hours_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    vacation_days: Mapped[int] = mapped_column(Integer, nullable=False)
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    bahncard: Mapped[int] = mapped_column(Integer, nullable=False)
    # Compatibility with the interim branch implementation; tf_identity is canonical.
    gender: Mapped[str] = mapped_column(String(20), default='unspecified', server_default='unspecified', nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    federal_state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    user: Mapped[User] = relationship(back_populates="profile")


class TfBahnCardValidity(Base):
    __tablename__ = "tf_bahncard_validity"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    valid_until: Mapped[date] = mapped_column(Date, nullable=False)


class SessionToken(Base):
    __tablename__ = "session_tokens"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class WorkMonth(Base):
    __tablename__ = "work_months"
    __table_args__ = (UniqueConstraint("tf_user_id", "year", "month"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tf_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    entries: Mapped[list["WorkEntry"]] = relationship(back_populates="work_month", cascade="all, delete-orphan")


class WorkEntry(Base):
    __tablename__ = "work_entries"
    __table_args__ = (UniqueConstraint("work_month_id", "client_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    work_month_id: Mapped[int] = mapped_column(ForeignKey("work_months.id"), nullable=False)
    client_id: Mapped[str] = mapped_column(String(36), nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[str] = mapped_column(String(5), nullable=False)
    end_time: Mapped[str] = mapped_column(String(5), nullable=False)
    pause_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    guest_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    away: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    accommodation: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    hotel_name: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, onupdate=now_utc, nullable=False)
    work_month: Mapped[WorkMonth] = relationship(back_populates="entries")
    date_override: Mapped["WorkEntryDates | None"] = relationship(cascade="all, delete-orphan",uselist=False)

    @property
    def explicit_end_date(self):
        return self.date_override.end_date if self.date_override else None


class ReportDispatch(Base):
    __tablename__ = "report_dispatches"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tf_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    work_month_id: Mapped[int] = mapped_column(ForeignKey("work_months.id"), nullable=False)
    recipient_email: Mapped[str] = mapped_column(String(320), nullable=False)
    filename: Mapped[str] = mapped_column(String(120), nullable=False)
    pdf_data: Mapped[bytes | None] = mapped_column(LargeBinary().with_variant(LONGBLOB(), "mysql"), nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="pending", nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class PlanMonth(Base):
    __tablename__ = "plan_months"
    __table_args__ = (UniqueConstraint("tf_user_id", "year", "month"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tf_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    days: Mapped[list["PlanDay"]] = relationship(back_populates="period", cascade="all, delete-orphan")


class PlanDay(Base):
    __tablename__ = "plan_days"
    __table_args__ = (UniqueConstraint("plan_month_id", "day"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_month_id: Mapped[int] = mapped_column(ForeignKey("plan_months.id"), nullable=False)
    day: Mapped[date] = mapped_column(Date, nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    note: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    period: Mapped[PlanMonth] = relationship(back_populates="days")


class PlanChange(Base):
    __tablename__ = "plan_changes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tf_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    admin_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    day: Mapped[date] = mapped_column(Date, nullable=False)
    previous_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    new_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    previous_note: Mapped[str] = mapped_column(String(500), nullable=False)
    new_note: Mapped[str] = mapped_column(String(500), nullable=False)
    source: Mapped[str] = mapped_column(String(12), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, nullable=False)


class WorkTimeChange(Base):
    __tablename__ = "work_time_changes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey("work_entries.id"), nullable=False, index=True)
    tf_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    admin_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    previous_start: Mapped[str] = mapped_column(String(5), nullable=False)
    previous_end: Mapped[str] = mapped_column(String(5), nullable=False)
    new_start: Mapped[str] = mapped_column(String(5), nullable=False)
    new_end: Mapped[str] = mapped_column(String(5), nullable=False)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    recipient_email: Mapped[str] = mapped_column(String(320), nullable=False)
    email_body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(12), default="pending", nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AccountPolicy(Base):
    __tablename__ = "account_policies"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class StaffProfile(Base):
    __tablename__ = "staff_profiles"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    first_name: Mapped[str] = mapped_column(String(120), nullable=False)
    last_name: Mapped[str] = mapped_column(String(120), nullable=False)
    nationality: Mapped[str] = mapped_column(String(120), nullable=False)
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    cost_center: Mapped[str] = mapped_column(String(80), nullable=False)


class StaffAddress(Base):
    __tablename__ = "staff_addresses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("staff_profiles.user_id"), nullable=False, index=True)
    street: Mapped[str] = mapped_column(String(200), nullable=False)
    house_number: Mapped[str] = mapped_column(String(30), nullable=False)
    postal_code: Mapped[str] = mapped_column(String(20), nullable=False)
    city: Mapped[str] = mapped_column(String(120), nullable=False)


class ModulePermission(Base):
    __tablename__ = "module_permissions"
    __table_args__ = (UniqueConstraint("user_id", "module"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    module: Mapped[str] = mapped_column(String(40), nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False)


class AccountAudit(Base):
    __tablename__ = "account_audits"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    target_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, nullable=False)


class WorkEntryLock(Base):
    __tablename__ = "work_entry_locks"
    entry_id: Mapped[int] = mapped_column(ForeignKey("work_entries.id"), primary_key=True)
    locked: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, nullable=False)


class WorkEntryAudit(Base):
    __tablename__ = "work_entry_audits"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey("work_entries.id"), nullable=False, index=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, nullable=False)


class ProfilePhoto(Base):
    __tablename__ = "profile_photos"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    image_data: Mapped[bytes] = mapped_column(LargeBinary().with_variant(LONGBLOB(), "mysql"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, onupdate=now_utc, nullable=False)


class WorkEntryDates(Base):
    __tablename__ = "work_entry_dates"
    entry_id: Mapped[int] = mapped_column(ForeignKey("work_entries.id"),primary_key=True)
    end_date: Mapped[date] = mapped_column(Date,nullable=False)


class ShiftModel(Base):
    __tablename__ = 'shift_models'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    blocks: Mapped[str] = mapped_column(Text, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class ShiftAssignment(Base):
    __tablename__ = 'shift_assignments'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_id: Mapped[int] = mapped_column(ForeignKey('shift_models.id'), nullable=False)
    tf_user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    admin_user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    cycle_start: Mapped[date] = mapped_column(Date, nullable=False)
    model_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    overwrite: Mapped[bool] = mapped_column(Boolean, nullable=False)
    changed_days: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, nullable=False)


class MailboxAccount(Base):
    __tablename__ = 'mailbox_accounts'
    tf_user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), primary_key=True)
    address: Mapped[str] = mapped_column(String(320), nullable=False)
    username: Mapped[str] = mapped_column(String(320), nullable=False)
    password_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, onupdate=now_utc, nullable=False)


class MailDraft(Base):
    __tablename__ = 'mail_drafts'
    actor_id: Mapped[int] = mapped_column(ForeignKey('users.id'), primary_key=True)
    tf_user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), primary_key=True)
    recipient: Mapped[str] = mapped_column(String(2000), default='', nullable=False)
    subject: Mapped[str] = mapped_column(String(300), default='', nullable=False)
    body: Mapped[str] = mapped_column(Text().with_variant(MEDIUMTEXT(), 'mysql'), default='', nullable=False)


class UserLocale(Base):
    __tablename__ = 'user_locales'
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), primary_key=True)
    language: Mapped[str] = mapped_column(String(2), default='de', nullable=False)


class MailboxSettings(Base):
    __tablename__ = 'mailbox_settings'
    tf_user_id: Mapped[int] = mapped_column(ForeignKey('mailbox_accounts.tf_user_id'), primary_key=True)
    config_json: Mapped[str] = mapped_column(Text, nullable=False)
    tokens_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)


class MailboxAuthorization(Base):
    __tablename__ = 'mailbox_authorizations'
    tf_user_id: Mapped[int] = mapped_column(ForeignKey('mailbox_accounts.tf_user_id'), primary_key=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey('users.id'), primary_key=True)
    device_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    next_poll_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    interval: Mapped[int] = mapped_column(Integer, nullable=False)


class TfDutyProfile(Base):
    __tablename__ = 'tf_duty_profiles'
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), primary_key=True)
    driver_type: Mapped[str] = mapped_column(String(16), nullable=False, default='route')


class PlanDuty(Base):
    __tablename__ = 'plan_duties'
    tf_user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), primary_key=True)
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    shift: Mapped[str] = mapped_column(String(16), nullable=False)


class PlanDutyAudit(Base):
    __tablename__ = 'plan_duty_audits'
    change_id: Mapped[int] = mapped_column(ForeignKey('plan_changes.id'), primary_key=True)
    previous_shift: Mapped[str] = mapped_column(String(16), nullable=False)
    new_shift: Mapped[str] = mapped_column(String(16), nullable=False)


class MailboxOAuthState(Base):
    __tablename__ = 'mailbox_oauth_states'
    state_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    tf_user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    actor_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    encrypted_payload: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class TfEmployment(Base):
    __tablename__ = "tf_employment"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    tf_number: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    weekly_minutes: Mapped[int] = mapped_column(Integer, default=2400, nullable=False)
    entry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    exit_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    immediate_block: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    nationality: Mapped[str | None] = mapped_column(String(2), nullable=True)
    home_station: Mapped[str | None] = mapped_column(String(10), nullable=True)


class TfAddress(Base):
    __tablename__ = "tf_addresses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    street: Mapped[str] = mapped_column(String(200), nullable=False)
    house_number: Mapped[str] = mapped_column(String(30), nullable=False)
    postal_code: Mapped[str] = mapped_column(String(20), nullable=False)
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    federal_state: Mapped[str] = mapped_column(String(2), nullable=False)
    is_postal: Mapped[bool] = mapped_column(Boolean, nullable=False)


class RailwayStation(Base):
    __tablename__ = "railway_stations"
    code: Mapped[str] = mapped_column(String(10), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)


class TfNumberMigration(Base):
    __tablename__ = "tf_number_migrations"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    previous_username: Mapped[str] = mapped_column(String(64), nullable=False)
    tf_number: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, nullable=False)


class TfIdentity(Base):
    __tablename__ = "tf_identity"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    gender: Mapped[str] = mapped_column(String(16), default="unspecified", nullable=False)


class DutyReport(Base):
    __tablename__='duty_reports'
    __table_args__=(UniqueConstraint('tf_user_id','client_id'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    tf_user_id:Mapped[int]=mapped_column(ForeignKey('users.id'),nullable=False,index=True)
    entry_id:Mapped[int]=mapped_column(ForeignKey('work_entries.id'),nullable=False,unique=True)
    client_id:Mapped[str]=mapped_column(String(36),nullable=False)
    payload_json:Mapped[str]=mapped_column(Text,nullable=False)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=now_utc,nullable=False)


class DutyGuestTrip(Base):
    __tablename__='duty_guest_trips'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    report_id:Mapped[int]=mapped_column(ForeignKey('duty_reports.id'),nullable=False,index=True)
    start_station:Mapped[str]=mapped_column(String(10),nullable=False)
    end_station:Mapped[str]=mapped_column(String(10),nullable=False)
    start_at:Mapped[datetime]=mapped_column(DateTime,nullable=False)
    end_at:Mapped[datetime]=mapped_column(DateTime,nullable=False)
    transport:Mapped[str]=mapped_column(String(20),nullable=False)
    transport_detail:Mapped[str]=mapped_column(String(140),default='',nullable=False)


class DutyReceipt(Base):
    __tablename__='duty_receipts'
    __table_args__=(UniqueConstraint('report_id','content_hash'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    report_id:Mapped[int]=mapped_column(ForeignKey('duty_reports.id'),nullable=False,index=True)
    filename:Mapped[str]=mapped_column(String(120),nullable=False)
    mime_type:Mapped[str]=mapped_column(String(40),nullable=False)
    content_hash:Mapped[str]=mapped_column(String(64),nullable=False)
    content:Mapped[bytes]=mapped_column(LargeBinary().with_variant(LONGBLOB(),'mysql'),nullable=False)
    recipient_email:Mapped[str]=mapped_column(String(320),default='',nullable=False)
    status:Mapped[str]=mapped_column(String(12),default='pending',nullable=False)
    attempts:Mapped[int]=mapped_column(Integer,default=0,nullable=False)
    last_error:Mapped[str]=mapped_column(String(500),default='',nullable=False)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=now_utc,nullable=False)
    sent_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)


class DocumentFile(Base):
    __tablename__='document_files'
    __table_args__=(UniqueConstraint('owner_id','source_key'),UniqueConstraint('owner_id','relative_path'))
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    owner_id:Mapped[int]=mapped_column(ForeignKey('users.id'),nullable=False,index=True)
    uploader_id:Mapped[int|None]=mapped_column(ForeignKey('users.id'),nullable=True)
    relative_path:Mapped[str]=mapped_column(String(500),nullable=False)
    display_name:Mapped[str]=mapped_column(String(255),nullable=False)
    source_key:Mapped[str|None]=mapped_column(String(100),nullable=True)
    byte_size:Mapped[int]=mapped_column(Integer,nullable=False)
    sha256:Mapped[str]=mapped_column(String(64),nullable=False)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=now_utc,nullable=False)
    updated_at:Mapped[datetime]=mapped_column(DateTime,default=now_utc,nullable=False)


class DocumentRenderState(Base):
    __tablename__='document_render_states'
    document_id:Mapped[int]=mapped_column(ForeignKey('document_files.id',ondelete='CASCADE'),primary_key=True)
    format_version:Mapped[int]=mapped_column(Integer,nullable=False,default=5)


class OvertimePolicy(Base):
    __tablename__='overtime_policies'
    tf_user_id:Mapped[int]=mapped_column(ForeignKey('users.id'),primary_key=True)
    month:Mapped[date]=mapped_column(Date,primary_key=True)
    enabled:Mapped[bool]=mapped_column(Boolean,nullable=False)
    actor_id:Mapped[int]=mapped_column(ForeignKey('users.id'),nullable=False)
    updated_at:Mapped[datetime]=mapped_column(DateTime,default=now_utc,nullable=False)


class OvertimeClosing(Base):
    __tablename__='overtime_closings'
    tf_user_id:Mapped[int]=mapped_column(ForeignKey('users.id'),primary_key=True)
    month:Mapped[date]=mapped_column(Date,primary_key=True)
    status:Mapped[str]=mapped_column(String(12),default='open',nullable=False)
    mode:Mapped[str]=mapped_column(String(12),default='payout',nullable=False)
    total_minutes:Mapped[int]=mapped_column(Integer,default=0,nullable=False)
    annual_minutes:Mapped[int]=mapped_column(Integer,default=0,nullable=False)
    payout_minutes:Mapped[int]=mapped_column(Integer,default=0,nullable=False)
    fingerprint:Mapped[str]=mapped_column(String(64),default='',nullable=False)
    revision:Mapped[int]=mapped_column(Integer,default=0,nullable=False)
    actor_id:Mapped[int]=mapped_column(ForeignKey('users.id'),nullable=False)
    updated_at:Mapped[datetime]=mapped_column(DateTime,default=now_utc,nullable=False)


class OvertimeAudit(Base):
    __tablename__='overtime_audits'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    tf_user_id:Mapped[int]=mapped_column(ForeignKey('users.id'),nullable=False,index=True)
    month:Mapped[date]=mapped_column(Date,nullable=False)
    actor_id:Mapped[int]=mapped_column(ForeignKey('users.id'),nullable=False)
    action:Mapped[str]=mapped_column(String(20),nullable=False)
    snapshot_json:Mapped[str]=mapped_column(Text,nullable=False)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=now_utc,nullable=False)



class TfStation(Base):
    __tablename__='tf_stations'
    __table_args__=(UniqueConstraint('owner_id','code'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    owner_id:Mapped[int]=mapped_column(ForeignKey('users.id'),nullable=False,index=True)
    code:Mapped[str]=mapped_column(String(10),nullable=False)
    name:Mapped[str]=mapped_column(String(200),nullable=False)
    contacts_json:Mapped[str]=mapped_column(Text,default='[]',nullable=False)
    revision:Mapped[int]=mapped_column(Integer,default=1,nullable=False)


class TfStationPlan(Base):
    __tablename__='tf_station_plans'
    station_id:Mapped[int]=mapped_column(ForeignKey('tf_stations.id',ondelete='CASCADE'),primary_key=True)
    filename:Mapped[str]=mapped_column(String(120),nullable=False)
    mime_type:Mapped[str]=mapped_column(String(40),nullable=False)
    content:Mapped[bytes]=mapped_column(LargeBinary().with_variant(LONGBLOB(),'mysql'),nullable=False)


class TfStationShare(Base):
    __tablename__='tf_station_shares'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    owner_id:Mapped[int]=mapped_column(ForeignKey('users.id'),nullable=False,index=True)
    token_hash:Mapped[str]=mapped_column(String(64),unique=True,nullable=False)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=now_utc,nullable=False)
    expires_at:Mapped[datetime]=mapped_column(DateTime,nullable=False)
    revoked:Mapped[bool]=mapped_column(Boolean,default=False,nullable=False)


class TfStationShareItem(Base):
    __tablename__='tf_station_share_items'
    __table_args__=(UniqueConstraint('share_id','code'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    share_id:Mapped[int]=mapped_column(ForeignKey('tf_station_shares.id',ondelete='CASCADE'),nullable=False,index=True)
    code:Mapped[str]=mapped_column(String(10),nullable=False)
    name:Mapped[str]=mapped_column(String(200),nullable=False)
    contacts_json:Mapped[str]=mapped_column(Text,nullable=False)
    plan_filename:Mapped[str|None]=mapped_column(String(120),nullable=True)
    plan_mime_type:Mapped[str|None]=mapped_column(String(40),nullable=True)
    plan_content:Mapped[bytes|None]=mapped_column(LargeBinary().with_variant(LONGBLOB(),'mysql'),nullable=True)


class TfStationDelivery(Base):
    __tablename__='tf_station_deliveries'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    share_id:Mapped[int]=mapped_column(ForeignKey('tf_station_shares.id',ondelete='CASCADE'),unique=True,nullable=False)
    recipient_id:Mapped[int]=mapped_column(ForeignKey('users.id'),index=True,nullable=False)


class TfStationNotes(Base):
    __tablename__='tf_station_notes'
    station_id:Mapped[int]=mapped_column(ForeignKey('tf_stations.id',ondelete='CASCADE'),primary_key=True)
    locomotive_parking:Mapped[str]=mapped_column(String(120),default='',nullable=False)
    train_securing:Mapped[str]=mapped_column(String(120),default='',nullable=False)
    special_features:Mapped[str]=mapped_column(Text,default='',nullable=False)


class TfStationShareNotes(Base):
    __tablename__='tf_station_share_notes'
    item_id:Mapped[int]=mapped_column(ForeignKey('tf_station_share_items.id',ondelete='CASCADE'),primary_key=True)
    locomotive_parking:Mapped[str]=mapped_column(String(120),default='',nullable=False)
    train_securing:Mapped[str]=mapped_column(String(120),default='',nullable=False)
    special_features:Mapped[str]=mapped_column(Text,default='',nullable=False)


class RailwayVehicle(Base):
    __tablename__='railway_vehicles'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    vehicle_number:Mapped[str]=mapped_column(String(16),unique=True,nullable=False)
    status:Mapped[str]=mapped_column(String(20),nullable=False)
    status_note:Mapped[str]=mapped_column(Text,default='',nullable=False)
    series:Mapped[str]=mapped_column(String(120),default='',nullable=False)
    lessor:Mapped[str]=mapped_column(String(200),default='',nullable=False)
    hotline:Mapped[str]=mapped_column(String(60),default='',nullable=False)
    name:Mapped[str]=mapped_column(String(120),default='',nullable=False)
    power_kw:Mapped[str]=mapped_column(String(40),default='',nullable=False)
    brake_r:Mapped[int]=mapped_column(Integer,nullable=False)
    brake_p:Mapped[int]=mapped_column(Integer,nullable=False)
    brake_g:Mapped[int]=mapped_column(Integer,nullable=False)
    spring_brake:Mapped[int]=mapped_column(Integer,nullable=False)
    spring_unit:Mapped[str]=mapped_column(String(2),nullable=False)
    next_revision:Mapped[date|None]=mapped_column(Date,nullable=True)
    mileage:Mapped[int]=mapped_column(Integer,nullable=False)
    notes:Mapped[str]=mapped_column(Text,default='',nullable=False)
    revision:Mapped[int]=mapped_column(Integer,default=1,nullable=False)
    updated_at:Mapped[datetime]=mapped_column(DateTime,default=now_utc,nullable=False)


class TrainGpsRecording(Base):
    __tablename__='train_gps_recordings'
    __table_args__=(UniqueConstraint('owner_id','journey_id'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    owner_id:Mapped[int]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'),nullable=False,index=True)
    journey_id:Mapped[str]=mapped_column(String(36),nullable=False)
    payload_json:Mapped[str]=mapped_column(Text().with_variant(MEDIUMTEXT(),'mysql'),nullable=False)
    revision:Mapped[int]=mapped_column(Integer,default=1,nullable=False)


class GpsStationCache(Base):
    __tablename__='gps_station_cache'
    cell:Mapped[str]=mapped_column(String(40),primary_key=True)
    payload_json:Mapped[str]=mapped_column(Text().with_variant(MEDIUMTEXT(),'mysql'),nullable=False)
    updated_at:Mapped[datetime]=mapped_column(DateTime,default=now_utc,nullable=False)

class AppDefaultValue(Base):
    __tablename__='app_default_values'
    __table_args__=(UniqueConstraint('category','value'),UniqueConstraint('category','label_key'))
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    category:Mapped[str]=mapped_column(String(10),nullable=False)
    value:Mapped[str]=mapped_column(String(64),nullable=False)
    label:Mapped[str]=mapped_column(String(200),nullable=False)
    label_key:Mapped[str]=mapped_column(String(400),nullable=False)
    active:Mapped[bool]=mapped_column(Boolean,nullable=False,default=True)
    ever_used:Mapped[bool]=mapped_column(Boolean,nullable=False,default=False)
    revision:Mapped[int]=mapped_column(Integer,nullable=False,default=1)

class AppDefaultSeed(Base):
    __tablename__='app_default_seed'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)

class BackendMenuPreference(Base):
    __tablename__='backend_menu_preferences'
    user_id:Mapped[int]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'),primary_key=True)
    variant:Mapped[str]=mapped_column(String(16),nullable=False,default='sidebar')
    revision:Mapped[int]=mapped_column(Integer,nullable=False,default=1)

class LocoHandoverDefault(Base):
    """Separate vocabulary for handovers; never mixed with train-event choices."""
    __tablename__='loco_handover_defaults'
    __table_args__=(UniqueConstraint('kind','scope_id','label_key'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    kind:Mapped[str]=mapped_column(String(16),nullable=False)
    label:Mapped[str]=mapped_column(String(255),nullable=False)
    label_key:Mapped[str]=mapped_column(String(510),nullable=False)
    email:Mapped[str]=mapped_column(String(254),nullable=False,default='')
    hotline_name:Mapped[str]=mapped_column(String(255),nullable=False,default='')
    hotline_email:Mapped[str]=mapped_column(String(254),nullable=False,default='')
    parent_id:Mapped[int|None]=mapped_column(ForeignKey('loco_handover_defaults.id'),nullable=True)
    scope_id:Mapped[int]=mapped_column(Integer,nullable=False,default=0)
    revision:Mapped[int]=mapped_column(Integer,nullable=False,default=1)

class LocoHandoverProtocol(Base):
    __tablename__='loco_handover_protocols'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    vehicle_id:Mapped[int]=mapped_column(ForeignKey('railway_vehicles.id'),nullable=False,index=True)
    author_id:Mapped[int|None]=mapped_column(ForeignKey('users.id',ondelete='SET NULL'),nullable=True)
    author_name:Mapped[str]=mapped_column(String(255),nullable=False)
    occurred_at:Mapped[datetime]=mapped_column(DateTime,nullable=False,index=True)
    payload_json:Mapped[str]=mapped_column(Text,nullable=False)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=now_utc,nullable=False)

class LocoHandoverAttachment(Base):
    __tablename__='loco_handover_attachments'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    protocol_id:Mapped[int]=mapped_column(ForeignKey('loco_handover_protocols.id',ondelete='CASCADE'),nullable=False,index=True)
    filename:Mapped[str]=mapped_column(String(120),nullable=False)
    mime_type:Mapped[str]=mapped_column(String(80),nullable=False)
    content:Mapped[bytes]=mapped_column(LargeBinary().with_variant(LONGBLOB(),'mysql'),nullable=False)

class LocoHandoverAttachmentChunk(Base):
    """Bound SQL packet size for host MySQL installations with small packet limits."""
    __tablename__='loco_handover_attachment_chunks'
    attachment_id:Mapped[int]=mapped_column(ForeignKey('loco_handover_attachments.id',ondelete='CASCADE'),primary_key=True)
    position:Mapped[int]=mapped_column(Integer,primary_key=True)
    content:Mapped[bytes]=mapped_column(LargeBinary().with_variant(LONGBLOB(),'mysql'),nullable=False)


class EmailDomain(Base):
    __tablename__ = 'email_domains'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(253), unique=True, nullable=False)


class EmployeeEmail(Base):
    __tablename__ = 'employee_emails'
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), primary_key=True)
    address: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    managed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class MailboxProvision(Base):
    __tablename__ = 'mailbox_provisions'
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), primary_key=True)
    address: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default='pending', nullable=False)
    error: Mapped[str] = mapped_column(String(200), default='', nullable=False)


class LeasingCompany(Base):
    __tablename__='leasing_companies'
    seed_key:Mapped[str|None]=mapped_column(String(40),unique=True,nullable=True)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    company:Mapped[str]=mapped_column(String(200),unique=True,nullable=False)
    contact:Mapped[str]=mapped_column(String(200),default='',nullable=False)
    street:Mapped[str]=mapped_column(String(255),default='',nullable=False)
    postal_code:Mapped[str]=mapped_column(String(7),default='',nullable=False)
    city:Mapped[str]=mapped_column(String(200),default='',nullable=False)
    country:Mapped[str]=mapped_column(String(2),default='DE',nullable=False)
    email:Mapped[str]=mapped_column(String(254),default='',nullable=False)
    phone:Mapped[str]=mapped_column(String(60),default='',nullable=False)
    mobile:Mapped[str]=mapped_column(String(60),default='',nullable=False)
    hotline:Mapped[str]=mapped_column(String(60),default='',nullable=False)
    notes:Mapped[str]=mapped_column(Text,default='',nullable=False)
    revision:Mapped[int]=mapped_column(Integer,default=1,nullable=False)


class VehicleLeasing(Base):
    __tablename__='vehicle_leasing'
    vehicle_id:Mapped[int]=mapped_column(ForeignKey('railway_vehicles.id'),primary_key=True)
    company_id:Mapped[int]=mapped_column(ForeignKey('leasing_companies.id'),nullable=False,index=True)


class SystemChangeLog(Base):
    __tablename__='system_change_log'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    changed_at:Mapped[datetime]=mapped_column(DateTime,default=now_utc,nullable=False,index=True)
    module:Mapped[str]=mapped_column(String(255),nullable=False)
    employee_id:Mapped[int|None]=mapped_column(Integer,nullable=True,index=True)
    employee:Mapped[str]=mapped_column(String(255),nullable=False)
    change:Mapped[str]=mapped_column(Text().with_variant(MEDIUMTEXT(),'mysql'),nullable=False)


class SystemMigration(Base):
    __tablename__='system_migrations'
    key:Mapped[str]=mapped_column(String(100),primary_key=True)
    applied_at:Mapped[datetime]=mapped_column(DateTime,default=now_utc,nullable=False)


class PlanningNoteBackup(Base):
    __tablename__='planning_note_backup'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    plan_day_id:Mapped[int]=mapped_column(Integer,nullable=False)
    tf_id:Mapped[int]=mapped_column(Integer,nullable=False)
    day:Mapped[date]=mapped_column(Date,nullable=False)
    note:Mapped[str]=mapped_column(Text,nullable=False)
    saved_at:Mapped[datetime]=mapped_column(DateTime,default=now_utc,nullable=False)


class AppDefaultOrder(Base):
    __tablename__='app_default_orders'
    scope:Mapped[str]=mapped_column(String(100),primary_key=True)
    ids_json:Mapped[str]=mapped_column(Text().with_variant(MEDIUMTEXT(),'mysql'),nullable=False)
    revision:Mapped[int]=mapped_column(Integer,nullable=False,default=1)


class VehicleRetirement(Base):
    """Separate table allows upgrading existing databases without altering vehicle data."""
    __tablename__='vehicle_retirements'
    vehicle_id:Mapped[int]=mapped_column(ForeignKey('railway_vehicles.id'),primary_key=True)


class DutyReportDraft(Base):
    __tablename__='duty_report_drafts'
    __table_args__=(UniqueConstraint('owner_id','client_id'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    owner_id:Mapped[int]=mapped_column(ForeignKey('users.id'),nullable=False,index=True)
    client_id:Mapped[str]=mapped_column(String(36),nullable=False)
    payload_json:Mapped[str]=mapped_column(Text().with_variant(MEDIUMTEXT(),'mysql'),nullable=False)
    receipt_keys_json:Mapped[str]=mapped_column(Text,nullable=False,default='[]')
    revision:Mapped[int]=mapped_column(Integer,nullable=False,default=1)
    finalized_report_id:Mapped[int|None]=mapped_column(ForeignKey('duty_reports.id'),nullable=True)
    updated_at:Mapped[datetime]=mapped_column(DateTime,default=now_utc,nullable=False)


class DutyReportDraftFile(Base):
    __tablename__='duty_report_draft_files'
    __table_args__=(UniqueConstraint('draft_id','file_key'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    draft_id:Mapped[int]=mapped_column(ForeignKey('duty_report_drafts.id'),nullable=False,index=True)
    file_key:Mapped[str]=mapped_column(String(36),nullable=False)
    filename:Mapped[str]=mapped_column(String(120),nullable=False)
    mime_type:Mapped[str]=mapped_column(String(40),nullable=False)
    content_hash:Mapped[str]=mapped_column(String(64),nullable=False)
    content:Mapped[bytes]=mapped_column(LargeBinary().with_variant(LONGBLOB(),'mysql'),nullable=False)


class AccountLoginStamp(Base):
    __tablename__='account_login_stamps'
    user_id:Mapped[int]=mapped_column(ForeignKey('users.id'),primary_key=True)
    last_login_at:Mapped[datetime]=mapped_column(DateTime,nullable=False)
    previous_login_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)


class TfMessageAttachment(Base):
    __tablename__='tf_message_attachments'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    filename:Mapped[str]=mapped_column(String(200),nullable=False)
    mime_type:Mapped[str]=mapped_column(String(80),nullable=False)
    content:Mapped[bytes]=mapped_column(LargeBinary().with_variant(LONGBLOB(),'mysql'),nullable=False)


class TfMessage(Base):
    __tablename__='tf_messages'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    sender_id:Mapped[int]=mapped_column(ForeignKey('users.id'),nullable=False,index=True)
    sender_name:Mapped[str]=mapped_column(String(250),nullable=False)
    subject:Mapped[str]=mapped_column(String(200),nullable=False)
    body:Mapped[str]=mapped_column(Text,nullable=False)
    attachment_id:Mapped[int|None]=mapped_column(ForeignKey('tf_message_attachments.id'),nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=now_utc,nullable=False,index=True)


class TfMessageDelivery(Base):
    __tablename__='tf_message_deliveries'
    __table_args__=(UniqueConstraint('message_id','recipient_id'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    message_id:Mapped[int]=mapped_column(ForeignKey('tf_messages.id'),nullable=False,index=True)
    recipient_id:Mapped[int]=mapped_column(ForeignKey('users.id'),nullable=False,index=True)
    read_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    deleted_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)


class StaffPersonnelNumber(Base):
    __tablename__ = 'staff_personnel_numbers'
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'),primary_key=True)
    number: Mapped[str] = mapped_column(String(30),nullable=False)


class VehicleTechnicalData(Base):
    __tablename__='vehicle_technical_data'
    vehicle_id:Mapped[int]=mapped_column(ForeignKey('railway_vehicles.id'),primary_key=True)
    length_mm:Mapped[int|None]=mapped_column(Integer,nullable=True)
    weight_kg:Mapped[int|None]=mapped_column(Integer,nullable=True)
    axle_count:Mapped[int|None]=mapped_column(Integer,nullable=True)
    brake_shoe:Mapped[str|None]=mapped_column(String(1),nullable=True)


class BrakeSheetDraft(Base):
    __tablename__='brake_sheet_drafts'
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    owner_id:Mapped[int]=mapped_column(ForeignKey('users.id'),nullable=False,index=True)
    payload_json:Mapped[str]=mapped_column(Text,nullable=False)
    calculation_json:Mapped[str]=mapped_column(Text,nullable=False)
    revision:Mapped[int]=mapped_column(Integer,nullable=False,default=1)
    created_at:Mapped[datetime]=mapped_column(DateTime,nullable=False,default=now_utc)
    created_by_name:Mapped[str]=mapped_column(String(241),nullable=False)
    updated_at:Mapped[datetime]=mapped_column(DateTime,nullable=False,default=now_utc)


class BrakeSheetDispatch(Base):
    __tablename__='brake_sheet_dispatches'
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    owner_id:Mapped[int]=mapped_column(ForeignKey('users.id'),nullable=False,index=True)
    draft_id:Mapped[str]=mapped_column(ForeignKey('brake_sheet_drafts.id'),nullable=False)
    draft_revision:Mapped[int]=mapped_column(Integer,nullable=False)
    document_id:Mapped[int]=mapped_column(ForeignKey('document_files.id'),nullable=False)
    filename:Mapped[str]=mapped_column(String(200),nullable=False)
    sender:Mapped[str]=mapped_column(String(320),nullable=False)
    mail_json:Mapped[str]=mapped_column(Text,nullable=False)
    pdf_content:Mapped[bytes]=mapped_column(LargeBinary().with_variant(LONGBLOB(),'mysql'),nullable=False)
    image_content:Mapped[bytes]=mapped_column(LargeBinary().with_variant(LONGBLOB(),'mysql'),nullable=False)
    status:Mapped[str]=mapped_column(String(20),nullable=False,default='ready')
    warning:Mapped[str]=mapped_column(String(1000),nullable=False,default='')
    created_at:Mapped[datetime]=mapped_column(DateTime,nullable=False,default=now_utc)
    sent_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)


class NationalBrakeSheetDraft(Base):
    __tablename__='national_brake_sheet_drafts'
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    owner_id:Mapped[int]=mapped_column(ForeignKey('users.id'),nullable=False,index=True)
    payload_json:Mapped[str]=mapped_column(Text,nullable=False)
    calculation_json:Mapped[str]=mapped_column(Text,nullable=False)
    revision:Mapped[int]=mapped_column(Integer,nullable=False,default=1)
    created_at:Mapped[datetime]=mapped_column(DateTime,nullable=False,default=now_utc)
    created_by_name:Mapped[str]=mapped_column(String(241),nullable=False)
    updated_at:Mapped[datetime]=mapped_column(DateTime,nullable=False,default=now_utc)


class UserSignature(Base):
    __tablename__='user_signatures'
    user_id:Mapped[int]=mapped_column(ForeignKey('users.id'),primary_key=True)
    image_data:Mapped[bytes]=mapped_column(LargeBinary().with_variant(LONGBLOB(),'mysql'),nullable=False)
    updated_at:Mapped[datetime]=mapped_column(DateTime,default=now_utc,onupdate=now_utc,nullable=False)

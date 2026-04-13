from sqlalchemy import Column, String, DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from database.connection import Base


class AttendanceStatus(str, enum.Enum):
    present = "present"
    late    = "late"
    absent  = "absent"   # set by admin after event ends for no-shows


class AttendanceLog(Base):
    __tablename__ = "attendance_logs"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id    = Column(UUID(as_uuid=True), ForeignKey("students.id"), nullable=False)
    event_id      = Column(UUID(as_uuid=True), ForeignKey("events.id"),   nullable=False)
    scanned_by    = Column(UUID(as_uuid=True), ForeignKey("admins.id"),   nullable=True)   # null if auto-absent
    status        = Column(Enum(AttendanceStatus), nullable=False)
    scanned_at    = Column(DateTime, nullable=True)                   # null for auto-absent
    scanned_out_at= Column(DateTime, nullable=True)                   # exit scan timestamp
    override_note = Column(String(255), nullable=True)                # reason if manually changed
    created_at    = Column(DateTime, default=datetime.utcnow)

    student          = relationship("Student", back_populates="attendance_logs")
    event            = relationship("Event",   back_populates="attendance_logs")
    scanned_by_admin = relationship("Admin",   back_populates="attendance_logs")

    def __repr__(self):
        return f"<AttendanceLog student={self.student_id} event={self.event_id} [{self.status}]>"

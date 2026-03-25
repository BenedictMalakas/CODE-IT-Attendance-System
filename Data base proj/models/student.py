from sqlalchemy import Column, String, DateTime, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from database.connection import Base


class StudentStatus(str, enum.Enum):
    pending  = "pending"    # registered, waiting for admin approval
    active   = "active"     # approved, has QR code
    rejected = "rejected"   # admin rejected the ID photo


class Student(Base):
    __tablename__ = "students"

    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name           = Column(String(100),  nullable=False)
    section        = Column(String(50),   nullable=False)
    student_id     = Column(String(50),   nullable=False, unique=True)  # e.g. "2024-0001"
    password_hash  = Column(String(255),  nullable=False)
    id_photo_path  = Column(String(500),  nullable=False)               # uploaded school ID photo
    status         = Column(Enum(StudentStatus), default=StudentStatus.pending, nullable=False)
    rejection_note = Column(String(255),  nullable=True)                # reason if rejected
    created_at     = Column(DateTime,     default=datetime.utcnow)
    updated_at     = Column(DateTime,     default=datetime.utcnow, onupdate=datetime.utcnow)

    qr_token         = relationship("QRToken",        back_populates="student", uselist=False)
    attendance_logs  = relationship("AttendanceLog",  back_populates="student")

    def __repr__(self):
        return f"<Student {self.student_id} — {self.name} [{self.status}]>"

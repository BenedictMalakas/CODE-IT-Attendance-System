from sqlalchemy import Column, String, Boolean, DateTime, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from database.connection import Base


class AdminRole(str, enum.Enum):
    chairperson    = "chairperson"
    vits           = "vits"           # VITS Officer
    representative = "representative"


class Admin(Base):
    __tablename__ = "admins"

    id                    = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name                  = Column(String(100),  nullable=False)
    email                 = Column(String(150),  nullable=False, unique=True)
    password_hash         = Column(String(255),  nullable=False)
    role                  = Column(Enum(AdminRole), nullable=False, default=AdminRole.vits)
    is_active             = Column(Boolean,      default=True)
    force_password_change = Column(Boolean,      default=False)
    created_at            = Column(DateTime,     default=datetime.utcnow)

    events           = relationship("Event",         back_populates="created_by_admin")
    attendance_logs  = relationship("AttendanceLog", back_populates="scanned_by_admin")
    admin_sections   = relationship("AdminSection",  back_populates="admin")

    def __repr__(self):
        return f"<Admin {self.email} [{self.role}]>"

from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from database.connection import Base


class Admin(Base):
    __tablename__ = "admins"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name          = Column(String(100),  nullable=False)
    email         = Column(String(150),  nullable=False, unique=True)
    password_hash = Column(String(255),  nullable=False)
    is_active     = Column(Boolean,      default=True)
    created_at    = Column(DateTime,     default=datetime.utcnow)

    events           = relationship("Event",         back_populates="created_by_admin")
    attendance_logs  = relationship("AttendanceLog", back_populates="scanned_by_admin")

    def __repr__(self):
        return f"<Admin {self.email}>"

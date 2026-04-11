from sqlalchemy import Column, String, Integer, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from database.connection import Base


class Section(Base):
    __tablename__ = "sections"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name       = Column(String(50),  nullable=False, unique=True)   # e.g. "BSIT-1A"
    year_level = Column(Integer,     nullable=False)                 # 1, 2, 3, or 4
    created_at = Column(DateTime,    default=datetime.utcnow)

    students         = relationship("Student",      back_populates="section_rel")
    admin_sections   = relationship("AdminSection", back_populates="section")

    def __repr__(self):
        return f"<Section {self.name} (Year {self.year_level})>"

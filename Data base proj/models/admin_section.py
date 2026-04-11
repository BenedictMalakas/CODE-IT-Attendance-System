from sqlalchemy import Column, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from database.connection import Base


class AdminSection(Base):
    """Maps Representative admins to the sections they are assigned to."""
    __tablename__ = "admin_sections"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    admin_id   = Column(UUID(as_uuid=True), ForeignKey("admins.id"), nullable=False)
    section_id = Column(UUID(as_uuid=True), ForeignKey("sections.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    admin   = relationship("Admin",   back_populates="admin_sections")
    section = relationship("Section", back_populates="admin_sections")

    def __repr__(self):
        return f"<AdminSection admin={self.admin_id} section={self.section_id}>"

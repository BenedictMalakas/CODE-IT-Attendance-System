from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from database.connection import Base


class QRToken(Base):
    __tablename__ = "qr_tokens"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id  = Column(UUID(as_uuid=True), ForeignKey("students.id"), nullable=False, unique=True)
    token       = Column(String(255), nullable=False, unique=True)  # UUID embedded in QR payload
    qr_path     = Column(String(500), nullable=False)               # path to saved QR PNG
    created_at  = Column(DateTime,    default=datetime.utcnow)

    student = relationship("Student", back_populates="qr_token")

    def __repr__(self):
        return f"<QRToken for student {self.student_id}>"

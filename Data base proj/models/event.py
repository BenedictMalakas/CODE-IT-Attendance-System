from sqlalchemy import Column, String, Date, Time, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from database.connection import Base


class Event(Base):
    __tablename__ = "events"

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name             = Column(String(150),  nullable=False)          # e.g. "Foundation Week Day 1"
    date             = Column(Date,         nullable=False)
    start_time       = Column(Time,         nullable=False)           # e.g. 08:00
    late_cutoff_mins = Column(Integer,      nullable=False, default=15)  # minutes after start = late
    created_by       = Column(UUID(as_uuid=True), ForeignKey("admins.id"), nullable=False)
    created_at       = Column(DateTime,     default=datetime.utcnow)

    created_by_admin = relationship("Admin",         back_populates="events")
    attendance_logs  = relationship("AttendanceLog", back_populates="event")

    def __repr__(self):
        return f"<Event '{self.name}' on {self.date} at {self.start_time}>"

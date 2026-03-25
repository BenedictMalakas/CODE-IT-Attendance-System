"""
seed.py — populate the database with realistic mock data for development.

Run with:
    python seed/seed.py

Requires the DB to be running and tables already created.
"""

import uuid
import random
from datetime import date, time, datetime, timedelta
from database.connection import SessionLocal, create_all_tables
from models.student import Student, StudentStatus
from models.admin import Admin
from models.event import Event
from models.qr_token import QRToken
from models.attendance_log import AttendanceLog, AttendanceStatus

# ─── fake bcrypt hash (dev only — never use plaintext in prod) ────────────────
FAKE_HASH = "$2b$12$FAKE_HASH_FOR_DEV_ONLY_DO_NOT_USE_IN_PRODUCTION"

SECTIONS = ["BSIT-1A", "BSIT-1B", "BSIT-2A", "BSIT-2B", "BSCS-1A"]

STUDENT_DATA = [
    ("Juan dela Cruz",      "BSIT-1A", "2024-0001"),
    ("Maria Santos",        "BSIT-1A", "2024-0002"),
    ("Carlos Reyes",        "BSIT-1B", "2024-0003"),
    ("Ana Gomez",           "BSIT-1B", "2024-0004"),
    ("Miguel Torres",       "BSIT-2A", "2024-0005"),
    ("Sofia Lim",           "BSIT-2A", "2024-0006"),
    ("Ramon Villanueva",    "BSIT-2B", "2024-0007"),
    ("Lea Aquino",          "BSIT-2B", "2024-0008"),
    ("Patrick Mendoza",     "BSCS-1A", "2024-0009"),
    ("Christine Flores",    "BSCS-1A", "2024-0010"),
    # pending (not yet approved)
    ("Jose Ramos",          "BSIT-1A", "2024-0011"),
    ("Grace Castillo",      "BSIT-2A", "2024-0012"),
    # rejected
    ("Dennis Bautista",     "BSCS-1A", "2024-0013"),
]

EVENT_DATA = [
    ("Foundation Week — Day 1",    date(2025, 9, 1),  time(8, 0),  15),
    ("Foundation Week — Day 2",    date(2025, 9, 2),  time(8, 0),  15),
    ("JS Seminar",                 date(2025, 9, 10), time(13, 0), 10),
    ("Career Talk",                date(2025, 9, 20), time(9, 0),  20),
    ("Acquaintance Party",         date(2025, 10, 5), time(17, 0), 30),
]


def seed():
    create_all_tables()
    db = SessionLocal()

    try:
        print("Seeding admins...")
        admin1 = Admin(
            id=uuid.uuid4(),
            name="Admin User",
            email="admin@school.edu",
            password_hash=FAKE_HASH,
            is_active=True,
        )
        admin2 = Admin(
            id=uuid.uuid4(),
            name="Super Admin",
            email="superadmin@school.edu",
            password_hash=FAKE_HASH,
            is_active=True,
        )
        db.add_all([admin1, admin2])
        db.flush()

        print("Seeding students...")
        students = []
        for i, (name, section, sid) in enumerate(STUDENT_DATA):
            if i < 10:
                status = StudentStatus.active
            elif i < 12:
                status = StudentStatus.pending
            else:
                status = StudentStatus.rejected

            s = Student(
                id=uuid.uuid4(),
                name=name,
                section=section,
                student_id=sid,
                password_hash=FAKE_HASH,
                id_photo_path=f"media/id_uploads/mock_{sid}.jpg",
                status=status,
                rejection_note="ID photo unclear" if status == StudentStatus.rejected else None,
            )
            students.append(s)

        db.add_all(students)
        db.flush()

        print("Seeding QR tokens for active students...")
        active_students = [s for s in students if s.status == StudentStatus.active]
        qr_tokens = []
        for s in active_students:
            token = str(uuid.uuid4())
            qt = QRToken(
                id=uuid.uuid4(),
                student_id=s.id,
                token=token,
                qr_path=f"media/qr_codes/{s.student_id}.png",
            )
            qr_tokens.append(qt)

        db.add_all(qr_tokens)
        db.flush()

        print("Seeding events...")
        events = []
        for name, ev_date, start_time, cutoff in EVENT_DATA:
            e = Event(
                id=uuid.uuid4(),
                name=name,
                date=ev_date,
                start_time=start_time,
                late_cutoff_mins=cutoff,
                created_by=admin1.id,
            )
            events.append(e)

        db.add_all(events)
        db.flush()

        print("Seeding attendance logs...")
        logs = []
        # Only log for past events (first 4) and active students
        past_events = events[:4]

        for event in past_events:
            cutoff_dt = datetime.combine(event.date, event.start_time) \
                        + timedelta(minutes=event.late_cutoff_mins)

            for s in active_students:
                roll = random.random()

                if roll < 0.70:       # 70% present
                    scan_time = datetime.combine(event.date, event.start_time) \
                                + timedelta(minutes=random.randint(0, event.late_cutoff_mins - 1))
                    status = AttendanceStatus.present
                elif roll < 0.85:     # 15% late
                    scan_time = cutoff_dt + timedelta(minutes=random.randint(1, 20))
                    status = AttendanceStatus.late
                else:                 # 15% absent
                    scan_time = None
                    status = AttendanceStatus.absent

                log = AttendanceLog(
                    id=uuid.uuid4(),
                    student_id=s.id,
                    event_id=event.id,
                    scanned_by=admin1.id if status != AttendanceStatus.absent else None,
                    status=status,
                    scanned_at=scan_time,
                )
                logs.append(log)

        db.add_all(logs)
        db.commit()

        print("\nDone! Summary:")
        print(f"  Admins:          2")
        print(f"  Students:        {len(students)} ({len(active_students)} active, 2 pending, 1 rejected)")
        print(f"  QR tokens:       {len(qr_tokens)}")
        print(f"  Events:          {len(events)}")
        print(f"  Attendance logs: {len(logs)}")

    except Exception as e:
        db.rollback()
        print(f"Seed failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()

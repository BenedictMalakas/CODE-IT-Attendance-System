"""
seed.py — Creates ONLY the Chairperson account.
No dummy students, events, or officers.

Run with:
    python seed.py
"""

import uuid
import hashlib
from database.connection import SessionLocal, create_all_tables
from models.admin import Admin, AdminRole


def hash_password(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def seed():
    create_all_tables()
    db = SessionLocal()

    try:
        # Check if chairperson already exists
        existing = db.query(Admin).filter_by(role=AdminRole.chairperson).first()
        if existing:
            print(f"Chairperson already exists: {existing.email}")
            print("Skipping seed.")
            return

        print("Creating Chairperson account...")
        chairperson = Admin(
            id=uuid.uuid4(),
            name="Chairperson Admin",
            email="chair@school.edu",
            password_hash=hash_password("chair123"),
            role=AdminRole.chairperson,
            is_active=True,
            force_password_change=False,  # Chairperson does not need to change password
        )
        db.add(chairperson)
        db.commit()

        print("\nDone! Summary:")
        print(f"  Chairperson: chair@school.edu / chair123")
        print(f"  Login at: /admin-panel/cp-x9k7m2v4-ctrl/")
        print()
        print("All other accounts (officers, reps, students, events)")
        print("should be created through the Chairperson dashboard.")

    except Exception as e:
        db.rollback()
        print(f"Seed failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()

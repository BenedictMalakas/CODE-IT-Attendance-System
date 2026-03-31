# main.py
from database.connection import Base, engine, SessionLocal, create_all_tables
from models import admin, student, event, attendance_log, qr_token
from datetime import date, time, datetime, timedelta
import uuid

# 1️⃣ Create all tables
create_all_tables()
print("✅ All tables created successfully.")


# ------------------------
# 2️⃣ Test Data Functions
# ------------------------
def add_test_admin():
    session = SessionLocal()
    try:
        new_admin = admin.Admin(
            name="Admin User",
            email="admin@example.com",
            password_hash="hashedpassword"
        )
        session.add(new_admin)
        session.commit()
        print("✅ Test Admin added.")
    except Exception as e:
        session.rollback()
        print("❌ Error adding admin:", e)
    finally:
        session.close()


def add_test_student():
    session = SessionLocal()
    try:
        new_student = student.Student(
            name="John Benedict",
            section="A",
            student_id="2026-0001",
            password_hash="hashedpassword",
            id_photo_path="path/to/photo.png",
        )
        session.add(new_student)
        session.commit()
        print("✅ Test Student added.")
    except Exception as e:
        session.rollback()
        print("❌ Error adding student:", e)
    finally:
        session.close()


def add_test_event(admin_id=None):
    session = SessionLocal()
    try:
        if not admin_id:
            admin_obj = session.query(admin.Admin).first()
            if not admin_obj:
                print("❌ No admin found. Add admin first.")
                return
            admin_id = admin_obj.id
        new_event = event.Event(
            name="Sample Event",
            date=date.today(),
            start_time=time(hour=8, minute=0),
            late_cutoff_mins=15,
            created_by=admin_id
        )
        session.add(new_event)
        session.commit()
        print("✅ Test Event added.")
    except Exception as e:
        session.rollback()
        print("❌ Error adding event:", e)
    finally:
        session.close()


def add_test_qr(student_id=None):
    session = SessionLocal()
    try:
        if not student_id:
            student_obj = session.query(student.Student).first()
            if not student_obj:
                print("❌ No student found. Add student first.")
                return
            student_id = student_obj.id
        new_qr = qr_token.QRToken(
            student_id=student_id,
            token=str(uuid.uuid4()),
            qr_path="path/to/qr.png"
        )
        session.add(new_qr)
        session.commit()
        print("✅ Test QR Token added.")
    except Exception as e:
        session.rollback()
        print("❌ Error adding QR token:", e)
    finally:
        session.close()


def add_test_attendance():
    session = SessionLocal()
    try:
        student_obj = session.query(student.Student).first()
        event_obj   = session.query(event.Event).first()
        admin_obj   = session.query(admin.Admin).first()
        if not (student_obj and event_obj):
            print("❌ Need at least one student and one event.")
            return
        new_log = attendance_log.AttendanceLog(
            student_id=student_obj.id,
            event_id=event_obj.id,
            scanned_by=admin_obj.id if admin_obj else None,
            status="present",
            scanned_at=None
        )
        session.add(new_log)
        session.commit()
        print("✅ Test Attendance Log added.")
    except Exception as e:
        session.rollback()
        print("❌ Error adding attendance log:", e)
    finally:
        session.close()


# ------------------------
# 3️⃣ QR Scanning Function
# ------------------------
def scan_qr_for_attendance():
    session = SessionLocal()
    try:
        qr_input = input("Scan QR token: ").strip()
        qr_obj = session.query(qr_token.QRToken).filter_by(token=qr_input).first()
        if not qr_obj:
            print("❌ Invalid QR token.")
            return
        student_obj = qr_obj.student

        event_obj = session.query(event.Event).order_by(event.Event.date.desc()).first()
        if not event_obj:
            print("❌ No event found. Add an event first.")
            return

        existing_log = session.query(attendance_log.AttendanceLog).filter_by(
            student_id=student_obj.id,
            event_id=event_obj.id
        ).first()
        if existing_log:
            print("⚠ Student already scanned for this event.")
            return

        now = datetime.now()
        event_start = datetime.combine(event_obj.date, event_obj.start_time)
        late_cutoff = event_start + timedelta(minutes=event_obj.late_cutoff_mins)
        if now <= event_start:
            status = "present"
        elif now <= late_cutoff:
            status = "late"
        else:
            status = "absent"

        admin_obj = session.query(admin.Admin).first()
        new_log = attendance_log.AttendanceLog(
            student_id=student_obj.id,
            event_id=event_obj.id,
            scanned_by=admin_obj.id if admin_obj else None,
            status=status,
            scanned_at=now
        )
        session.add(new_log)
        session.commit()
        print(f"✅ Attendance recorded: {student_obj.name} is {status.upper()} for {event_obj.name}")

    except Exception as e:
        session.rollback()
        print("❌ Error recording attendance:", e)
    finally:
        session.close()


# ------------------------
# 4️⃣ Main Menu
# ------------------------
def main():
    while True:
        print("\n=== Attendance Tracker Menu ===")
        print("1. Add Test Admin")
        print("2. Add Test Student")
        print("3. Add Test Event")
        print("4. Add Test QR Token")
        print("5. Add Test Attendance Log")
        print("6. Exit")
        print("7. Scan QR for Attendance")  # new QR scanning option
        choice = input("Enter choice: ")
        if choice == "1":
            add_test_admin()
        elif choice == "2":
            add_test_student()
        elif choice == "3":
            add_test_event()
        elif choice == "4":
            add_test_qr()
        elif choice == "5":
            add_test_attendance()
        elif choice == "6":
            print("Exiting...")
            break
        elif choice == "7":
            scan_qr_for_attendance()
        else:
            print("❌ Invalid choice. Try again.")


if __name__ == "__main__":
    main()
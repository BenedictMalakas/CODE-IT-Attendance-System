from database.connection import SessionLocal
from models import admin, student, event, qr_token, attendance_log

session = SessionLocal()

# Check Admins
admins = session.query(admin.Admin).all()
print("Admins:", admins)

# Check Students
students = session.query(student.Student).all()
print("Students:", students)

# Check Events
events = session.query(event.Event).all()
print("Events:", events)

# Check QR Tokens
qrs = session.query(qr_token.QRToken).all()
print("QR Tokens:", qrs)

# Check Attendance Logs
logs = session.query(attendance_log.AttendanceLog).all()
print("Attendance Logs:", logs)

session.close()
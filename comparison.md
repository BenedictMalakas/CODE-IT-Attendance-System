# CODE-IT Attendance System - Complete Specification for Comparison & Restoration

This document provides an exhaustive inventory of every feature, function, UI element, validation, and technical detail in the original CODE-IT Attendance System. Use this to identify what is missing in your prototype implementation.

## 1. STUDENT PORTAL - COMPLETE FEATURE SPECIFICATION

### 1.1 Login Page (/student/login/)

#### URL & Routing
- Route: `/student/login/` (student_portal:login)
- Template: `student_portal/templates/student_portal/login.html`
- View: `student_portal.views.login_view`
- Method: GET (display form), POST (process login)
- Redirect if already logged in: `student_portal:dashboard`

#### Form Fields
- **Student ID Input**
  - Type: TextInput
  - Name: `student_id`
  - Placeholder: `e.g. 24-0001`
  - Autocomplete: `username`
  - Required: Yes
  - CSS Class: `form-control`
  - Label: "Student ID"

- **Password Input**
  - Type: PasswordInput
  - Name: `password`
  - Placeholder: `Your password`
  - Autocomplete: `current-password`
  - Required: Yes
  - CSS Class: `form-control`
  - Label: "Password"

#### Buttons
- **Login Button**
  - Type: Submit
  - Text: "Login"
  - Class: `btn btn-primary`
  - Action: POST to same view

- **Register Link**
  - Text: "Don't have an account? Register here"
  - URL: `student_portal:register`
  - Type: Hyperlink

#### Security Features
- IP-based rate limiting: `get_client_ip(request)` → check `is_ip_locked(ip)` → if True, show error message "Too many failed attempts. Try again after 15 minutes." and display form without processing
- Failed attempt tracking: `track_login_failure(ip)` increments cache counter with 15-min expiry
- Successful login: `clear_login_failures(ip)` clears counter
- Session fixation: `request.session.cycle_key()` rotates session ID

#### Validation & Logic
1. Check if already logged in: `get_current_student(request)` → if exists, redirect to dashboard
2. If stale session exists: pop keys `student_id`, `student_name`, cycle_key()
3. Check IP lockout: if `is_ip_locked(ip)`, display form without processing
4. Form validation: Django form validates required fields
5. Database lookup: `Student.objects.get(student_id=student_id_val)`
6. Password verification: `verify_password(password, student.password_hash)`
7. Hash migration: if not `student.password_hash.startswith('pbkdf2_')`, run `make_password(password)`, save
8. Status checks:
   - If `student.status == 'pending'`: show warning "Your account is still pending approval."
   - If `student.status == 'rejected'`: show error "Your registration was rejected: {student.rejection_note}" (default: "No reason provided.")
   - If `student.status == 'active'`: create session
9. Session creation:
   - `request.session['student_id'] = str(student.id)`
   - `request.session['student_name'] = student.name` (computed: first_name + last_name)
   - `request.session.cycle_key()`
   - Redirect to `student_portal:dashboard`
10. Failed login: show error "Invalid Student ID or password." and call `track_login_failure(ip)`

#### Error Messages
- "Too many failed attempts. Try again after 15 minutes."
- "Invalid Student ID or password."
- "Your account is still pending approval."
- "Your registration was rejected: [reason]"

### 1.2 Register Page (/student/register/)

#### URL & Routing
- Route: `/student/register/` (student_portal:register)
- Template: `student_portal/templates/student_portal/register.html`
- View: `student_portal.views.register_view`
- Method: GET (display form), POST (process registration)
- Redirect if already logged in: `student_portal:dashboard`

#### Form Fields

- **First Name Input**
  - Type: TextInput
  - Name: `first_name`
  - Max length: 50
  - Placeholder: `e.g. Juan`
  - Required: Yes
  - CSS Class: `form-control`
  - Label: "First Name"
  - Validation: Regex `^[A-Za-z\s]+$` (letters and spaces only)
  - Error message: "First name must contain letters only. No special characters or numbers."

- **Last Name Input**
  - Type: TextInput
  - Name: `last_name`
  - Max length: 50
  - Placeholder: `e.g. Dela Cruz`
  - Required: Yes
  - CSS Class: `form-control`
  - Label: "Last Name"
  - Validation: Regex `^[A-Za-z\s]+$`
  - Error message: "Last name must contain letters only. No special characters or numbers."

- **Student ID Input**
  - Type: TextInput
  - Name: `student_id`
  - Max length: 50
  - Placeholder: `e.g. 24-0001`
  - Maxlength (HTML): `7`
  - Required: Yes
  - CSS Class: `form-control`
  - Label: "Student ID"
  - Validation: Regex `^\d{2}-\d{4}$` (format XX-XXXX)
  - Uniqueness check: `Student.objects.filter(student_id=sid).exists()`
  - Error messages:
    - "Student ID must be in the format xx-xxxx (e.g. 24-0001)."
    - "A student with that ID already exists."

- **Year Level Dropdown**
  - Type: Select
  - Name: `year_level`
  - CSS Class: `form-select`
  - ID: `id_year_level`
  - Required: Yes
  - Label: "Year Level"
  - Options:
    - `''` → "— Select Year Level —"
    - `'1'` → "1st Year"
    - `'2'` → "2nd Year"
    - `'3'` → "3rd Year"
    - `'4'` → "4th Year"
  - Trigger: onchange → JavaScript call `/api/sections/?year=[value]` to populate Section dropdown

- **Section Dropdown**
  - Type: Select
  - Name: `section`
  - CSS Class: `form-select`
  - ID: `id_section`
  - Disabled (HTML): `disabled="disabled"`
  - Required: Yes
  - Label: "Section"
  - Populated via AJAX from year_level dropdown
  - Options: Dynamically loaded from sections_by_year_api

- **Email Input**
  - Type: EmailInput
  - Name: `email`
  - Placeholder: `e.g. juan@gmail.com`
  - Required: Yes
  - CSS Class: `form-control`
  - Label: "Email Address"
  - Validation: 
    - Format: Regex `^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$`
    - Provider whitelist: @gmail.com, @outlook.com, @yahoo.com, @hotmail.com, @icloud.com, @protonmail.com, .edu, .edu.ph
    - Uniqueness: `Student.objects.filter(email=email).exists()`
  - Error messages:
    - "Please enter a valid email address."
    - "Please use a recognized email provider (Gmail, Outlook, Yahoo, etc.) or an .edu address."
    - "An account with this email already exists."

- **Password Input**
  - Type: PasswordInput
  - Name: `password`
  - Min length: 8
  - Placeholder: `Min 8 chars, 1 special char`
  - Required: Yes
  - CSS Class: `form-control`
  - Label: "Password"
  - Validation:
    - Min 8 characters
    - Regex `[!@#$%^&*(),.?":{}|<>]` (at least one special char)
  - Error messages:
    - "Password must be at least 8 characters long."
    - "Password must contain at least one special character."

- **Confirm Password Input**
  - Type: PasswordInput
  - Name: `confirm_password`
  - Placeholder: `Re-enter password`
  - Required: Yes
  - CSS Class: `form-control`
  - Label: "Confirm Password"
  - Validation: Must match `password`
  - Error message: "Passwords do not match."

- **ID Photo Upload**
  - Type: FileInput
  - Name: `id_photo`
  - Accept: `.png, .jpg, .jpeg, .webp`
  - Required: No
  - Label: "ID Photo"
  - Validation:
    - File extension in ['png', 'jpg', 'jpeg', 'webp']
    - Max file size: 10MB (middleware)
  - Error message: "Invalid file type. Only PNG, JPG, and WebP are allowed."
  - Storage: `/media/id_photos/id_[safe_student_id].[ext]`
    - Safe: Replace `-` with `_`
    - Check if exists: delete old, save new
    - DB: Stored as `/media/[saved_path]`

#### Form Processing
1. Fetch sections for display: `get_sorted_sections()`
2. Check if already logged in: `request.session.get('student_id')` → if yes, redirect to dashboard
3. Re-enable section field on POST: `form.fields['section'].widget.attrs.pop('disabled', None)`
4. Extract cleaned data: `student_id`, `section`, `year_level`, `first_name`, `last_name`, `email`, `password`, `confirm_password`
5. Validate student_id uniqueness: `Student.objects.filter(student_id=sid).exists()`
6. Fetch section: `Section.objects.get(id=section_id)` (error if DoesNotExist)
7. Handle file upload (if provided):
   - Extract extension: `photo.name.split('.')[-1].lower()`
   - Validate: must be in ['png', 'jpg', 'jpeg', 'webp']
   - Generate filename: `id_photos/id_[safe_id].[ext]`
   - Delete if exists: `default_storage.delete(filename)`
   - Save: `default_storage.save(filename, photo)` → returns saved_path
   - Set: `id_photo_path = f'/media/{saved_path}'`
8. Create Student with status='pending'
9. Display success message and redirect to login

#### Buttons
- **Submit Button**: "Register"
- **Login Link**: "Already have an account? Login here"

#### Context Variables
- `form`: StudentRegisterForm instance
- `sections`: get_sorted_sections()

### 1.3 Dashboard (/student/)

#### URL & Routing
- Route: `/` (student_portal:dashboard)
- Template: `student_portal/templates/student_portal/dashboard.html`
- View: `student_portal.views.dashboard_view`
- Method: GET
- Requires: `@student_required` decorator

#### Data Fetched
- Current student: `get_current_student(request)` (select_related('section'))
- Today's date: `dj_timezone.now().date()`
- Attendance logs: `AttendanceLog.objects.filter(student=student).select_related('event')`
- Upcoming events: `Event.objects.filter(date__gte=today, status='active').order_by('date', 'start_time')[:5]`
- QR token: `QRToken.objects.filter(student=student).first()`

#### Summary Cards
- **Total Present**: Count of present logs
- **Total Late**: Count of late logs
- **Total Absent**: Count of absent logs
- **Total Records**: Count of all logs

#### QR Token Display
- Display QR image if exists: `qr_token.qr_path`
- Message: "Show this QR code at events to record your attendance"
- If no QR: "Your QR code will be generated once your registration is approved."

#### Upcoming Events Section
- Max: 5 events
- Columns: name, date, start_time, status

#### Context Variables
- `student`, `qr_token`, `upcoming_events`, `total_present`, `total_late`, `total_absent`, `total_records`

### 1.4 My QR Page (/student/my-qr/)

#### URL & Routing
- Route: `/my-qr/` (student_portal:my_qr)
- Requires: `@student_required` decorator

#### Display
- Student info: name, student ID, section, year level
- QR image: Large display of `qr_token.qr_path`
- Instructions: "Show this QR code at events to record your attendance."

### 1.5 My Attendance Page (/student/attendance/)

#### URL & Routing
- Route: `/attendance/` (student_portal:attendance)
- Requires: `@student_required` decorator
- Pagination: 25 per page

#### Data
- Logs: Ordered by event date DESC, then scanned_at DESC
- Summary cards: Present, Late, Absent counts

#### Attendance Table
- Columns: Event Name, Date, Status (badge), Scanned At
- Row styling: Color-coded by status
- Pagination controls with query preservation

#### Context Variables
- `student`, `logs`, `page_obj`, `present`, `late`, `absent`, `pagination_query`

### 1.6 Profile Page (/student/profile/)

#### URL & Routing
- Route: `/profile/` (student_portal:profile)
- Requires: `@student_required` decorator

#### GET Response
- Student info: name, student ID, email, section, year level
- Profile picture section with upload form
- Password change section

#### POST - Upload Photo Action
1. Validate: `action == 'upload_photo'` and file exists
2. Check extension: must be in ['png', 'jpg', 'jpeg', 'webp']
3. Generate filename: `id_photos/profile_[student.id]_[timestamp].[ext]`
4. Delete old if exists (silent fail)
5. Save and update: `student.id_photo_path = f'/media/{saved_path}'`
6. Message: "Profile picture updated successfully."

#### POST - Change Password Action
1. Validate: password min 8 chars, 1 special char, match confirm
2. Hash and save: `student.password_hash = make_password(new_pw)`
3. Message: "Password updated successfully."

#### Error Messages
- "Invalid file type. Only PNG, JPG, and WebP are allowed."
- "Please enter a new password."
- "Password must be at least 8 characters."
- "Password must contain at least one special character."
- "Passwords do not match."

### 1.7 Logout (/student/logout/)

#### URL & Routing
- Route: `/logout/` (student_portal:logout)
- View: `student_portal.views.logout_view`

#### Logic
1. Flush session: `request.session.flush()`
2. Redirect to: `student_portal:login`

---

## 2. ADMIN PANEL - CORE FEATURES

### 2.1 Admin Login (/admin-panel/login/)

#### Form Fields
- **Email Input**: EmailInput, class form-control
- **Password Input**: PasswordInput, class form-control
- **Role Dropdown**: Select with options 'vits' and 'representative' (excludes chairperson)

#### Security
- IP rate limiting: 5 failed attempts = 15 minute lockout
- Session rotation: cycle_key() on login
- Hash migration: Upgrade legacy hashes on successful login
- Role validation: Must match selected role

#### Logic
1. Reject chairperson login at this endpoint
2. Verify IP not locked
3. Lookup admin: `Admin.objects.get(email=email, is_active=True)`
4. Verify password
5. Create session with: `admin_id`, `admin_name`, `admin_role`, `force_password_change`
6. Redirect to dashboard (auto-routes by role)

#### Error Messages
- "Too many failed attempts. Try again after 15 minutes."
- "Invalid email or password."
- "This account is registered as a [role]. Please select the correct role."

### 2.2 Chairperson Hidden Login (/chair_adminlogin/cp-x9k7m2v4-ctrl/)

#### URL & Routing
- Hidden endpoint at `/chair_adminlogin/cp-x9k7m2v4-ctrl/`
- Separate from regular admin login
- Only accepts role='chairperson'

#### Logic
1. Lookup: `Admin.objects.get(email=email, is_active=True, role='chairperson')`
2. Verify password
3. Create session
4. Redirect to: `admin_panel:chairperson_dashboard`

#### Error Messages
- "Too many failed attempts. Try again after 15 minutes."
- "Invalid credentials."

### 2.3 Force Password Change

#### Triggering
- If `request.session.get('force_password_change') == True`
- Modal on first login

#### Form Fields
- **New Password**: PasswordInput, min 8 chars, 1 special char
- **Confirm Password**: PasswordInput, must match

#### Logic
1. Validate: min 8 chars, 1 special char regex `[!@#$%^&*(),.?":{}|<>]`, match confirm
2. Hash and save: `admin.password_hash = make_password(new_pw)`
3. Clear flag: `admin.force_password_change = False`
4. Update session: `request.session['force_password_change'] = False`
5. Redirect to: `admin_panel:dashboard`

#### Error Messages
- "Password must be at least 8 characters."
- "Password must contain at least one special character."
- "Passwords do not match."

### 2.4 Admin Dashboard (Auto-Routes)

#### Routing Logic
1. Call `auto_update_event_statuses()`
2. Get role from session
3. Route by role:
   - 'chairperson' → chairperson_dashboard
   - 'representative' → _rep_dashboard
   - 'vits' → _vits_dashboard

### 2.5 VITS Officer Dashboard

#### Data Fetched
- Total events: Event.objects.count()
- Total active students: Student.objects.filter(status='active').count()
- Pending students: Student.objects.filter(status='pending').count()
- Total logs: AttendanceLog.objects.count()
- Today's events: Events for current date
- Recent events: Last 5 events (ORDER BY -date, -start_time)
- Active events: All events with status='active'
- Section tiles: Attendance data per section for selected event

#### Summary Cards
- Total Events
- Total Active Students
- Pending Students
- Total Attendance Logs

#### Sections
- Today's Events list
- Recent Events list (5)
- Active Events selector dropdown
- Section tiles grid (attendance overview by section)

#### Navigation
- Create Event button
- View Events button
- Student Management button
- Scanner link (if event selected)

### 2.6 Representative Dashboard

#### Restrictions
- All data filtered by representative's assigned sections via AdminSection lookup
- Only view events for their sections
- Only manage students in their sections
- Only manage admins (other reps) assigned to their sections

#### Data
- Filtered to: Section.objects.filter(admin_sections__admin=rep_admin)
- Events in those sections
- Students in those sections
- Attendance logs for students in those sections

#### Sections
- Same layout as VITS dashboard but filtered

### 2.7 Chairperson Dashboard

#### Data
- Full system access (no filters)
- All events, all students, all admins, all logs

#### Sections
- Complete system overview
- All management capabilities
- Activity logs viewer
- Excel export access

### 2.8 Events Management

#### URL Routes
- List: `/admin-panel/events/` (admin_panel:events)
- Create: `/admin-panel/events/create/` (admin_panel:create_event)
- Edit: `/admin-panel/events/[id]/edit/` (admin_panel:edit_event)
- Delete: `/admin-panel/events/[id]/delete/` (admin_panel:delete_event)
- Start: `/admin-panel/events/[id]/start/` (admin_panel:start_event)
- End: `/admin-panel/events/[id]/end/` (admin_panel:end_event)
- Close: `/admin-panel/events/[id]/close/` (admin_panel:close_event) - Chairperson only
- Extend Grace: `/admin-panel/events/[id]/extend-grace/` (admin_panel:extend_grace_event)
- Scanner: `/admin-panel/events/[id]/scanner/` (admin_panel:scanner)

#### Create Event Form
- **Name**: CharField, max 150
- **Date**: DateField, no past dates, no past times on today
- **Start Time**: TimeField, optional
- **End Time**: TimeField, optional, must be > start_time if provided
- **Late Cutoff (mins)**: IntegerField, default 15

#### Validation
- No past dates
- No past times on today's date
- If end_time provided, must be greater than start_time
- Name required

#### Event Lifecycle
- **pending**: Initial status
- **active**: After start_event
- **ended**: After end_event (enables check-out)
- **closed**: Chairperson-only (locks event, final comparison available)

#### Event Actions

**Start Event**
1. Requires status='pending'
2. Set status='active'
3. Auto-stamp start_time with current time if blank
4. Record in activity log

**End Event**
1. Requires status='active'
2. Set status='ended'
3. Enable check-out mode for scanner
4. Record in activity log

**Close Event**
1. Chairperson-only
2. Requires status='ended'
3. Set status='closed'
4. Lock all scanning
5. Enable final comparison view
6. Record in activity log

**Extend Grace Period**
1. Active events only
2. Add 15 minutes to late_cutoff_mins
3. Record in activity log

**Delete Event**
1. Only if status='pending'
2. Cascade delete to AttendanceLogs
3. Record in activity log

### 2.9 QR Scanner (/admin-panel/events/[id]/scanner/)

#### Display Logic
- Status pending: "Event not started"
- Status active: Show scanner interface
- Status ended: Show scanner with check-out mode
- Status closed: "Event closed - no scanning allowed"

#### Scanner Interface
- QR input field (auto-focus)
- Camera/upload option (if browser supports)
- Manual student ID field (fallback)
- Current event name and status
- Real-time attendance count display

#### Scan Processing (POST to /api/events/[id]/scan-qr/)
1. Parse QR token
2. Lookup QRToken and Student
3. Get current event
4. Validate event status:
   - pending: Reject "Event not started"
   - active: Check-in mode
   - ended: Check-out mode
   - closed: Reject "Event closed"
5. Check student status: active only
6. Check if student already scanned:
   - If pending/active + already logged: "Already checked in"
   - If ended + not logged: "Not checked in for this event"
   - If ended + already logged: Check-out
7. Log attendance:
   - scanned_at = current time (check-in)
   - scanned_out_at = current time (check-out)
8. Determine status:
   - Before late_cutoff_mins: present
   - After late_cutoff_mins: late
9. Response: JSON {success, message, status}

### 2.10 Set Expected Students

#### URL
- Route: `/admin-panel/events/[id]/expected-students/` (admin_panel:set_expected_students)

#### Logic
1. Get all students in event's section(s)
2. Show checklist of students
3. Mark selected as "absent" pre-emptively
4. Prevent removal of already-scanned students
5. Save: Create AttendanceLog with status='absent' for unchecked students

### 2.11 Attendance View

#### URL
- Route: `/admin-panel/events/[id]/attendance/` (admin_panel:attendance)

#### Overviews
1. **Check-In Overview** (all events)
   - Cards showing: Present count, Late count, Absent count
   - Tiles by section showing attendance breakdown

2. **Check-Out Overview** (status='ended' only)
   - Cards: Checked out count, Not checked out count
   - Tiles by section

3. **Final Comparison** (status='closed' only)
   - Compare check-in vs check-out
   - Duration calculations
   - Discrepancies

#### Attendance Table
- Paginated: 25 per page
- Columns: Student ID, Name, Status, Scanned At, Scanned Out At
- Row colors: present=green, late=yellow, absent=red
- Filters: Status dropdown
- Export button: Excel download

### 2.12 Excel Export

#### URL
- Route: `/admin-panel/events/[id]/export/` (admin_panel:export_attendance)

#### File Details
- Filename: `Attendance_[event_name]_[date].xlsx`
- Columns: Student ID, Name, Year, Section, Status, Scanned At, Scanned Out At
- Formatting:
  - Header row: Merged cells, bold, centered
  - Rows colored by status: present=light green, late=light yellow, absent=light red
  - Timestamps formatted: YYYY-MM-DD HH:MM:SS
  - Column widths auto-adjusted

### 2.13 Student Management

#### URL
- Route: `/admin-panel/students/` (admin_panel:students)

#### Features
- Paginated table: 25 per page
- Filters: Status (pending/active/rejected), Section
- Columns: ID, Name, Email, Status, Section, Actions
- Action buttons: Approve, Reject, Generate QR, Revoke QR, Delete
- Bulk actions: Approve multiple students

#### Sorting
- Default: Most recent first
- Filterable by status and section

#### Bulk Approve
- Select multiple pending students
- One click → all approved with QRs generated in single transaction

### 2.14 Student Approve

#### URL
- Route: `/admin-panel/students/[id]/approve/` (admin_panel:approve_student)

#### Logic
1. Set status='active'
2. Check if QRToken exists:
   - If not: Generate new token and QR PNG
   - If exists: Use existing
3. Save QRToken
4. Generate QR image: `qr.make(token)` → PNG file
5. Save: `/media/qr_codes/[student_id].png`
6. Create QRToken: token + qr_path
7. Email QR to student with PNG attachment
8. Record activity log
9. Message: "Student approved and QR code generated"

### 2.15 Student Reject

#### URL
- Route: `/admin-panel/students/[id]/reject/` (admin_panel:reject_student)

#### Form
- **Rejection Note**: TextField, optional
- Default if empty: "No reason provided."

#### Logic
1. Set status='rejected'
2. Store rejection_note
3. Save
4. Message: "Student rejected"
5. Record activity log

### 2.16 Student Delete

#### URL
- Route: `/admin-panel/students/[id]/delete/` (admin_panel:delete_student)

#### Logic
1. Check: Only if status='pending'
2. Delete cascade: AttendanceLog, QRToken
3. Delete Student
4. Message: "Student deleted"
5. Record activity log

### 2.17 Generate/Regenerate QR

#### URL
- Route: `/admin-panel/students/[id]/generate-qr/` (admin_panel:generate_qr)

#### Logic
1. Lookup or create QRToken
2. Generate token: `secrets.token_urlsafe(32)`
3. Create QR image
4. Save: `/media/qr_codes/[student_id].png`
5. Store QRToken
6. Email QR to student
7. Message: "QR code generated and emailed"

### 2.18 Revoke/Regenerate QR

#### URL
- Route: `/admin-panel/students/[id]/revoke-qr/` (admin_panel:revoke_qr)

#### Logic
1. Delete old QRToken
2. Generate new token: `secrets.token_urlsafe(32)`
3. Create new QR image
4. Save with new filename
5. Create new QRToken
6. Email new QR
7. Message: "QR code revoked and new one generated"
8. Record activity log

### 2.19 Sections Management

#### URL
- Route: `/admin-panel/sections/` (admin_panel:sections_manage)

#### Features
- List of all sections
- Create new section form:
  - Name: Auto-generated as "BSIT [year]-[i]"
  - Year Level: Dropdown 1-4
- Delete button per section
- Edit capability

#### Auto-Generation Logic
1. Get year level
2. Find max index for that year
3. Generate name: `f"BSIT {year}-{index+1}"`

#### Sorting
- Sorted numerically by year and index
- Example: BSIT 1-1, BSIT 1-2, ..., BSIT 2-1, BSIT 2-2, ...

### 2.20 Admin Management

#### URL
- Route: `/admin-panel/admins/` (admin_panel:admins_manage)

#### Features
- List of all admins
- Create new admin form:
  - Name: CharField
  - Email: EmailField, unique
  - Role: Select (vits, representative)
  - Sections (if representative): Multi-select
- Generated password: `secrets.token_urlsafe(12)`
- Force password change flag = True
- Email credentials to new admin
- Display generated password once (copy option)

#### Logic
1. Generate random password: `secrets.token_urlsafe(12)`
2. Hash: `make_password(generated_password)`
3. Create Admin: role, force_password_change=True
4. If representative: Create AdminSection mappings
5. Email: Subject line includes generated password
6. Message: "Admin created. Password emailed."
7. Record activity log

### 2.21 Activity Logs

#### URL
- Route: `/admin-panel/activity-logs/` (admin_panel:activity_logs)

#### Features
- Paginated table: 25 per page
- Columns: Timestamp, Admin, Action, Target, Description
- Filters:
  - Action type dropdown (distinct values)
  - Admin dropdown
  - Date range picker
- Sort: Most recent first
- Clear logs button (Chairperson-only)

#### Clear Activity Logs
1. Delete all ActivityLog records
2. Create new ActivityLog entry: action='LOGS_CLEARED', description='Admin cleared all activity logs'
3. Record who cleared them
4. Message: "All activity logs cleared"

---

## 3. SHARED FEATURES & UTILITIES

### 3.1 Decorators

**@student_required**
- Checks: `request.session.get('student_id')`
- Redirect: `student_portal:login`

**@admin_required**
- Checks: `request.session.get('admin_id')`
- Redirect: `admin_panel:login`

### 3.2 View Architecture
- Monolithic `views.py` used in both applications
- Shared context processors for global variables (e.g. notifications)
- Extensively uses Django messages framework

### 3.3 Database Models

**Admin**
- Fields: id, name, email, password_hash, role, force_password_change, is_active

**Section**
- Fields: id, name, year_level

**AdminSection** (Mapping)
- Fields: id, admin (FK), section (FK)

**Event**
- Fields: id, name, date, start_time, end_time, status, late_cutoff_mins

**EventSection** (Mapping)
- Fields: id, event (FK), section (FK)

**Student**
- Fields: id, first_name, last_name, student_id, section (FK), email, password_hash, id_photo_path, status, rejection_note

**QRToken**
- Fields: id, student (FK), token, qr_path

**AttendanceLog**
- Fields: id, event (FK), student (FK), status, scanned_at, scanned_out_at, scanned_by (FK Admin)

**ActivityLog**
- Fields: id, admin (FK), action, target, description, timestamp

### 3.4 Media Handling
- `media/id_photos/`: Uploaded student IDs
- `media/qr_codes/`: Generated QR PNGs
- Handled safely via Django's default_storage to prevent naming collisions

---
*End of Complete Specification*

# CODE-IT System: Technical Analysis & Defense Guide

This document provides a comprehensive, line-by-line explanation of the core source code for the **CODE-IT Attendance System**, as presented in the system documentation. It is designed to assist in technical understanding and defense preparation.

---

## 1. CHAIRMAN CODE SNIPPETS

### A. Login Authentication & Security
These functions handle the entry point of the system and protect against automated attacks.

```python
# Helper to securely hash a raw string
def hash_password(raw: str) -> str:
    # return make_password(raw)
    # Explanation: Calls Django's internal hashing function. 
    # It adds a unique salt and uses the PBKDF2-SHA256 algorithm by default.
    return make_password(raw)

# Helper to verify if user input matches the stored hash
def verify_password(raw: str, stored: str) -> bool:
    # if not stored: return False
    # Explanation: Safety check. If the database field is null or empty, access is denied.
    if not stored: return False
    
    # if stored.startswith('pbkdf2_'):
    # Explanation: Identifies if the password was hashed using the modern Django format.
    if stored.startswith('pbkdf2_'):
        # return check_password(raw, stored)
        # Explanation: Uses Django's secure constant-time comparison to prevent timing attacks.
        return check_password(raw, stored)
    
    # return hashlib.sha256(raw.encode()).hexdigest() == stored
    # Explanation: Fallback for old accounts. Hashes raw input with SHA256 and compares manually.
    return hashlib.sha256(raw.encode()).hexdigest() == stored

# Brute-force protection: Checks if an IP is blocked
def is_ip_locked(ip):
    # return (cache.get(f'login_attempts_{ip}') or 0) >= 5
    # Explanation: Checks the system cache for a failure counter tied to the visitor's IP. 
    # If the count is 5 or higher, the function returns True, signaling a lockout.
    return (cache.get(f'login_attempts_{ip}') or 0) >= 5

# Increments the failure count in the cache
def track_login_failure(ip):
    # key = f'login_attempts_{ip}'
    # Explanation: Generates a specific key for this IP address to store in memory.
    key = f'login_attempts_{ip}'
    
    # current = cache.get(key, 0)
    # Explanation: Retrieves the current number of failures or defaults to 0.
    current = cache.get(key, 0)
    
    # cache.set(key, current + 1, timeout=900)
    # Explanation: Increments the count and sets a 15-minute (900 seconds) expiry timer.
    cache.set(key, current + 1, timeout=900)
```

### B. Event Management Logic
Handles the lifecycle of school events and section-based targeting.

```python
def event_create_view(request):
    # event = form.save(commit=False)
    # Explanation: Creates a model instance from the form data but doesn't write to DB yet.
    event = form.save(commit=False)
    
    # event.id = uuid.uuid4()
    # Explanation: Generates a random, 36-character unique ID to prevent URL guessing.
    event.id = uuid.uuid4()
    
    # event.created_by = get_current_admin(request)
    # Explanation: Retrieves the current session user to record who created the event.
    event.created_by = get_current_admin(request)
    
    # event.save()
    # Explanation: Commits the initial event data to the database.
    event.save()

    # Section Assignment Logic
    choice = form.cleaned_data.get('expected_year_section', '')
    if choice.startswith('year_'):
        # year_level = int(choice.replace('year_', ''))
        # Explanation: Extracts the number (1, 2, 3, or 4) from the dropdown choice.
        year_level = int(choice.replace('year_', ''))
        
        # event.expected_sections.set(Section.objects.filter(year_level=year_level))
        # Explanation: Bulk assigns every section belonging to that specific year level.
        event.expected_sections.set(Section.objects.filter(year_level=year_level))
```

### C. Automated Activity Logging
Ensures every sensitive administrative action is tracked.

```python
def log_activity(request, action, target=None, description=None):
    # admin = get_current_admin(request)
    # Explanation: Gets the specific officer performing the action.
    admin = get_current_admin(request)
    
    # ActivityLog.objects.create(...)
    # Explanation: Inserts a new row into the audit trail table.
    ActivityLog.objects.create(
        id=uuid.uuid4(),
        admin=admin,            # Tracks WHO did it.
        action=action,          # Tracks WHAT was done (e.g., 'EVENT_DELETED').
        target=target,          # Tracks WHAT was affected.
        description=description # Tracks the specific DETAILS.
    )
```

---

## 2. ADMIN VITS OFFICER SNIPPETS

### A. QR Scanning API (Check-In & Check-Out)
This is the core engine for attendance recording.

```python
def scan_qr_api(request, event_id):
    # event = get_object_or_404(Event, id=event_id)
    # Explanation: Ensures the event exists; otherwise, returns a 404 error.
    event = get_object_or_404(Event, id=event_id)

    # --- CHECK-OUT MODE ---
    if event.status == 'ended':
        # existing = AttendanceLog.objects.filter(student=student, event=event).first()
        # Explanation: Finds the student's entry record for this specific event.
        existing = AttendanceLog.objects.filter(student=student, event=event).first()
        
        # if not existing: return JsonResponse(...)
        # Explanation: Rejects the scan if the student never checked in.
        if not existing: return JsonResponse({'success': False, 'message': 'Not checked in.'})
        
        # existing.scanned_out_at = dj_timezone.now()
        # Explanation: Records the exact timestamp of their departure.
        existing.scanned_out_at = dj_timezone.now()
        
        # existing.save(update_fields=['scanned_out_at'])
        # Explanation: Updates only the 'scanned_out_at' column for better performance.
        existing.save(update_fields=['scanned_out_at'])
```

---

## 3. REPRESENTATIVE SNIPPETS (Data Privacy)

### A. Section-Based View Restriction
Guarantees that Reps can only manage their own assigned students.

```python
# if admin_role == 'representative':
# Explanation: Checks the session to see if the user has restricted permissions.
if admin_role == 'representative':
    
    # assigned_sections = Section.objects.filter(assigned_admins__admin=current_admin)
    # Explanation: Queries the database for sections where this Rep is explicitly assigned.
    assigned_sections = Section.objects.filter(assigned_admins__admin=current_admin)

# total_students = Student.objects.filter(status='active', section__in=assigned_sections).count()
# Explanation: Filters all counts on the dashboard to only include the Rep's assigned sections.
total_students = Student.objects.filter(status='active', section__in=assigned_sections).count()
```

---

## 4. STUDENT SNIPPETS

### A. Magic Byte Validation (File Security)
Prevents malicious files from being uploaded as ID photos.

```python
def validate_upload(uploaded_file):
    # header = uploaded_file.read(16)
    # Explanation: Reads the first 16 bytes (hex signature) of the file content.
    header = uploaded_file.read(16)
    
    # for offset, magic in MAGIC_SIGNATURES.get(ext):
    # Explanation: Iterates through known "Magic Byte" signatures for the file extension.
    for offset, magic in MAGIC_SIGNATURES.get(ext):
        
        # if header[offset:offset + len(magic)] != magic:
        # Explanation: If the real content signature doesn't match the extension, reject it.
        if header[offset:offset + len(magic)] != magic:
            return False, 'File content mismatch (Not a real image).'
```

---

## 5. GENERAL SYSTEM SECURITY

### A. DDoS Protection Middleware
The system's first line of defense against network attacks.

```python
# if request_count >= 100:
# Explanation: Global Rate Limit. If an IP sends 100 requests in 60 seconds...
if request_count >= 100:
    
    # cache.set(f'ddos_block_{ip}', True, timeout=300)
    # Explanation: Automatically blocks the IP address for 5 minutes (300 seconds).
    cache.set(f'ddos_block_{ip}', True, timeout=300)
    
    # return HttpResponse('429 Too Many Requests', status=429)
    # Explanation: Tells the attacker/bot that they have exceeded the limit.
    return HttpResponse('429 Too Many Requests', status=429)
```

---

## PANELIST DEFENSE QUESTIONS (PREPARATION)

### 1. Architectural Integrity
*   **Question**: "Explain how your system handles 'Session Fixation' attacks."
*   **Answer**: "In the `login_view`, we use `request.session.cycle_key()`. This destroys the old session ID and issues a new one immediately after a successful login, ensuring an attacker cannot hijack a session through a pre-known ID."

### 2. Scalability
*   **Question**: "Your `sections_manage_view` uses a regex loop to find the highest section number. If you have 1,000 sections, will this slow down the server?"
*   **Answer**: "Since adding sections is an administrative task done infrequently, the overhead is minimal. However, to optimize, we filter by `year_level` first, narrowing the loop only to relevant records."

### 3. Forensic Auditing
*   **Question**: "If the Chairperson deletes the activity logs, is there a way to know WHO deleted the logs themselves?"
*   **Answer**: "Yes. Our code (Page 11) ensures that immediately after a wipe, the system creates a *new* log entry: `ActivityLog.objects.create(action='LOGS_CLEARED')`. This means the very last log entry in the database will always show the identity of the Chairperson who cleared the history."

### 4. Data Accuracy
*   **Question**: "How does the system calculate if a student is 'Late' versus 'Present' automatically?"
*   **Answer**: "The system takes the `event.start_time` and adds the `late_cutoff_mins` (e.g., 15 mins). It then compares the student's scan time (`dj_timezone.now()`) against that calculated cutoff. If the scan is after the cutoff, it is saved as 'late' instead of 'present'."

# CODE-IT: Enterprise System Architecture

This document provides a comprehensive overview of the **CODE-IT Attendance Portal** system architecture, operational workflows, and security models. It is designed for developers, administrators, and stakeholders to understand the ecosystem at an enterprise level.

---

## 1. System High-Level Flowchart

This diagram illustrates the lifecycle of a student from registration to attendance, along with administrative oversight and the core security layers.

```mermaid
sequenceDiagram
    autonumber
    actor Student
    actor Admin
    actor Chairperson
    participant Portal as Student Portal
    participant System as Core System (Django)
    participant DB as Database (Supabase)
    participant Mail as Email Service

    Note over Student, Mail: PHASE 1: ENROLLMENT
    Student->>Portal: Submit Registration (w/ ID Photo)
    Portal->>DB: Save Pending Student Profile
    Admin->>System: Review Registration Request
    Admin->>System: Approve Student
    System->>DB: Update Status: ACTIVE
    System->>System: Generate Secure UUID Token & QR Code
    System->>Mail: Trigger Approval Email with QR Code Attachment
    Mail-->>Student: QR Code Received via Email

    Note over Student, Mail: PHASE 2: AUTHENTICATION
    Student->>Portal: Login (Student ID + Password)
    Chairperson->>System: Login via Hidden/Randomized URL
    System->>DB: Verify Credentials & Role
    System->>System: Initialize Secure Session

    Note over Student, Mail: PHASE 3: LIVE ATTENDANCE (EVENT CYCLE)
    Admin->>System: Create & Start Event
    Student->>Admin: Present Mobile QR Code
    Admin->>System: Scan QR via Mobile Admin Panel
    System->>System: Validate Token & Check PH Time (Lateness)
    System->>DB: Record Timestamped Attendance
    System->>DB: Mark 'Present', 'Late', or 'Absent'

    Note over Student, Mail: PHASE 4: AUDIT & SECURITY
    Admin->>System: Perform Maintenance (CRUD)
    System->>DB: Auto-log Action (Admin, Target, Timestamp)
    Chairperson->>System: Review Centralized Activity Log (Audit Trail)
```

---

## 2. Core Functional Modules

### A. Student Portal (`student_portal`)
- **Profile Management**: Self-registration, profile picture updates, and password security.
- **Attendance Insight**: Personal dashboard showing total "Present," "Late," and "Absent" statistics.
- **Digital ID**: Secure view of the student's unique attendance QR code.

### B. Admin Panel (`admin_panel`)
- **Student Vetting**: Multi-lane management of Pending, Active, and Rejected student records.
- **Section Automation**: Bulk creation and automated alphanumeric sorting of academic sections.
- **Event Lifecycle**:
    - **START**: Opens the scanner for check-in.
    - **GRACE**: Permits attendance with "Late" status.
    - **END**: Closes check-in and opens check-out.
    - **CLOSE**: Finalizes records and generates XLSX reports.
- **Scanning Engine**: Mobile-responsive scanner with real-time validation against the student's encrypted token.

### C. Chairperson Command Center
- **RBAC Management**: Assignment of VITS Officers and Representatives to specific sections.
- **Infrastructure Control**: Dedicated tools for system-wide section and officer configuration.
- **Audit Oversight**: Access to the centralized **Activity Log** to monitor every administrative action for accountability.

---

## 3. Technology Stack

| Layer | Technology |
| :--- | :--- |
| **Backend** | Django 5.x / Python 3.12 |
| **Database** | Supabase (PostgreSQL) |
| **Authentication** | Custom Session-based RBAC |
| **Integrations** | SMTP (Email Notifications), QR Code Py Lib |
| **Frontend** | Bootstrap 5, Vanilla JS, Mermaid.js |

---

## 4. Security & Compliance
- **Activity Logging**: No critical action (student approval, event deletion, user creation) occurs without a server-side audit record.
- **Data Privacy**: Per recent security audits, IP addresses are excluded from logs to maintain administrator privacy.
- **Role Isolation**: Strict `@role_required` decorators prevent horizontal and vertical privilege escalation.

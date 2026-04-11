# CODE-IT Attendance System

University attendance tracking system with QR code scanning, event management, and role-based dashboards.

---

## 📋 Changelog

### What's New / Ano mga bago?

1. **Database Cleanup** — Winipe ko yung buong database para matanggal lahat ng mga test accounts at dummy data.

2. **Seed Script Update** — Inayos ko na din yung seed script kaya ngayon Chairperson account na lang talaga yung ginagawa niya by default.

3. **Hidden Chairperson Login** — Meron na din hidden na login endpoint specifically para lang sa Chairperson para mas secure.

4. **Auto-Generated Admin Passwords** — Tinanggal ko na yung manual na pag-type ng password kapag gumagawa ka ng account para sa VITS o Representative kase si Chairperson na ang maglalagay ng VITS Officers. System na din mismo mag-gegenerate ng password tapos ise-send na lang nang automatic sa email nila.

5. **Forced Password Change** — Nilagyan ko ng forced password change. So pag nag-login yung admin sa unang login niya, hindi nila ma-iiskip, kailangan talaga nilang mag-palit ng password nila for security purposes.

6. **Timezone Precision** — Konting tweak na din sa timezone para mas sure yung time accuracy/precision. Naka double lock na sa Philippine Standard Time (Asia/Manila) lahat ng checking ng oras at scanning para siguradong tama yung logs.

7. **Dashboard Section Breakdown** — Sa dashboard ng VITS tsaka Chairperson, nilagyan ko ng breakdown sa bawat section card. Makikita mo na agad dun kung ilan yung present, late, at absent. Dito na din makikita anong section ang pinaka konti ang attendees.

8. **Updated Dependencies** — Updated the requirements.txt :)

---

## 🔗 Updated Endpoints

| Role | Login URL |
|------|-----------|
| **Student** | `http://localhost:8000/student/login/` |
| **VITS / Representative** | `http://localhost:8000/admin-panel/login/` |
| **Chairperson** | `http://localhost:8000/chair_adminlogin/cp-x9k7m2v4-ctrl/` |

---

## 🚀 Quick Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Rebuild Django internal tables
cd SYSTEMPROJECT
python manage.py migrate

# Seed Chairperson account
cd ..
cd Data base proj"
python seed.py

# Run the server
cd ..
cd SYSTEMPROJECT
python manage.py runserver

> now go to the endpoints :)
```

### Default Chairperson Credentials
- **Email:** `chair@school.edu`
- **Password:** `chair123`

---

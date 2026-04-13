# CODE-IT Attendance System

University attendance tracking system with QR code scanning, event management, and role-based dashboards.

---

## 📋 Changelog

### What's New / Ano mga bago?

1. **Compact & Mobile-Friendly UI** — Inayos ko yung buong interface para mas maging compact at hindi na mukhang malaking-malaki sa mobile screen. Mas malinis na rin yung sa mga students' dashboard layout natin.

2. **Session / Role Isolation** — Inayos ko na yung issue sa pag-login. Kapag Chairperson ka, doon ka lang sa hidden endpoint makakapasok. Kung ordinary VITS officer ka tas nag-try ka dun sa chairperson URL, maki-kick ka pabalik. Tapos nilagyan ko ng `forced_password_change` para pagka-login ng bagong admin, required palitan yung system-generated password.

3. **Stacked Donut Chart** — Tinanggal ko na yung napakalaking Pie Chart sa dashboard kase kumakain ng espasyo. Pinalitan ko siya ng compact na magandang Stacked Donut chart para clear at mas presentable tignan yung data ng attendance.

4. **Year Level Dropdown sa Sections** — Sa dashboard ni Chairperson, ginawan ko ng Year Level dropdown mask filter yung mga list of sections para hindi sumobra yung haba pababa at para mas pleasant sa mata basahin.

5. **Auto-Generated QR & Emailing** — Tinanggal ko na nang tuluyan yung manual na "Generate QR" button kase yung logic ko na mismo yung gagawa ng QR tsaka mag-sesend derekta sa email ng estudyante pagdating nung na-Approve na ang registration nila.

6. **Admin / VITS Registration Fix** — Tiniyak ko na rin allowed at hindi mag-eerror pag yung mismong VITS officers or Representatives ay magreregister rin as "Student" account para ma-track din sila na present sa loob ng venue.

7. **Optional Start & End Time** — Ginawa ko ng optional lang (pwede i-blanko) or "null" sa database yung Time natin kapag gagawa ka ng Event. Kung i-sscan at i-sstart niyo ng wala dun, susundin na lang at i-sestamp niya automatic yung current na Philippine Time kung anong oras niyo clinick ang manual "Start".

8. **Live Active Counting Metrics** — Tinanggal ko muna yung Expected Students screen, kase dito sa dashboard natin ngayon... yung Absent na nakatala eh eksaktong kung ilan lahat yung tao dun sa section. Sa oras na mag bukas yung event, unti-unti lalakad yung 'Present' / 'Late' habang bumababa ang 'Absent' dependente sa pag scan nila ng totoong buhay! Pag inend yung event tsaka lang mag rereset ang dashboard to 0 para ready para sa next.

9. **Live Photo Scanner** — Para alam ng officer kung sino yung nag s-scan... once na nag pop up sa screen scanner ang check-in ng isang tao, kasabay niya ipapakita yung 64px ID Picture nila doon! Pinalitan ko rin pala yung mga emoji-emoji na yun nung proper Badge status flags para maging propesyunal tignan!

10. **Check-Out & Final Comparison System** — Binago ko yung logs nang slight. Meron tayung tatlong phases:
      - *Start Phase*: Nakatala yung lahat nang nag scan papasok.
      - *Exit/End Scan*: Pwedeng i-scan na lahat ng estudyante pag palabas as "Check Out" timer and list of missing the exit.
      - *Final Close Event*: And finally, dinagdag ko yung button na kulay red na "Close Event". Kapag clinick ito ni Chairperson, ila-lock out niyang permanently yung buong pag-sscan dito ... mag-gegenerate na siya ng magkadikit na "Check-in vs Check-out" record tapos ilalabas natin ang "FINAL OUTPUT LIST"! Dito masasabi kung sino ang True/Final Present gamit yung filter natin ng sections tsaka year level drop-downs direkta sa list.

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
cd "Data base proj"
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

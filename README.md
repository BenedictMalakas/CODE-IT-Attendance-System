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

11. **Activity log**- Meron ng activity log na chairman lang nakakaaccess nakikita nya dito kung ano yung denelete, create, accept ng mga admins meron nadin tong filter na pwede mong isearch yung name ng admin para makita mo ano ginawa nila.
12. **HTTPS** - gumagana na yung cam kasi nakakuha na nang certificate sa certbot ng azure para mas secure na kasi kanina di gumagana dahil naka HTTP lang
13. **Fixed Login "Kick-Out" Bug** - since bawal mag login pag same broweser ang admin panel and chairperson dahil same lang naman sila ng session id na kapag pumunta kadon nag aauto logout inayos ko sya na if same browser yung gamit then for example nasa admin ka clinick mo chairperson mag aauto balik ka sa admin.
14. **Overall UI/UX Polish** - Na-fix na natin yung z-index issues pag may binuksang modal na nagiging unclickable buttons, at yung "scan" button tinanggal ko sa *closed events*. Center aligned narin yung mga Donut Chart. Tapos sa Activity logs, di na uma-overlap ang mga title bands.
15. **Pagination System** - Para di ka maumay kaka-scroll pag sobrang dami ng records, nag add ako ng Pagination sa lahat ng Data Tables like ung Logs, Students, Events, and Sections view natin. Set yan to 25 items per page display.
16. **Advanced Table Filters & Batch Management** - Sa Student Management at Activity Logs, nadagdagan ng Date Range, Section filters, at may Checkbox "Select All" nang kasama pang *bulk approve*. Sa Admins Sections Overview, may Year Level menu filter narin.
17. **QR Secure & Display** - Na-fix ko yung missing Token variable view sa dashboard kaya lalabas na yung actual na QR ID if Verified na. Tinago ko rin yung literal na text UUID ng QR nila kase di naman nila need basahin yun for security.
18. **Session Expiry Indicator** - Nag add ako ng Live Countdown timer "Session" para sa portal ng students na mag-wa-warn kapag onting oras nalang bago mag expire yung browser auth nila.
19. *Password Encryption Upgrade* - 

Before - yung unang ginawa natin is naka SHA-256 which is good naman pero kapag kasi nakuha data base natin possible na mahulaan password gamit yung rainbow tables, rainbow tables andon nakalagay mga naka encrypt na basic password like password123 syf83hwianf so kaya sya mahulaan pag nagka access sa data base

After - gumamit na tayo ngayon ng PBKDF2-SHA256 so eto hashing padin pero may random hash na sya each user for example syf83hwianf sa password 123 madadagdagan sya ng syf83hwianf-ytiahsif so mahihirapan i-crack mga password kahit nagkaaccess na sa database

20. **Random Admin Passwords**-
Before -  {lastname}_@2026# ganito lang yung format so pag kilala mo kung sinong admin or what possible na makapasok kahit sino lalo na pag dipa nala-log in magandang ginawa natin dito is using one time password na magpapalit 

After - Mas secure na sya crytographycally random na yung password na isesend sa gmail nung mga admin gamit yung python secret module

21. **15 minute login lockout**
Before: kahit ilang try pwede sa password concern ko is kapag may nagpasok ng bot na kaya mag generate nang maraming pass possible na ma crack 

After - Ngayon nilagyan ko sya nang after 5 failed attempt magkakaroon ka ng 15 minutes cooldown bago makapag try ulit

22. **Session Fixation Protection** - 
Before- before kasi yung system nadin hindi nagbabago session id nya so pag may hacker na nakanakaw nung session cookie pag nagsend sya sayo ng fake link madali nalang sya makakapasok without using your password kasi nga session cookie yon so mahirap sya lalo na pag sa public wifi.

After - request.session.cycle_key()  sinisira nito yung old session id tas gagawa sta bago pero naka keep padin log in data so pagnanakaw session cookie wala din since nagbago nga

23. **Secure Cookie Setting** - 
Before- yung system kasi natin naka on yung SESSION_COOKIE_SECURE = False meaning nakakpagsend tayo ng login cookie sa HTTP which is delikado lalo na sa public tas merong sniffing traffic na nangyari so bali para syang naka tap sa calls then makikita nila password email pati yung session cookie

After - 
**HTTPS only** - para dina magsend ng plain cookie sa HTTP
**HttpOnly** -  since before wala tong  SESSION_COOKIE_HTTPONLY = True kapag merong nag inject sa site natin ng malicious script mababasa nya or makukuha nya yung cookies na pwedeng makuha lahat ng data na priniprevent natin
**SameSite=Lax** -  because of this naka tied lang sa specific domain yung system natin so kahit na may mapindot namalicious website walang mangyayari hindi nya maaaccept yung mga nakatagong request sa malicious site

24. **DDoS Protection Middleware**- 
Before - walang humaharang sa server natin sa pag flood ng request so pwedeng magrequest ng ilang libong beses na magcacause ng pagkasira nung server, lalo na ngayon usong uso since madaming gumagamit ng mga bot para magrequest ng magrequest

After - ngayon merong ng custom middle middleware config/middleware.py meron tong 3 layers na humaharang

**IP Block**	- Instantly rejects IPs that were already flagged	Blocked for 5 min
**Body size** - Rejects oversized uploads/payloads	Max 10MB eto yung nangyayari nung nakaraan na nagkakaerror pag sobra yung na a- upload 
**Rate Limit**	* -Counts requests per IP per minute	100 req/min, then blocked

25. **Additional Protection** - 
**Refferer Policy** - before kasi nakikita ng mga external site full URL nung system natin which is risky now pag accidentally tayo makapindot ng external site ang mangyayari is //school.com eto nalang makikita hindi na yung kadugtong na mahaba
**Permissions Policy** -  hinaharangan mga unathorized access  sa camera pati location APIs para if ever na may makapasok wala lang din mangyayari sakanila

**CORS_ALLOW_ALL_ORIGINS = DEBUG** - 	Before, pwede makagawa ng API calls kahit na anong website sa sytem natin now hindi na nakaset na sya na domain lang natin
**Removed '' from ALLOWED_HOSTS** - 	Before, any domain pwedeng mag point sa server natin para syang call center na lahat sinasagot nya kahit scam na so now meron na syang caller id na specific domain lang sinasagot nya

**X-Content-Type-Options: nosniff** - Since naka camera tayo sa scan mahirap na pag wala tayo neto since creative mga hackers for example yung hacker may hidden code na nilagay mag eexecute sya  which is priniprevent natin

**X-Frame-Options** - priniprevent neto yung clickjacking or yung paglagay ng website natin sakanila basically ang nangyayari dito para syang invisible layer na akala mo andon kapa sa system natin pag nag click ka hack kana, so since meron tayo nito pag may nag try satin ng clickjacking instead na yung portal makita error makikita nila.

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

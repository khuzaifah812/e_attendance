 # SARS - Students Attendance & Registration System
Django (backend) + MySQL + plain HTML/CSS/JavaScript (front end). Light-green professional theme.

## 1. Run it locally (Windows / Linux / macOS)
Requirements: Python 3.10+, MySQL 8 (XAMPP/MySQL Server) - or skip MySQL for a quick test (SQLite is used when DB_NAME is empty).

```bash
cd sars
python -m venv venv
venv\Scripts\activate            # Linux/macOS: source venv/bin/activate
pip install -r requirements.txt

# MySQL: create the database once
#   mysql -u root -p -e "CREATE DATABASE sars_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
copy .env.example .env           # Linux/macOS: cp .env.example .env   -> then edit DB_PASSWORD etc.

python manage.py makemigrations core
python manage.py migrate
python manage.py seed_demo --lat YOUR_LAT --lng YOUR_LNG --email your@email.com
python manage.py runserver
```
Open http://127.0.0.1:8000 .  `--lat/--lng` = GPS of the place where you will test (so the demo room is "where you are").
Get them from Google Maps (long-press your position). Without them the room is in Kampala centre.

Demo logins (password = the full name; admin has a fixed password):
| Role | Username | Password |
|---|---|---|
| Administrator | admin | Admin@123 |
| Coordinator | COORD01 | Grace Nakato |
| Lecturer | LEC001 / LEC002 / LEC003 | Sarah Ndagire / Peter Ssemwogerere / Joan Atim |
| Student | 2026/0001 ... 2026/0008 | Francis Musimbi, Sarah Nalubega, David Kato, Aisha Nanyonga, John Bosco, Mary Achieng, Brian Mugisha, Esther Namatovu |

Own admin instead: `python manage.py createsuperuser`.

### Emails
No SMTP set = emails are printed in the terminal. To send real emails (Gmail): turn on 2-step verification, create an
"App password", then set in `.env`: EMAIL_HOST_USER=you@gmail.com, EMAIL_HOST_PASSWORD=<app password>.

### Reminders (5 h / 1 h / 10 min students, 2 h / 10 min lecturers)
They are sent by a scheduler that checks every minute. `ENABLE_SCHEDULER=1` starts it inside `runserver`/gunicorn.
Alternative: `python manage.py send_reminders --loop` in a second terminal (or a cron job running `send_reminders` every minute).

## 2. Deploy online: Clever Cloud (MySQL) + Render (web app)
1. **Database** - clevercloud.com -> Create -> Add-on -> MySQL (free DEV plan). Open the add-on and copy `MYSQL_ADDON_URI`
   (looks like `mysql://user:password@host:3306/dbname`).
2. **GitHub** - push the `sars` folder to a new GitHub repository (`.env` is git-ignored).
3. **Render** - New -> Web Service -> connect the repo. Settings:
   - Build command: `./build.sh`
   - Start command: `gunicorn sars.wsgi:application --workers 1 --threads 4 --timeout 120`
   - Environment variables: `PYTHON_VERSION=3.12.7`, `DEBUG=False`, `SECRET_KEY=<long random text>`,
     `DATABASE_URL=<the MYSQL_ADDON_URI>`, `ENABLE_SCHEDULER=1`, and for email `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`.
   (or use the included `render.yaml` as a Blueprint.)
4. After the first deploy open Render -> Shell and run: `python manage.py seed_demo --lat YOUR_LAT --lng YOUR_LNG --email you@mail.com`
   (or `python manage.py createsuperuser`).
5. Free-tier notes: the service sleeps after ~15 min idle, which pauses reminders - create a free monitor at uptimerobot.com that
   opens `https://YOUR-APP.onrender.com/health/` every 5 minutes. Uploaded attachments (notes/assignments) are stored on Render's
   temporary disk and are lost on redeploy (profile photos are stored in the database, so they are safe). For permanent files add a
   Render Disk mounted at `/opt/render/project/src/media`.
6. HTTPS (Render) is required for GPS and camera on phones; localhost is allowed for testing.

## 3. How to demonstrate every requirement
| Requirement | Where to show it |
|---|---|
| Username = reg. number, password = name | Register a student at /register/ then login with `reg no` / `First Last` |
| Physical attendance needs room location + face or QR | Lecturer LEC001 -> Lectures -> live "Algorithms" lecture -> Session -> Activate. Student -> Take attendance: location box turns green, then face scan (enrol face first in My Profile) or QR/code tab |
| Online lecture code lasts 30 min, only during the lecture | LEC002 -> live online lecture -> Session -> Activate (countdown shown; never beyond the lecture end). Outside lecture time activation is refused |
| Only once per lecture | Try to mark the same lecture again: warning box |
| Attendance % incl. emergency lectures | Student dashboard / My Attendance (taught lectures only) |
| Calendar day-one to end | Calendar page (month navigation limited to the semester) |
| Reminders on system + email | Notifications page (System / Email tabs). The seed makes a lecture ~65 min ahead: you get the 1 h and 10 min reminders |
| Admin dashboard, photo, details, date/time, GPS | Login as admin |
| Admin opens any student dashboard | Students -> View dashboard; Print button prints the attendance list |
| Lecturer clash protection | Lectures -> Schedule lecture; try an overlapping time for the same lecturer -> error |
| Posts reach students by system + email | Lecturer -> Post Material |
| Coordinator = lecturer + student management | Login COORD01 |

## 4. Honest limitations
* Face matching runs in the browser (face-api.js models are loaded from the jsDelivr CDN, so the device needs internet); the server compares the
  128-number face descriptor with the enrolled one. It is suitable for a coursework/prototype, not a high-security product (GPS and the
  face descriptor are sent by the browser and could be spoofed by a determined user).
* Registration numbers are used as usernames; the default password (the name) should be changed in My Profile.

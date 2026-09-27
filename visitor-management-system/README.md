# Visitor Management System

A complete Flask + SQLite visitor management web application for offices, colleges, residential societies, corporate buildings, and institutions.

## Features

- Secure login with Flask-Login and Werkzeug password hashing.
- Role-based access for ADMIN, SECURITY, and RECEPTIONIST.
- Visitor registration with appointment, host, ID proof, and optional photo upload.
- Unique visitor IDs such as `VIS-2026-00001`.
- Approval workflow: Pending, Approved, Rejected, Cancelled.
- Check-in and check-out with timestamps, duration, and activity history.
- Blacklist management with an ADMIN-only override at check-in.
- Host CRUD, deactivation, search, and visitor association view.
- Live visitor log with AJAX refresh every 12 seconds.
- Dashboard statistics from real database records plus Chart.js charts.
- In-app notifications with unread count, mark-read, manual sending, and optional email.
- Visitor pass with QR code and print support.
- Search, filtering, and pagination for visitor records.
- Daily/weekly/monthly, host-wise, and department-wise reporting.
- CSV export, PDF export, and browser print support.
- ADMIN user management including role changes, deactivation, and password reset.
- CSRF protection, input validation, upload extension/MIME/image validation, upload size limit, secure session cookie settings, and friendly error pages.

## Technology stack

Backend: Python, Flask

Frontend: HTML5, CSS3, JavaScript, Bootstrap 5, Bootstrap Icons, Chart.js

Database: SQLite, SQLAlchemy ORM via Flask-SQLAlchemy

Authentication: Flask-Login, Werkzeug password hashing, Flask-WTF CSRF protection

Optional: Flask-Mail, QRCode, Pillow, ReportLab

## Project structure

```text
visitor-management-system/
├── app.py
├── config.py
├── requirements.txt
├── README.md
├── seed.py
├── .env.example
├── .gitignore
├── database.db                 # demo copy; working DB is instance/database.db
├── models/
│   ├── __init__.py
│   ├── user.py
│   ├── visitor.py
│   ├── host.py
│   └── notification.py
├── routes/
│   ├── __init__.py
│   ├── auth.py
│   ├── dashboard.py
│   ├── visitors.py
│   ├── hosts.py
│   ├── notifications.py
│   └── reports.py
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   ├── notifications.html
│   ├── users/
│   │   ├── list.html
│   │   ├── form.html
│   │   └── settings.html
│   ├── visitors/
│   │   ├── list.html
│   │   ├── add.html
│   │   ├── edit.html
│   │   ├── details.html
│   │   ├── checkin.html
│   │   ├── live.html
│   │   ├── pass.html
│   │   └── blacklist.html
│   ├── hosts/
│   │   ├── list.html
│   │   ├── add.html
│   │   ├── edit.html
│   │   ├── form.html
│   │   └── details.html
│   ├── notifications/send.html
│   ├── reports/
│   │   └── visitors.html
│   └── errors/
│       ├── 403.html
│       ├── 404.html
│       └── 500.html
├── static/
│   ├── css/style.css
│   ├── js/script.js
│   └── uploads/
└── instance/
    └── database.db           # working SQLite database
```

## Windows / VS Code installation

Open the project folder in VS Code and run these commands in the integrated terminal.

```bat
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python seed.py
python app.py
```

Open:

`http://127.0.0.1:5000`

## Development credentials

ADMIN

- Email: `admin@visitor.com`
- Password: `Admin@123`

SECURITY

- Email: `security1@visitor.com`
- Password: `Security@123`

RECEPTIONIST

- Email: `reception1@visitor.com`
- Password: `Reception@123`

Additional seeded accounts are in `security2@visitor.com` and `reception2@visitor.com` using the same role password pattern.

These are development credentials. Change passwords before any production use.

## Database setup and reset

The application automatically creates all database tables on startup.

To ensure the current seed data without destroying existing records:

```bat
python seed.py
```

To completely reset the database and restore the demo data:

```bat
python seed.py --reset
```

The working database is `instance/database.db`. The included SQLite files are schema-initialized; on first application startup, `app.py` automatically inserts the development users, 10 hosts, and 20 demo visitors.

## Email configuration

Email is optional. The application continues to work using in-app notifications even when SMTP is not configured.

Set the variables shown in `.env.example` in the Windows environment before starting the application. For example, configure `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD`, and `MAIL_DEFAULT_SENDER`.

For production, keep credentials in environment variables or a secure secret store instead of committing them to source control.

## How to use

1. Sign in as ADMIN, SECURITY, or RECEPTIONIST.
2. Add hosts before registering visitors if you reset the database.
3. Register a visitor with appointment and identity information.
4. Receptionist/Admin can approve or reject pending visitors and can send manual in-app notifications. Security-created visitors are auto-approved for walk-in/front-desk use.
5. Security/Admin checks the visitor in. The application verifies blacklist status first.
6. Security/Admin checks the visitor out later and the system stores the visit duration.
7. Use Live Visitors for the automatically refreshing active visitor list.
8. Use Reports for date/status/host/department filters and CSV/PDF/print output.

## Roles

### ADMIN

Full access, including users, hosts, visitors, dashboard, reports, blacklist, and deletion.

### SECURITY

Register visitors, check visitors in/out, view/search records, and view today's visitor activity.

### RECEPTIONIST

Register and manage appointments, view visitors, approve/reject/cancel visitors, manage hosts, and receive notifications.

## Security notes

- Passwords are stored as salted hashes, never plaintext.
- CSRF protection is enabled for form submissions.
- SQLAlchemy ORM is used instead of handwritten SQL for application queries.
- Jinja auto-escaping protects normal HTML rendering from injected markup.
- Uploads are limited to JPG/JPEG/PNG, checked with Pillow, and limited to 2 MB.
- Uploaded filenames are replaced with random UUID-based names.
- Role checks are applied to privileged routes.
- User-facing 403, 404, 413, and 500 pages avoid exposing internal stack traces.

## Testing

Run the included automated smoke/integration tests:

```bat
python -m pytest -q
```

The tests cover login, role restrictions, visitor registration, approval, check-in/out, notifications, blacklist protection, host CRUD, reporting exports, and invalid login handling.

## Deployment

For real deployment, use a production WSGI server such as Waitress on Windows or Gunicorn on Linux. Set a strong `SECRET_KEY`, use a production database when needed, configure HTTPS, set `SESSION_COOKIE_SECURE=true` behind HTTPS, and replace all development credentials.

Example Windows production server:

```bat
pip install waitress
waitress-serve --listen=127.0.0.1:5000 app:app
```

For internet-facing deployments, place the app behind a reverse proxy/TLS terminator and keep SMTP/database credentials outside the source code.


### The world’s most high-end designed, lightweight, and feature-rich learning management system.

Learning management system using Django web framework. You might want to develop a learning management system (also known as a school/college management system) for a school/college organization, or simply for the purpose of learning the tech stack and enhancing your portfolio. In either case, this project would be a great way to get started. The aim is to create the world's most lightweight yet feature-rich learning management system. However, this is not possible without your support, so please give it a star ⭐️.

_Documentation is under development_

## Current features

- Dashboard: School demographics and analytics. Restricted to only admins
- News And Events: All users can access this page
- Student records include personal, programme, cohort, enrolment, and next-of-kin details.
- Registrars and users with student-management permissions can search student records and record lifecycle status changes; withdrawals are archived rather than deleting accounts or records.
- Student documents are stored outside public media storage and served through authenticated downloads.
- Accepted admission applications can be linked to matching, active student records.
- Admissions administrators can add, rename, deactivate, and reactivate application statuses from the Admissions dashboard. Reviewers can move an application to any active status; the current status is selected by default, and status history is retained.
- Academic course registration is limited to active students and courses matching their programme, level, year, and current semester. Enrollment attempts link to a semester; drops retain grades and record who dropped them and when. Student timetables use the current semester's linked academic session.
- Clinical Training supports ward and capacity management, dated student placements with supervisor and semester links, audited placement status history, student clinical logbooks, and supervisor verification of clinical hours.
- Assessment & Results exposes the assessment hub, student grade views, and lecturer score entry through the main application routes. Score updates are restricted to the lecturer's allocated course and active semester enrollments.
- Finance supports semester fee categories, student invoices and statements, idempotent semester invoice generation, and payment records with outstanding-balance validation. Invoice totals are derived from their fee items; student invoice views are restricted to the signed-in student's own records.
- Staff and Department management supports staff categories, employee records linked to departments and faculties, department heads, active/inactive status, and department CRUD through permission-checked screens and authenticated finance APIs. Deactivating a staff record preserves its payroll history.
- Institutional Reporting & Analytics combines admissions, student enrolment, results, clinical placements, invoices/payments, and procurement indicators. Reports can be filtered by academic semester and exported as CSV; access is limited to superusers or users granted the `reports.view` role permission, with user-level DENY overrides honored.
- Procurement supports supplier and purchasing-plan records, requisitions that move through configurable status and approval rules, received supplier quotations with their original documents and itemized prices, and purchase orders created from the selected offer. Workflow rules can route each status change to a role or named user; department-specific rules take precedence over global rules and require a named approver because accounts are not otherwise linked to procurement departments. Requesters cannot approve their own requisitions. Review decisions are recorded with actor, timestamp, and comments; one quotation can be selected per approved requisition, and orders inherit that quotation's supplier, items, and prices before manager approval. Purchasing approvals use POST requests, active suppliers and approved requisitions are required, order values are checked against requisition limits, and soft-deleted purchasing records remain retained.
- Admin manages lecturers(Add, Update, Delete)
- Students can Add and Drop courses
- Lecturers submit students' scores: _Attendance, Mid exam, Final exam, assignment_
- The system calculates students' _Total, average, point, and grades automatically_
- Grade comment for each student with a **pass**, **fail**, or **pass with a warning**
- Assessment result page for students
- Grade result page for students
- Session/year and semester management
- Assessments and grades will be grouped by semester
- Upload video and documentation for each course
- PDF generator for students' registration slip and grade result
- Page access restriction
- Storing of quiz results under each user
- Question order randomization
- Previous quiz scores can be viewed on the category page
- Correct answers can be shown after each question or all at once at the end
- Logged-in users can return to an incomplete quiz to finish it and non-logged-in users can complete a quiz if their session persists
- The quiz can be limited to one attempt per user
- Questions can be given a category
- Success rate for each category can be monitored on a progress page
- Explanation for each question result can be given
- Pass marks can be set
- Multiple choice question type
- True/False question type
- Essay question type................._Coming soon_
- Custom message displayed for those that pass or fail a quiz
- Custom permission (view_sittings) added, allowing users with that permission to view quiz results from users
- A marking page which lists completed quizzes, can be filtered by quiz or user, and is used to mark essay questions
- Finance module - INvoice students with both partial and full payments - allow printing out.
- Student view invoice- students are able to view there invoices according to the semesters
- Voting module - for both opinion polls and campus elections.
- Faculty admin module
# Quick note for future contributors

If you would like to contribute, simply begin by implementing one from the list in the `TODO.md` file.

# Requirements:

> The following program(s) are required to run the project

- [Python3.8+](https://www.python.org/downloads/)

# Installation

- Clone the repo with

```bash
git clone the project
```

- Create and activate a python virtual environment

```bash
pip install -r requirements.txt
```

- Create `.env` file inside the root directory

- Copy and paste everything in the `.env.example` file into the `.env` file. Don't forget to customize the variable values

For local development, `DEBUG=True` uses a development-only fallback secret when `SECRET_KEY` is empty. Before deployment, set `DEBUG=False`, provide a long, randomly generated `SECRET_KEY`, and configure `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` for the deployment domains. For HTTPS-only deployments, also enable `SECURE_SSL_REDIRECT` and configure `SECURE_HSTS_SECONDS` after confirming HTTPS is enforced end to end.

### Nginx media serving

Site logos and the favicon are public branding assets stored under
`MEDIA_ROOT/site/`. In production, serve only this directory directly through
Nginx; do not expose the rest of `MEDIA_ROOT`, which may contain private
uploads. The included Nginx snippet targets `/var/www/erp-ap/media/site/`:

1. Copy `deploy/nginx/erp-ap-media.conf` to
   `/etc/nginx/snippets/erp-ap-media.conf`.
2. Add `include /etc/nginx/snippets/erp-ap-media.conf;` inside the active
   site's `server` block.
3. Ensure the Nginx worker can read files in
   `/var/www/erp-ap/media/site/`, and that this directory is on persistent
   storage included in backups.
4. Run `sudo nginx -t` and, if it succeeds, reload Nginx with
   `sudo systemctl reload nginx`.

The configured logo files must exist under `/var/www/erp-ap/media/site/`.
If the database has their names but the files are missing, restore the files
from backup or upload them again in **System Settings → Branding & Logo**.

Superusers can configure SMTP host, port, authentication, TLS/SSL, and sender details from **System Settings → Email Server**. Dashboard settings are disabled until explicitly enabled; otherwise the application uses the `EMAIL_*` values in `.env`. SMTP passwords entered in the dashboard are encrypted using `SECRET_KEY`, so protect backups of both the database and that key. Changing `SECRET_KEY` makes previously stored SMTP passwords unreadable; enter the password again after rotating the key.

```bash
python manage.py migrate
```

```bash
python manage.py createsuperuser
```

For local demo data, first apply the project migrations, then run:

```bash
python manage.py seed_demo_data --dry-run
python manage.py seed_demo_data
```

The seeder is restricted to `DEBUG=True` with SQLite, marks generated records
with `DEMO`, creates fictional admissions, academic, clinical, staff, finance,
and procurement records, and is safe to rerun. Demo accounts have unusable
passwords; set credentials manually only if you need to sign in as one.

To seed only fictional Procurement examples, use:

```bash
python manage.py seed_demo_data --procurement-only --dry-run
python manage.py seed_demo_data --procurement-only
```

This creates only the demo procurement account and its sample suppliers,
department, plan, requisition, quotation, and order. It never imports records
from the local database.

```bash
python manage.py runserver
```

Last but not least, go to this address http://127.0.0.1:8000

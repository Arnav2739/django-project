# 💊 Smart MedTrack

**Automated Medication Adherence & Inventory Forecasting System**  
*A clinical telemetric and safety management platform built on Django 5+, Celery, Redis, HTMX, and Tailwind CSS.*

---

## 🌟 Executive Summary & Key Highlights

Smart MedTrack solves three fundamental flaws of conventional alarm apps and plastic pillboxes:
1. **Biological Routine Anchoring**: Dosing schedules align with human meal routines (`Breakfast`, `Lunch`, `Dinner`, `Bedtime` with offsets like *-15 min before breakfast*) rather than arbitrary clock alarms.
2. **Two-Tier Fail-Safe Escalation**: Unconfirmed doses trigger an automated escalation chain. If a dose is unconfirmed 30 minutes past its scheduled time, Tier 1 primary caregivers receive an urgent alert. If unacknowledged within 60 minutes, secondary Tier 2 emergency contacts are escalated.
3. **Atomic Inventory & Depletion Forecasting**: Medication stock decrements concurrently and safely using database row locking (`select_for_update` + `transaction.atomic`). Rolling 7-day burn rates calculate exact stockout dates and trigger proactive replenishment alerts.
4. **Clinical Adherence Reports**: Generates verifiable, print-ready and PDF-exportable adherence scorecards with physician attestation blocks.

---

## 🏗️ Architecture & Tech Stack

| Component | Technology | Role |
|---|---|---|
| **Backend & ORM** | Python 3.13 / Django 6.1 | Core MVC, business logic, authentication, ORM |
| **Database** | PostgreSQL 16 (or SQLite fallback) | ACID relational storage, row-level locks, constraints |
| **Async Task Queue** | Celery 5.4 + Redis 8 | Periodic missed dose scanner, multi-channel alerts |
| **Dynamic Frontend** | Django Templates + HTMX 2.0 | Reactive partial swaps (instant dose check-offs) without SPA bloat |
| **Styling & UI** | Tailwind CSS + Google Inter | Glassmorphic clinical dashboard, status tags, responsive sidebar |
| **Reporting & Export** | HTML5 Print CSS / WeasyPrint | A4 clinical compliance scorecards with physician sign-off |

---

## 📁 Repository Structure

```
django-project/
├── core/                       # Project configuration
│   ├── settings.py             # Settings (Environ, Celery, DB, Static)
│   ├── urls.py                 # Master URL routing
│   ├── celery.py               # Celery application setup
│   └── wsgi.py / asgi.py
├── medtrack/                   # Main application
│   ├── models.py               # 6 Core models (PatientProfile, Routine, Medication, Regimen, DoseEvent, Caregiver)
│   ├── views.py                # Auth, Dashboard, CRUD views, Clinical Reports
│   ├── urls.py                 # App route mappings
│   ├── forms.py                # Tailwind-styled forms with dynamic weekday selectors
│   ├── admin.py                # Customized Django admin interface
│   ├── tests.py                # Comprehensive 14-test unit & integration test suite
│   ├── tasks.py                # Celery periodic and async background tasks
│   ├── services/
│   │   ├── scheduling.py       # Anchor-offset time calculation & daily dose event generation
│   │   ├── inventory.py        # Atomic stock decrement, 7-day burn rate, stockout calculation
│   │   ├── escalation.py       # 30m Tier 1 & 60m Tier 2 missed-dose state machine
│   │   ├── notifications.py    # Multi-channel caregiver alert dispatcher (SMS / Email)
│   │   └── reports.py          # Clinical adherence data compilation & PDF rendering
│   ├── templatetags/
│   │   └── medtrack_tags.py    # Timezone conversion, status colors, and stock gauges
│   └── templates/medtrack/
│       ├── base.html           # Responsive layout with modern glassmorphism & sidebar
│       ├── dashboard.html      # Intake dashboard with HTMX instant check-offs
│       ├── login.html / register.html
│       ├── profile_setup.html  # Daily routine anchors configuration
│       ├── medication_list.html / medication_form.html / medication_confirm_delete.html
│       ├── regimen_list.html / regimen_form.html / regimen_confirm_delete.html
│       ├── caregiver_list.html / caregiver_form.html / caregiver_confirm_delete.html
│       ├── partials/dose_card.html
│       └── reports/adherence_report.html
├── docker-compose.yml          # Local PostgreSQL 16 + Redis 7 stack
├── requirements.txt            # Python dependencies
└── manage.py
```

---

## 🚀 Quickstart Guide

### ⚡ One-Click Run (Windows)
Double-click `start.bat` or run in terminal:
```cmd
start.bat
```
This automated launcher:
1. Verifies/creates `.venv` and installs required packages.
2. Lets you choose between **Fast Local Mode** (SQLite) or **Docker Stack** (Postgres + Redis + Celery).
3. Automatically runs migrations and verifies demo seed data.
4. Opens your default web browser to [http://127.0.0.1:8000/](http://127.0.0.1:8000/).

---

### Manual Setup

#### 1. Prerequisites
- Python 3.10+ installed
- *(Optional for full Docker stack)* Docker & Docker Compose

#### 2. Virtual Environment Setup
```powershell
# Windows PowerShell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

```bash
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Database & Migrations
The application automatically defaults to SQLite for immediate local development. To use PostgreSQL, start the container (`docker compose up -d`) and set `DATABASE_URL` in `.env`.

Apply all database migrations:
```bash
python manage.py migrate
```

### 4. Seed Deterministic Sample Data
Load sample patient routines, medications, regimens, caregivers, and scheduled doses:
```bash
python manage.py seed_db --flush
```

**Pre-seeded Demo Accounts:**
| Username | Password | Profile | Routine Anchor |
|---|---|---|---|
| `patient1` | `medtrack123` | Ramesh Patel | IST (Asia/Kolkata) — Metformin, Lisinopril, Atorvastatin |
| `patient2` | `medtrack123` | Sarah Johnson | EST (America/New_York) — Levothyroxine, Omeprazole |

---

## 🖥️ Running the Application

### Start Development Server
```bash
python manage.py runserver
```
Navigate to [http://127.0.0.1:8000/](http://127.0.0.1:8000/) to access the dashboard.

### Run Celery Worker & Beat (Escalation Engine)
In separate terminal tabs with `.venv` activated:
```bash
# Terminal 1: Celery Worker
celery -A core worker -l info -P solo

# Terminal 2: Celery Beat (Periodic 1-minute missed dose scanner)
celery -A core beat -l info
```

---

## 🧪 Test Suite

Run the full automated test suite (covering models, scheduling, atomic inventory decrements, views, escalation engine, and clinical reporting):
```bash
python manage.py test medtrack
```
*Current test result:* `14 tests passing, 0 errors, 0 failures`.

---

## 🩺 Clinical Workflow & State Machine

```
[ Scheduled Anchor ] ──> Scheduled (+0m)
                               │
            ┌──────────────────┴──────────────────┐
            │                                     │
            ▼ (Intake confirmed)                  ▼ (Unconfirmed >30m)
     [ TAKEN / TAKEN_LATE ]                    [ MISSED ]
            │                                     │
    Atomic Inventory                              ├─> Tier 1 Alert (Primary Caregiver)
     Stock Decrement                              │
                                                  ▼ (Unresolved >60m)
                                              [ TIER 2 ALERT ]
                                              (Emergency Secondary Contact)
```

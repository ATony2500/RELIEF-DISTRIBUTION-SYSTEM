# National Relief Distribution System (NRDS)

A web-based humanitarian aid management platform developed for Nigeria's relief distribution operations.

**Author:** ADACHE, Dominion Enemona (FT22ACMP0514)  
**Institution:** Nasarawa State University, Keffi  
**Supervisor:** Dr. Mustafa Ahmed Umar  

---

## Overview

The NRDS is a full-stack web application that digitises Nigeria's relief distribution process. It covers:

- Beneficiary registration and NIN-based identity verification  
- Real-time inventory management across multiple warehouses  
- Nearest Neighbour route optimisation for delivery planning  
- Role-based access control (RBAC) for all user types  
- Immutable audit trail for accountability and transparency  
- Reporting dashboards for NEMA, SEMAs, and partner organisations  
- Dark-themed UI built on Tailwind CSS with a custom green/navy palette  

---

## Technology Stack

| Layer | Technology |
|---|---|
| Back-end | Python 3.10+, Flask 3.x |
| ORM | SQLAlchemy 2.x + Flask-SQLAlchemy |
| Database | MySQL 8.0 (via PyMySQL) |
| Authentication | Flask-Login + Flask-Bcrypt |
| Migrations | Flask-Migrate (Alembic) |
| Front-end styling | Tailwind CSS 3.x (dark theme, compiled) |
| Front-end | HTML5, Jinja2 templates, JavaScript |

---

## Design System

The application uses a dark theme with the following palette:

| Token | Hex | Usage |
|---|---|---|
| Background | `#041122` | App body, auth gradient endpoint |
| Primary | `#7FDA89` | Buttons, links, active states, focus rings |
| Primary Dark | `#259073` | Sidebar, button hover, badge text |
| Accent | `#E6F99D` | Vulnerability tags, highlight backgrounds |

Surfaces and text use Tailwind's slate scale: `slate-900` for cards/topbar, `slate-800` for inputs and table headers, `slate-200` for body text, `slate-400` for muted text. Badge and alert components retain their own light backgrounds for contrast.

---

## Project Structure

```
RELIEF-DISTRIBUTION-SYSTEM/
├── app/
│   ├── __init__.py          # Application factory
│   ├── models/              # SQLAlchemy models
│   │   ├── user.py          # Users & RBAC
│   │   ├── beneficiary.py   # Beneficiaries & households
│   │   ├── inventory.py     # Warehouses, items, movements
│   │   ├── distribution.py  # Batches & records
│   │   ├── route.py         # Routes & stops
│   │   ├── audit.py         # Audit log
│   │   └── zone.py          # States, LGAs, distribution points
│   ├── routes/              # Flask blueprints
│   │   ├── auth.py          # Login / logout / profile
│   │   ├── main.py          # Dashboard
│   │   ├── admin.py         # User & system management
│   │   ├── beneficiary.py   # Beneficiary CRUD
│   │   ├── inventory.py     # Inventory management
│   │   ├── distribution.py  # Distribution batches & route opt.
│   │   ├── reports.py       # Summary reports & CSV export
│   │   ├── api.py           # Internal JSON API
│   │   └── errors.py        # HTTP error handlers
│   ├── utils/
│   │   ├── audit.py         # Audit trail helper
│   │   ├── helpers.py       # Shared utilities (timestamps, forms, queries, audit)
│   │   ├── nin_verifier.py  # NIN verification (simulated)
│   │   ├── route_optimizer.py # Nearest Neighbour algorithm
│   │   └── decorators.py    # RBAC decorators
│   ├── templates/           # Jinja2 HTML templates
│   └── static/              # CSS (compiled), JS, images
├── src/
│   └── input.css            # Tailwind CSS source (dark theme)
├── config.py                # Configuration classes
├── tailwind.config.js       # Tailwind config (theme, safelist)
├── package.json             # Node scripts (build:css, watch:css)
├── run.py                   # Development entry point
├── seed.py                  # Database seeder (states → distribution records)
├── test_pages.py            # Integration test script
└── requirements.txt
```

---

## Setup

### 1. Prerequisites

- Python 3.10 or higher
- MySQL 8.0 (WAMP64 or standalone)
- Node.js 18+ (for Tailwind CSS build)
- `pip`

### 2. Create the database

In MySQL:
```sql
CREATE DATABASE nrds_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Or via Python:
```python
import pymysql
conn = pymysql.connect(host='localhost', user='root', password='')
conn.cursor().execute('CREATE DATABASE IF NOT EXISTS nrds_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
conn.commit()
```

### 3. Configure environment

Copy `.env.example` to `.env` and update values:
```env
SECRET_KEY=your-long-secret-key
DATABASE_URL=mysql+pymysql://root:yourpassword@localhost/nrds_db
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
npm install
```

### 5. Build the CSS

The styles are written in Tailwind CSS (`src/input.css`) and compiled to
`app/static/css/style.css`.  Rebuild after changing the source:

```bash
npm run build:css       # one-off production build (minified)
npm run watch:css       # watch mode during development
```

### 6. Create tables

```bash
python -c "from app import create_app, db; app = create_app(); ctx = app.app_context(); ctx.push(); db.create_all()"
```

### 7. Seed the database

```bash
python seed.py
```

The seeder is idempotent and creates:
- 37 Nigerian states + FCT with coordinates
- 18 LGAs across 6 states
- 54 distribution points
- Admin + 5 sample staff users
- 6 warehouses with 15 item types each
- 100 beneficiaries with NIN hashing
- 2+ distribution batches
- 40+ distribution records with stock deductions and movements

### 8. Run the application

```bash
python run.py
```

Open your browser at: **http://localhost:5000**

### 9. (Optional) Run integration tests

```bash
python test_pages.py
```

Tests all 25 pages by logging in as admin and checking for HTTP errors.

---

## Default Login Credentials

| Username | Password | Role |
|---|---|---|
| `admin` | `Admin@1234` | Administrator |
| `field_kano` | `Password@123` | Field Officer |
| `warehouse_borno` | `Password@123` | Warehouse Staff |
| `logistics_01` | `Password@123` | Logistics Officer |
| `coordinator_01` | `Password@123` | Programme Coordinator |
| `partner_wfp` | `Password@123` | Partner Organisation |

---

## Key Features

### Beneficiary Management
- Register beneficiaries with 11-digit NIN validation
- NIN stored as SHA-256 hash; raw value never persisted
- NIN verification simulated against NIMC (replace with live API in production)
- Vulnerability flagging: elderly, disabled, pregnant, unaccompanied minor
- Household grouping with head-of-household designation
- Duplicate detection via NIN hash uniqueness constraint

### Inventory Management
- Multi-warehouse inventory across all 36 Nigerian states + FCT
- Receipt, dispatch, transfer, adjustment, and loss movement types
- Low-stock alerts that flag both threshold breaches and zero-stock items
- Stock-level progress bars with colour-coded status (red/amber/green)
- Full movement history per item with audit logging

### Distribution Management
- Two-step distribution recording (preview → confirm) to prevent errors
- Duplicate distribution guard (unique constraint on batch/beneficiary/item)
- Row-level locking (`with_for_update`) to prevent concurrent overdraw
- Distribution point dropdown pre-populated with all active points
- State filter narrows the dropdown client-side (no AJAX required)
- NIN lookup with masked display for privacy

### Route Optimisation
- Nearest Neighbour heuristic (O(n²)) using Haversine formula
- Open-path TSP variant (warehouse → last stop, no return)
- Saves ordered route to database with per-stop distances
- Generates route code and links to distribution batch

### Role-Based Access Control

| Role | Permissions |
|---|---|
| `admin` | Full system access |
| `programme_coord` | Manage batches, view reports |
| `warehouse` | Manage inventory |
| `field_officer` | Register beneficiaries, record distributions |
| `logistics` | Create routes |
| `partner` | Read-only reports |

### Audit Trail
- Every create/update/delete action is logged immutably
- Captures user, IP address, timestamp, entity type and ID
- Viewable in admin panel with action-based filtering

### Reporting
- Beneficiary summary by state, gender, and vulnerability
- Inventory report with low-stock highlighting and category grouping
- Distribution report with batch performance and completion rates
- Audit summary with paginated log viewer
- CSV export for all reports

---

## Production Deployment

For production (Ubuntu 22.04 + Nginx + Gunicorn):

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 "run:app"
```

Set `FLASK_ENV=production` and provide a strong `SECRET_KEY` in the environment.

See Chapter 3 of the project report for full hardware/software requirements.

---

## References

- Laporte, G. (1992). The traveling salesman problem. *EJOR*, 59(2), 231–247.
- Sinnott, R. W. (1984). Virtues of the Haversine. *Sky and Telescope*, 68(2), 159.
- Grinberg, M. (2018). *Flask Web Development* (2nd ed.). O'Reilly Media.
- Ferraiolo et al. (2001). Proposed NIST standard for RBAC. *ACM TISSEC*, 4(3).

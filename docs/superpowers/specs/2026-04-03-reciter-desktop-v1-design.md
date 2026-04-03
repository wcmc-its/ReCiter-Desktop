# ReCiter Desktop v1 — Design Spec

## Overview

Standalone web application for author name disambiguation. Institutions upload a researcher list (CSV/Excel), and the system retrieves candidate articles from PubMed, computes evidence features, and scores each article using pre-trained XGBoost models. Designed for librarians and research administrators — non-technical users who need clear guidance and no jargon.

**Target user**: Librarian or research administrator with no programming experience.

**Starting inputs**: Email domain, identity CSV (researchers), optionally PMIDs and accept/reject curation data.

**Output**: Scored article list per researcher, exportable as CSV.

---

## Architecture

Three-container Docker Compose setup:

```
docker compose up
  ├── frontend   (Next.js 14 App Router, port 3002)
  ├── api        (Python FastAPI, port 8090)
  └── db         (MariaDB 11, port 3306)
```

### Frontend (Next.js)
- Next.js 14 with App Router
- React, Tailwind CSS, shadcn/ui components
- SSE (Server-Sent Events) for real-time progress updates
- No authentication (local/institutional tool)

### Backend (FastAPI)
- Wraps existing Python modules: `core/`, `features/`, `models/`, `config/`
- Exposes REST + SSE endpoints
- Adaptive concurrent processing (multiple researchers in parallel)
- PubMed E-utilities integration with rate limiting

### Database (MariaDB)
- MariaDB 11, chosen for future compatibility with Publication Manager (which uses MariaDB/MySQL via Sequelize)
- Schema designed to align with Publication Manager tables for eventual integration

### Why This Stack
- **Next.js + FastAPI** over Streamlit: enables future integration with Publication Manager (Next.js/React), which will add curation workflows
- **MariaDB** over SQLite: same database engine as Publication Manager, enabling shared schema when curation is integrated
- **Docker Compose**: single `docker compose up` command — no Node.js/Python/MariaDB installation required for the end user

---

## User Flow

### Dashboard (Home)

Adaptive home screen that shows current state and guides the user to the next logical step.

**First visit**: Welcome message explaining what ReCiter Desktop does. Single button: "Set Up Your Institution."

**Progressive state**: Status cards in a row showing completion state:
- Institution: name + checkmark, or "Not configured"
- Researchers: count loaded, or "Not uploaded"
- Articles: count retrieved, or "Not yet retrieved"
- Scores: count scored, or "Not yet scored"

Each card highlights when it's the next step. A prominent action button always points to the logical next action.

**Education panel** (collapsible, always visible after setup): explains that the current model uses identity evidence only (25 features). Institutions that curate articles (accept/reject) unlock a more powerful 43-feature model. Links to Publication Manager as the future path for curation.

### 1. Institution Setup

Three-step flow on one page with a stepper:

**Step 1: Enter domain**
- Single text input: institution email domain (e.g., `fredhutch.org`)
- Optional: institution display name
- "Discover" button

**Step 2: Discovery (auto)**
- System queries PubMed using `{domain}[ad]` to find articles from that institution
- Progress stats stream via SSE: "Searching PubMed... 412 articles found... analyzing affiliations... 3 email domains discovered... 8 institutions identified..."
- Transitions automatically to Step 3 when done

**Step 3: Classify institutions**
- List of discovered institutions, each with a radio group: **Home / Collaborating / Skip**
- Pre-selected based on frequency (top entries as Home, rest as Collaborating), but user confirms each one
- Discovered email domains shown below with checkboxes (pre-checked, user can uncheck)
- "Save" button

Behind the scenes, the system generates ReCiter-compatible configuration (institution keywords, email suffixes, collaborating institution keywords) from the user's classifications. The keyword generation logic (removing stopwords, joining with pipe delimiters) is invisible to the user.

### 2. Researchers

**Upload zone**:
- Drag-and-drop area with clear instructions: "Upload your researcher list — a spreadsheet with one row per researcher. At minimum, include a unique ID, first name, and last name. Optional: email, department, doctoral year, ORCID."
- Accepts CSV, Excel (.xlsx, .xls), TSV
- "Download sample template" link with preview of expected format
- Note: "Column names are flexible — we recognize many common variations."

**Column mapping confirmation**:
- Auto-detect columns using alias matching (30+ variations: `emp_id`/`cwid`/`netid` → Person ID, `fname`/`firstname`/`first_name` → First Name, `phd_year`/`doctoral_year` → Doctoral Year, etc.)
- Table showing: checkbox | Your Column | → | Maps To | Sample Value
- "Select All" / "Deselect All" buttons
- Unmapped columns highlighted in amber with dropdown to assign or skip
- Each row individually toggleable

**Preview**: First few rows shown as they'll be imported, using mapped column headers.

**Gold standard detection**: If the CSV contains PMID + assertion columns, show a green banner: "Curation data detected — we found X accept/reject records. Import this data to enable the more accurate scoring model." Single checkbox to include/exclude.

**Import**: Progress bar → "47 researchers loaded"

### 3. Articles (Optional Pre-Upload)

For users who already have PMIDs, this page lets them upload before running the pipeline:

**Upload PMIDs**: CSV upload with person_id + pmid columns. Same column mapper UI pattern. Fetches article metadata from PubMed and links articles to researchers.

This step is optional. If skipped, the pipeline will search PubMed for each researcher automatically.

### 4. Processing Pipeline

Unified view for the full pipeline. If articles were pre-uploaded, the pipeline skips retrieval and starts at Match. Otherwise, it runs all four phases: Retrieve → Match → Analyze → Score.

**Overall progress bar** at top with running totals (researchers complete, articles found, articles scored).

**Phase legend**: color-coded phases:
- Blue: Retrieving from PubMed
- Purple: Identifying target authors
- Amber: Computing features
- Red: Scoring

**Per-researcher rows** in a table with columns: Researcher (clickable), UID, Articles, Status, Progress. Multiple researchers process concurrently at different phases.

**Completed section**: Collapsed to a single summary line ("12 researchers complete • 823 articles scored") with a "Show details" toggle. Expanded view shows each researcher with article count, score range, and "View articles" link.

**Queued section**: Dimmed rows showing researchers waiting to be processed.

### 5. Results (Article Detail View)

Accessed by clicking a researcher name from the pipeline or dashboard.

**Header**: Researcher name + UID + total article count.

**Threshold slider**: Adjustable score threshold with color gradient (red → amber → green). Shows count above/below threshold.

**Article table** with columns: Score (color-coded badge: green >70, amber 30-70, red <30), Title, Journal, Year, PubMed link.

Sortable by any column. Default sort: score descending.

**Export button**: Download CSV for this researcher or all researchers.

### 6. Export

Available from the Results view and the Dashboard (after scoring is complete).

- **Per-researcher CSV**: articles + scores for one researcher
- **All results CSV**: full dataset across all researchers
- Columns: person_id, pmid, title, journal, year, score, pubmed_url

---

## API Design

### Institution
| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/institution/discover` | Takes `{domain, year_range?}`, returns SSE stream of discovery progress, then discovered institutions and email domains |
| POST | `/api/institution/configure` | Saves home/collaborating classifications, generates config |
| GET | `/api/institution` | Returns current institution config |

### Researchers
| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/researchers/upload` | Multipart file upload, returns auto-detected column mappings |
| POST | `/api/researchers/import` | Takes confirmed mappings + file reference, imports to DB |
| GET | `/api/researchers` | List all researchers with stats |
| GET | `/api/researchers/{person_id}` | Single researcher detail |

### Articles
| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/articles/upload` | Upload PMID CSV, fetch metadata from PubMed |
| POST | `/api/articles/search` | Trigger PubMed search for all/selected researchers, SSE stream |
| GET | `/api/articles/{person_id}` | Articles for a researcher |

### Pipeline
| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/pipeline/run` | Full pipeline (retrieve → match → analyze → score), SSE stream with per-researcher progress |
| GET | `/api/pipeline/status` | Current pipeline state |

### Scores
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/scores/{person_id}` | Scored articles for a researcher |
| GET | `/api/scores/export` | CSV download (all or filtered by person_id, threshold) |

### Real-Time Updates
All long-running operations (institution discovery, article retrieval, pipeline) use **Server-Sent Events (SSE)** — the frontend subscribes and updates the UI in real time. No polling.

---

## Database Schema (MariaDB)

```sql
CREATE TABLE institution (
    config_key VARCHAR(255) PRIMARY KEY,
    config_value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE identity (
    person_id VARCHAR(128) PRIMARY KEY,
    first_name VARCHAR(128) NOT NULL,
    last_name VARCHAR(128) NOT NULL,
    middle_name VARCHAR(128) DEFAULT '',
    primary_email VARCHAR(256) DEFAULT '',
    primary_institution VARCHAR(256) DEFAULT '',
    department VARCHAR(256) DEFAULT '',
    title VARCHAR(256) DEFAULT '',
    orcid VARCHAR(64) DEFAULT '',
    bachelor_year INT DEFAULT 0,
    doctoral_year INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE article (
    pmid VARCHAR(20) PRIMARY KEY,
    title TEXT,
    journal VARCHAR(512),
    pub_year INT,
    doi VARCHAR(128),
    abstract TEXT,
    authors JSON,
    mesh_headings JSON,
    keywords JSON,
    grants JSON,
    publication_types JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE person_article (
    person_id VARCHAR(128),
    pmid VARCHAR(20),
    target_author_index INT DEFAULT -1,
    source ENUM('upload', 'search') DEFAULT 'search',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (person_id, pmid),
    FOREIGN KEY (person_id) REFERENCES identity(person_id) ON DELETE CASCADE,
    FOREIGN KEY (pmid) REFERENCES article(pmid) ON DELETE CASCADE
);

CREATE TABLE person_article_score (
    person_id VARCHAR(128),
    pmid VARCHAR(20),
    model_type ENUM('identityOnly', 'feedbackIdentity') NOT NULL,
    raw_score FLOAT,
    calibrated_score FLOAT,
    features JSON,
    scored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (person_id, pmid, model_type),
    FOREIGN KEY (person_id) REFERENCES identity(person_id) ON DELETE CASCADE,
    FOREIGN KEY (pmid) REFERENCES article(pmid) ON DELETE CASCADE
);

CREATE TABLE curation (
    person_id VARCHAR(128),
    pmid VARCHAR(20),
    assertion ENUM('ACCEPTED', 'REJECTED') NOT NULL,
    source ENUM('import', 'manual') DEFAULT 'import',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (person_id, pmid),
    FOREIGN KEY (person_id) REFERENCES identity(person_id) ON DELETE CASCADE,
    FOREIGN KEY (pmid) REFERENCES article(pmid) ON DELETE CASCADE
);
```

---

## Docker Compose

```yaml
version: "3.8"

services:
  frontend:
    build: ./frontend
    ports:
      - "3002:3000"
    depends_on:
      - api
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8090

  api:
    build: ./api
    ports:
      - "8090:8090"
    depends_on:
      db:
        condition: service_healthy
    volumes:
      - ./models:/app/models
      - ./data:/app/data
    environment:
      - DATABASE_URL=mysql+pymysql://reciter:reciter_local@db:3306/reciter_desktop
      - PUBMED_API_KEY=${PUBMED_API_KEY:-}

  db:
    image: mariadb:11
    ports:
      - "3306:3306"
    volumes:
      - db_data:/var/lib/mysql
    environment:
      MARIADB_ROOT_PASSWORD: root_local
      MARIADB_DATABASE: reciter_desktop
      MARIADB_USER: reciter
      MARIADB_PASSWORD: reciter_local
    healthcheck:
      test: ["CMD", "healthcheck.sh", "--connect", "--innodb_initialized"]
      interval: 5s
      timeout: 5s
      retries: 10

volumes:
  db_data:
```

Usage:
```bash
# Start everything
docker compose up

# With PubMed API key for faster retrieval (10 req/sec vs 3)
PUBMED_API_KEY=your_key docker compose up

# Open the app
open http://localhost:3002
```

---

## Directory Structure

```
ReCiter-Desktop/
├── frontend/                    # Next.js 14 app
│   ├── app/
│   │   ├── layout.tsx          # Root layout with sidebar
│   │   ├── page.tsx            # Dashboard home
│   │   ├── setup/
│   │   │   └── page.tsx        # Institution setup (3-step)
│   │   ├── researchers/
│   │   │   └── page.tsx        # Upload + column mapping
│   │   ├── articles/
│   │   │   └── page.tsx        # Retrieve articles
│   │   ├── pipeline/
│   │   │   └── page.tsx        # Processing pipeline view
│   │   └── results/
│   │       ├── page.tsx        # All researchers results
│   │       └── [personId]/
│   │           └── page.tsx    # Individual researcher articles
│   ├── components/
│   │   ├── sidebar.tsx         # Navigation sidebar
│   │   ├── status-card.tsx     # Dashboard status cards
│   │   ├── column-mapper.tsx   # CSV column mapping UI
│   │   ├── file-upload.tsx     # Drag-and-drop upload zone
│   │   ├── pipeline-row.tsx    # Per-researcher pipeline row
│   │   ├── score-badge.tsx     # Color-coded score badge
│   │   └── threshold-slider.tsx
│   ├── lib/
│   │   ├── api.ts              # API client
│   │   └── sse.ts              # SSE subscription helper
│   ├── Dockerfile
│   └── package.json
│
├── api/                         # FastAPI backend
│   ├── main.py                 # FastAPI app + CORS
│   ├── routers/
│   │   ├── institution.py      # Institution discovery + config
│   │   ├── researchers.py      # Upload, mapping, import
│   │   ├── articles.py         # PubMed retrieval
│   │   ├── pipeline.py         # Full pipeline orchestration
│   │   └── scores.py           # Score retrieval + export
│   ├── services/
│   │   ├── institution_discovery.py  # PubMed-based institution profiling
│   │   ├── column_mapper.py         # CSV column auto-detection
│   │   └── pipeline_runner.py       # Concurrent pipeline orchestration
│   ├── database.py             # SQLAlchemy + MariaDB connection
│   ├── models.py               # SQLAlchemy ORM models
│   ├── Dockerfile
│   └── requirements.txt
│
├── core/                        # Existing scoring engine (unchanged)
│   ├── config.py
│   ├── database.py             # Legacy SQLite (kept for reference)
│   ├── identity.py
│   ├── article.py
│   ├── target_author.py
│   ├── preprocessing.py
│   ├── scoring.py
│   ├── pubmed.py
│   └── feature_generator.py
│
├── features/                    # Existing feature calculators (unchanged)
│   ├── name_match.py
│   ├── email_match.py
│   ├── affiliation.py
│   ├── organization.py
│   ├── journal_subfield.py
│   ├── degree_year.py
│   ├── gender.py
│   ├── article_size.py
│   ├── author_count.py
│   └── feedback.py
│
├── models/                      # Pre-trained ML models
│   └── wcm/
│       ├── feedbackIdentityModel.joblib
│       ├── feedbackIdentityScaler.joblib
│       ├── feedbackIdentityCalibrator.joblib
│       ├── identityOnlyModel.joblib
│       ├── identityOnlyScaler.joblib
│       └── identityOnlyCalibrator.joblib
│
├── data/                        # Lookup tables
│   ├── name_frequency.json
│   ├── gender/Gender.json
│   └── science_metrix/
│
├── config/
│   └── default_config.yaml
│
├── docker-compose.yml
├── requirements.txt
└── CLAUDE.md
```

---

## Scoring Pipeline (Unchanged)

The existing scoring engine is preserved intact. The FastAPI backend calls these modules directly:

```
Feature rows (from feature_generator)
  → Select model: feedbackIdentity (if curations exist) or identityOnly
  → Preprocessing: derive features (firstNameFrequencyScore, etc.)
  → StandardScaler transform
  → XGBoost predict_proba → raw probability
  → IsotonicRegression calibration → 0-100 score
  → Return scored DataFrame
```

Model selection is invisible to the user — the system automatically uses the more powerful feedbackIdentity model if imported curation data exists for a researcher.

### Model Types
| Model | Features | When Used |
|-------|----------|-----------|
| identityOnly | 25 (19 base + 6 derived) | No curation data |
| feedbackIdentity | 43 (31 base + 12 derived) | Curation data imported |

### Critical Dependency
Models require **XGBoost 3.2.0** exactly. Cross-version loading causes score drift amplified by the isotonic calibrator step function.

---

## What's Out of Scope for v1

- **Curation workflow** — accepting/rejecting articles in the UI. Future integration with Publication Manager.
- **Local model training** — training on local curation data. Requires curation workflow first.
- **Scopus integration** — external institutions don't have Scopus API keys.
- **Authentication** — local/institutional tool, no login required.
- **Grant matching** — feature stub returns 0.0 (no lookup logic).
- **Relationship scoring** — co-author network analysis stubs return 0.0.

---

## Future: Publication Manager Integration

The architecture is designed for eventual integration with [Publication Manager](https://github.com/wcmc-its/reciter-publication-manager):

- **Same database engine** (MariaDB) — schemas can be aligned or shared
- **Same frontend framework** (Next.js/React) — curation UI can be added as new pages
- **FastAPI backend** provides scoring as a service that Publication Manager can call
- The education panel on the dashboard introduces this path to users

---

## Key Design Decisions

1. **Auto-discovery over manual config**: Institution setup uses PubMed mining (from `reciter_institution_setup.py`) rather than asking users to type keywords they don't understand.
2. **Column auto-detection over rigid templates**: CSV import uses 30+ alias mappings (from `run_external_validation.py`) with user confirmation, not a fixed schema.
3. **Home vs. Collaborating classification by user**: The distinction between home and collaborating institutions is fuzzy — only the user knows which is which. The system pre-selects based on frequency but requires user confirmation.
4. **Invisible model switching**: The system automatically uses the best available model. No jargon about "identityOnly" vs "feedbackIdentity" in the UI.
5. **SSE over polling**: Long-running operations stream progress in real time rather than requiring the frontend to poll.
6. **Concurrent adaptive processing**: Multiple researchers are processed in parallel with adaptive worker counts, matching the existing `run_external_validation.py` pattern.
7. **Docker Compose**: Single command to start everything — appropriate for non-technical users.

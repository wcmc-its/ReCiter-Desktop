# ReCiter Desktop v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Docker Compose web application (Next.js + FastAPI + MariaDB) that lets librarians upload researcher lists, discover/upload articles, and score them using pre-trained XGBoost models.

**Architecture:** Three-container Docker Compose: Next.js 14 frontend (port 3002) talks to a FastAPI Python backend (port 8090) which wraps the existing `core/` and `features/` scoring engine and persists data in MariaDB 11 (port 3306). Long-running operations use SSE for real-time progress.

**Tech Stack:** Next.js 14 (App Router), React, Tailwind CSS, shadcn/ui, FastAPI, SQLAlchemy, MariaDB 11, Docker Compose, XGBoost 3.2.0

**Spec:** `docs/superpowers/specs/2026-04-03-reciter-desktop-v1-design.md`

---

## Phase 1: Infrastructure & Database

### Task 1: Docker Compose + Project Scaffolding

**Files:**
- Create: `docker-compose.yml`
- Create: `api/Dockerfile`
- Create: `api/requirements.txt`
- Create: `api/__init__.py`
- Create: `api/main.py`
- Create: `frontend/Dockerfile`
- Create: `frontend/package.json`
- Modify: `.gitignore`

- [ ] **Step 1: Create docker-compose.yml**

```yaml
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
      - ./core:/app/core
      - ./features:/app/features
      - ./models:/app/models
      - ./data:/app/data
      - ./config:/app/config
    environment:
      - DATABASE_URL=mysql+pymysql://reciter:reciter_local@db:3306/reciter_desktop
      - PUBMED_API_KEY=${PUBMED_API_KEY:-}

  db:
    image: mariadb:11
    ports:
      - "3306:3306"
    volumes:
      - db_data:/var/lib/mysql
      - ./api/schema.sql:/docker-entrypoint-initdb.d/schema.sql
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

- [ ] **Step 2: Create api/requirements.txt**

```
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
sqlalchemy>=2.0.0
pymysql>=1.1.0
python-multipart>=0.0.6
pandas>=2.0.0
openpyxl>=3.1.0
xgboost==3.2.0
scikit-learn>=1.3.0
numpy>=1.24.0
scipy>=1.10.0
requests>=2.28.0
pyyaml>=6.0
joblib>=1.3.0
python-Levenshtein>=0.21.0
sse-starlette>=1.6.0
```

- [ ] **Step 3: Create api/Dockerfile**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/api
# core/, features/, models/, data/, config/ are mounted as volumes

ENV PYTHONPATH=/app

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8090"]
```

- [ ] **Step 4: Create api/__init__.py (empty) and api/main.py skeleton**

```python
# api/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="ReCiter Desktop API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3002"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check():
    return {"status": "ok"}
```

- [ ] **Step 5: Initialize Next.js frontend**

Run:
```bash
cd /Users/paulalbert/Dropbox/GitHub/ReCiter-Desktop
npx create-next-app@14 frontend --typescript --tailwind --eslint --app --src-dir=false --import-alias="@/*" --no-turbo
```

- [ ] **Step 6: Create frontend/Dockerfile**

```dockerfile
FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

CMD ["npm", "start"]
```

- [ ] **Step 7: Update .gitignore**

Append to existing `.gitignore`:
```
# Docker
db_data/

# Frontend
frontend/node_modules/
frontend/.next/

# API
api/__pycache__/
api/*.pyc

# Brainstorming artifacts
.superpowers/
```

- [ ] **Step 8: Verify Docker Compose starts**

Run: `docker compose up --build -d db`
Then: `docker compose exec db mariadb -u reciter -preciter_local reciter_desktop -e "SELECT 1"`
Expected: `1` returned, confirming MariaDB is running.

Run: `docker compose down`

- [ ] **Step 9: Commit**

```bash
git add docker-compose.yml api/Dockerfile api/requirements.txt api/__init__.py api/main.py frontend/ .gitignore
git commit -m "Scaffold project: Docker Compose, FastAPI, Next.js"
```

---

### Task 2: Database Schema + SQLAlchemy Models

**Files:**
- Create: `api/schema.sql`
- Create: `api/database.py`
- Create: `api/models.py`
- Test: `api/tests/test_models.py`

- [ ] **Step 1: Create api/schema.sql**

```sql
CREATE TABLE IF NOT EXISTS institution (
    config_key VARCHAR(255) PRIMARY KEY,
    config_value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS identity (
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

CREATE TABLE IF NOT EXISTS article (
    pmid VARCHAR(20) PRIMARY KEY,
    title TEXT,
    journal VARCHAR(512),
    pub_year INT,
    doi VARCHAR(128),
    abstract_text TEXT,
    authors JSON,
    mesh_headings JSON,
    keywords JSON,
    grants JSON,
    publication_types JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS person_article (
    person_id VARCHAR(128),
    pmid VARCHAR(20),
    target_author_index INT DEFAULT -1,
    source ENUM('upload', 'search') DEFAULT 'search',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (person_id, pmid),
    FOREIGN KEY (person_id) REFERENCES identity(person_id) ON DELETE CASCADE,
    FOREIGN KEY (pmid) REFERENCES article(pmid) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS person_article_score (
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

CREATE TABLE IF NOT EXISTS curation (
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

- [ ] **Step 2: Create api/database.py**

```python
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "mysql+pymysql://reciter:reciter_local@localhost:3306/reciter_desktop",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 3: Create api/models.py**

```python
from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    Float,
    Enum,
    ForeignKey,
    JSON,
    TIMESTAMP,
)
from sqlalchemy.sql import func
from api.database import Base


class Institution(Base):
    __tablename__ = "institution"

    config_key = Column(String(255), primary_key=True)
    config_value = Column(Text, nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())


class Identity(Base):
    __tablename__ = "identity"

    person_id = Column(String(128), primary_key=True)
    first_name = Column(String(128), nullable=False)
    last_name = Column(String(128), nullable=False)
    middle_name = Column(String(128), default="")
    primary_email = Column(String(256), default="")
    primary_institution = Column(String(256), default="")
    department = Column(String(256), default="")
    title = Column(String(256), default="")
    orcid = Column(String(64), default="")
    bachelor_year = Column(Integer, default=0)
    doctoral_year = Column(Integer, default=0)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())


class Article(Base):
    __tablename__ = "article"

    pmid = Column(String(20), primary_key=True)
    title = Column(Text)
    journal = Column(String(512))
    pub_year = Column(Integer)
    doi = Column(String(128))
    abstract_text = Column(Text)
    authors = Column(JSON)
    mesh_headings = Column(JSON)
    keywords = Column(JSON)
    grants = Column(JSON)
    publication_types = Column(JSON)
    created_at = Column(TIMESTAMP, server_default=func.now())


class PersonArticle(Base):
    __tablename__ = "person_article"

    person_id = Column(
        String(128), ForeignKey("identity.person_id", ondelete="CASCADE"), primary_key=True
    )
    pmid = Column(
        String(20), ForeignKey("article.pmid", ondelete="CASCADE"), primary_key=True
    )
    target_author_index = Column(Integer, default=-1)
    source = Column(Enum("upload", "search"), default="search")
    created_at = Column(TIMESTAMP, server_default=func.now())


class PersonArticleScore(Base):
    __tablename__ = "person_article_score"

    person_id = Column(
        String(128), ForeignKey("identity.person_id", ondelete="CASCADE"), primary_key=True
    )
    pmid = Column(
        String(20), ForeignKey("article.pmid", ondelete="CASCADE"), primary_key=True
    )
    model_type = Column(
        Enum("identityOnly", "feedbackIdentity"), primary_key=True, nullable=False
    )
    raw_score = Column(Float)
    calibrated_score = Column(Float)
    features = Column(JSON)
    scored_at = Column(TIMESTAMP, server_default=func.now())


class Curation(Base):
    __tablename__ = "curation"

    person_id = Column(
        String(128), ForeignKey("identity.person_id", ondelete="CASCADE"), primary_key=True
    )
    pmid = Column(
        String(20), ForeignKey("article.pmid", ondelete="CASCADE"), primary_key=True
    )
    assertion = Column(Enum("ACCEPTED", "REJECTED"), nullable=False)
    source = Column(Enum("import", "manual"), default="import")
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
```

- [ ] **Step 4: Write test for models**

Create `api/tests/__init__.py` (empty) and `api/tests/test_models.py`:

```python
from api.models import Identity, Article, PersonArticle, PersonArticleScore, Curation, Institution


def test_identity_columns():
    """Verify Identity model has all expected columns."""
    cols = {c.name for c in Identity.__table__.columns}
    assert "person_id" in cols
    assert "first_name" in cols
    assert "last_name" in cols
    assert "middle_name" in cols
    assert "primary_email" in cols
    assert "primary_institution" in cols
    assert "department" in cols
    assert "title" in cols
    assert "orcid" in cols
    assert "doctoral_year" in cols
    assert "bachelor_year" in cols


def test_article_columns():
    cols = {c.name for c in Article.__table__.columns}
    assert "pmid" in cols
    assert "title" in cols
    assert "journal" in cols
    assert "pub_year" in cols
    assert "authors" in cols
    assert "mesh_headings" in cols


def test_person_article_composite_pk():
    pk_cols = [c.name for c in PersonArticle.__table__.primary_key.columns]
    assert "person_id" in pk_cols
    assert "pmid" in pk_cols


def test_score_composite_pk():
    pk_cols = [c.name for c in PersonArticleScore.__table__.primary_key.columns]
    assert "person_id" in pk_cols
    assert "pmid" in pk_cols
    assert "model_type" in pk_cols
```

- [ ] **Step 5: Run tests**

Run: `cd /Users/paulalbert/Dropbox/GitHub/ReCiter-Desktop && python -m pytest api/tests/test_models.py -v`
Expected: All 4 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add api/schema.sql api/database.py api/models.py api/tests/
git commit -m "Add MariaDB schema and SQLAlchemy ORM models"
```

---

## Phase 2: Backend Services & API

### Task 3: Column Mapper Service

**Files:**
- Create: `api/services/column_mapper.py`
- Create: `api/services/__init__.py`
- Test: `api/tests/test_column_mapper.py`

- [ ] **Step 1: Write failing tests**

```python
# api/tests/test_column_mapper.py
from api.services.column_mapper import detect_mappings, CANONICAL_FIELDS


def test_exact_match():
    headers = ["person_id", "first_name", "last_name"]
    mappings = detect_mappings(headers)
    assert mappings["person_id"] == "person_id"
    assert mappings["first_name"] == "first_name"
    assert mappings["last_name"] == "last_name"


def test_alias_match():
    headers = ["emp_id", "fname", "lname", "phd_year"]
    mappings = detect_mappings(headers)
    assert mappings["emp_id"] == "person_id"
    assert mappings["fname"] == "first_name"
    assert mappings["lname"] == "last_name"
    assert mappings["phd_year"] == "doctoral_year"


def test_unmapped_columns():
    headers = ["person_id", "first_name", "last_name", "favorite_color"]
    mappings = detect_mappings(headers)
    assert mappings.get("favorite_color") is None


def test_gold_standard_detection():
    headers = ["person_id", "first_name", "last_name", "pmid", "assertion"]
    mappings = detect_mappings(headers)
    assert mappings["pmid"] == "pmid"
    assert mappings["assertion"] == "assertion"


def test_title_and_institution_aliases():
    headers = ["uid", "fname", "lname", "rank", "primary_institution"]
    mappings = detect_mappings(headers)
    assert mappings["rank"] == "title"
    assert mappings["primary_institution"] == "primary_institution"


def test_case_insensitive():
    headers = ["Person_ID", "First_Name", "Last_Name"]
    mappings = detect_mappings(headers)
    assert mappings["Person_ID"] == "person_id"


def test_canonical_fields_has_required():
    assert "person_id" in CANONICAL_FIELDS
    assert "first_name" in CANONICAL_FIELDS
    assert "last_name" in CANONICAL_FIELDS
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest api/tests/test_column_mapper.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'api.services'`

- [ ] **Step 3: Implement column mapper**

Create `api/services/__init__.py` (empty) and:

```python
# api/services/column_mapper.py
"""Auto-detect CSV column mappings using alias matching."""

CANONICAL_FIELDS = [
    "person_id",
    "first_name",
    "last_name",
    "middle_name",
    "primary_email",
    "primary_institution",
    "department",
    "title",
    "orcid",
    "bachelor_year",
    "doctoral_year",
    "pmid",
    "assertion",
]

# Maps normalized alias → canonical field name
_ALIASES: dict[str, str] = {
    # person_id
    "personid": "person_id",
    "person_id": "person_id",
    "uid": "person_id",
    "userid": "person_id",
    "employeeid": "person_id",
    "empid": "person_id",
    "emp_id": "person_id",
    "cwid": "person_id",
    "netid": "person_id",
    "id": "person_id",
    # first_name
    "firstname": "first_name",
    "first_name": "first_name",
    "fname": "first_name",
    "first": "first_name",
    "givenname": "first_name",
    # last_name
    "lastname": "last_name",
    "last_name": "last_name",
    "lname": "last_name",
    "last": "last_name",
    "surname": "last_name",
    "familyname": "last_name",
    # middle_name
    "middlename": "middle_name",
    "middle_name": "middle_name",
    "middleinitial": "middle_name",
    "middle_initial": "middle_name",
    "middle": "middle_name",
    "mi": "middle_name",
    "middleinit": "middle_name",
    # primary_email
    "email": "primary_email",
    "primaryemail": "primary_email",
    "primary_email": "primary_email",
    "emailaddress": "primary_email",
    "email_address": "primary_email",
    # primary_institution
    "institution": "primary_institution",
    "primaryinstitution": "primary_institution",
    "primary_institution": "primary_institution",
    # department
    "department": "department",
    "dept": "department",
    "division": "department",
    "organizationalunit": "department",
    "organizational_unit": "department",
    "org_unit": "department",
    # title
    "title": "title",
    "rank": "title",
    "academictitle": "title",
    "academic_title": "title",
    "jobtitle": "title",
    "job_title": "title",
    "position": "title",
    # orcid
    "orcid": "orcid",
    "orcidid": "orcid",
    "orcid_id": "orcid",
    "orcidurl": "orcid",
    "orcid_url": "orcid",
    # bachelor_year
    "bacheloryear": "bachelor_year",
    "bachelor_year": "bachelor_year",
    "bsyear": "bachelor_year",
    "bs_year": "bachelor_year",
    # doctoral_year
    "doctoralyear": "doctoral_year",
    "doctoral_year": "doctoral_year",
    "phdyear": "doctoral_year",
    "phd_year": "doctoral_year",
    "degreeyear": "doctoral_year",
    "degree_year": "doctoral_year",
    # gold standard
    "pmid": "pmid",
    "pubmedid": "pmid",
    "pubmed_id": "pmid",
    "assertion": "assertion",
    "assertionstatus": "assertion",
    "assertion_status": "assertion",
    "userassertion": "assertion",
    "user_assertion": "assertion",
    "status": "assertion",
}


def _normalize(header: str) -> str:
    """Lowercase, strip whitespace, remove hyphens/dots/spaces between words."""
    return header.lower().strip().replace("-", "").replace(".", "").replace(" ", "")


def detect_mappings(headers: list[str]) -> dict[str, str | None]:
    """
    Given a list of CSV headers, return a dict mapping each header to its
    canonical field name, or None if unmapped.

    Returns: {original_header: canonical_field_or_None}
    """
    used_fields: set[str] = set()
    result: dict[str, str | None] = {}

    for header in headers:
        normalized = _normalize(header)
        canonical = _ALIASES.get(normalized)
        if canonical and canonical not in used_fields:
            result[header] = canonical
            used_fields.add(canonical)
        else:
            result[header] = None

    return result
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest api/tests/test_column_mapper.py -v`
Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add api/services/ api/tests/test_column_mapper.py
git commit -m "Add column mapper service with alias auto-detection"
```

---

### Task 4: Institution Discovery Service

**Files:**
- Create: `api/services/institution_discovery.py`
- Test: `api/tests/test_institution_discovery.py`

- [ ] **Step 1: Write failing tests**

```python
# api/tests/test_institution_discovery.py
from api.services.institution_discovery import (
    generate_keywords,
    extract_email_domains,
    extract_institution_names,
)


def test_generate_keywords():
    result = generate_keywords("Fred Hutchinson Cancer Center")
    assert "fred" in result
    assert "hutchinson" in result
    assert "cancer" in result
    assert "|" in result


def test_generate_keywords_removes_stopwords():
    result = generate_keywords("University of Washington School of Medicine")
    assert "of" not in result.split("|")
    assert "washington" in result


def test_extract_email_domains_from_affiliations():
    affiliations = [
        "Fred Hutchinson Cancer Center, jsmith@fredhutch.org",
        "University of Washington, jdoe@uw.edu",
        "Fred Hutchinson Cancer Center, bchen@fredhutch.org",
    ]
    domains = extract_email_domains(affiliations)
    assert ("fredhutch.org", 2) in [(d, c) for d, c in domains]


def test_extract_institution_names():
    affiliations = [
        "Department of Medicine, Fred Hutchinson Cancer Center, Seattle, WA, USA",
        "Division of Oncology, Fred Hutchinson Cancer Center, Seattle, WA, USA",
        "Department of Biostatistics, University of Washington, Seattle, WA, USA",
    ]
    institutions = extract_institution_names(affiliations)
    names = [name for name, count in institutions]
    assert any("Fred Hutchinson" in n for n in names)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest api/tests/test_institution_discovery.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement institution discovery service**

```python
# api/services/institution_discovery.py
"""
Auto-discover institutional configuration from PubMed.
Ported from reciter_institution_setup.py.
"""
import re
import time
import logging
from collections import Counter
from typing import AsyncGenerator
import requests
from xml.etree import ElementTree

logger = logging.getLogger(__name__)

PUBMED_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

STOPWORDS = {"of", "the", "for", "and", "to", "in", "at", "on", "a", "an"}
GENERIC_INSTITUTION_WORDS = {
    "university", "hospital", "center", "centre", "institute",
    "college", "school", "department", "division", "faculty",
    "program", "programme", "laboratory", "lab",
}
LOCATION_PATTERNS = re.compile(
    r"^\d{5}|USA$|^[A-Z]{2}$|^\d|United States|Canada|UK|China|Japan|Germany|France"
)


def generate_keywords(institution_name: str) -> str:
    """Convert institution name to pipe-delimited keywords for ReCiter config."""
    words = institution_name.lower().split()
    filtered = [
        w for w in words
        if w not in STOPWORDS and w not in GENERIC_INSTITUTION_WORDS
    ]
    if not filtered:
        filtered = [w for w in words if w not in STOPWORDS]
    return "|".join(filtered[:4])


def extract_email_domains(affiliations: list[str]) -> list[tuple[str, int]]:
    """Extract email domains from affiliation strings, ranked by frequency."""
    domain_counts: Counter = Counter()
    email_re = re.compile(r"[\w.+-]+@([\w-]+\.[\w.-]+)")
    for aff in affiliations:
        for match in email_re.finditer(aff):
            domain = match.group(1).lower()
            domain_counts[domain] += 1
    return domain_counts.most_common()


def extract_institution_names(affiliations: list[str]) -> list[tuple[str, int]]:
    """Extract institution-like names from affiliation strings, ranked by frequency."""
    name_counts: Counter = Counter()
    for aff in affiliations:
        segments = [s.strip() for s in aff.split(",")]
        for seg in segments:
            if LOCATION_PATTERNS.search(seg):
                continue
            if "@" in seg:
                continue
            seg_lower = seg.lower()
            has_inst_word = any(w in seg_lower for w in GENERIC_INSTITUTION_WORDS)
            if has_inst_word and len(seg) > 5:
                name_counts[seg] += 1
    return name_counts.most_common()


def pubmed_search(domain: str, year_range: str | None = None,
                  api_key: str | None = None) -> list[str]:
    """Search PubMed for articles with the given domain in affiliations."""
    query = f"{domain}[ad]"
    if year_range:
        query += f" AND {year_range}[dp]"
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": 500,
        "retmode": "json",
    }
    if api_key:
        params["api_key"] = api_key
    resp = requests.get(PUBMED_ESEARCH, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("esearchresult", {}).get("idlist", [])


def pubmed_fetch_affiliations(pmids: list[str],
                              api_key: str | None = None) -> list[str]:
    """Fetch author affiliations for a list of PMIDs."""
    all_affiliations: list[str] = []
    batch_size = 100
    for i in range(0, len(pmids), batch_size):
        batch = pmids[i : i + batch_size]
        params = {
            "db": "pubmed",
            "id": ",".join(batch),
            "rettype": "xml",
            "retmode": "xml",
        }
        if api_key:
            params["api_key"] = api_key
        resp = requests.get(PUBMED_EFETCH, params=params, timeout=60)
        resp.raise_for_status()
        root = ElementTree.fromstring(resp.text)
        for article in root.findall(".//PubmedArticle"):
            for author in article.findall(".//Author"):
                for aff in author.findall(".//Affiliation"):
                    if aff.text:
                        all_affiliations.append(aff.text)
        if i + batch_size < len(pmids):
            time.sleep(0.4)
    return all_affiliations


async def discover_institution(
    domain: str,
    year_range: str | None = None,
    api_key: str | None = None,
) -> AsyncGenerator[dict, None]:
    """
    Generator that yields progress events during institution discovery.
    Each event is a dict with 'type' and data fields.
    """
    yield {"type": "status", "message": f"Searching PubMed for {domain}..."}

    pmids = pubmed_search(domain, year_range, api_key)
    yield {"type": "status", "message": f"{len(pmids)} articles found"}

    if not pmids:
        yield {"type": "complete", "institutions": [], "email_domains": []}
        return

    yield {"type": "status", "message": "Analyzing affiliations..."}
    affiliations = pubmed_fetch_affiliations(pmids, api_key)

    email_domains = extract_email_domains(affiliations)
    yield {
        "type": "status",
        "message": f"{len(email_domains)} email domains discovered",
    }

    institutions = extract_institution_names(affiliations)
    yield {
        "type": "status",
        "message": f"{len(institutions)} institutions identified",
    }

    yield {
        "type": "complete",
        "institutions": [
            {"name": name, "count": count, "keywords": generate_keywords(name)}
            for name, count in institutions[:20]
        ],
        "email_domains": [
            {"domain": d, "count": c} for d, c in email_domains[:10]
        ],
    }
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest api/tests/test_institution_discovery.py -v`
Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add api/services/institution_discovery.py api/tests/test_institution_discovery.py
git commit -m "Add institution discovery service with PubMed mining"
```

---

### Task 5: Institution API Endpoints

**Files:**
- Create: `api/routers/__init__.py`
- Create: `api/routers/institution.py`
- Modify: `api/main.py`

- [ ] **Step 1: Create api/routers/institution.py**

```python
# api/routers/institution.py
import json
import os
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.database import get_db
from api.models import Institution
from api.services.institution_discovery import discover_institution, generate_keywords

router = APIRouter(prefix="/api/institution", tags=["institution"])


class DiscoverRequest(BaseModel):
    domain: str
    year_range: str | None = None


class InstitutionClassification(BaseModel):
    name: str
    classification: str  # "home", "collaborating", "skip"
    keywords: str


class ConfigureRequest(BaseModel):
    institutions: list[InstitutionClassification]
    email_domains: list[str]
    institution_label: str


@router.post("/discover")
async def discover(req: DiscoverRequest):
    api_key = os.environ.get("PUBMED_API_KEY")

    async def event_stream():
        async for event in discover_institution(req.domain, req.year_range, api_key):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/configure")
def configure(req: ConfigureRequest, db: Session = Depends(get_db)):
    home_keywords = []
    collab_keywords = []
    for inst in req.institutions:
        if inst.classification == "home":
            home_keywords.append(inst.keywords)
        elif inst.classification == "collaborating":
            collab_keywords.append(inst.keywords)

    config_pairs = {
        "institution_label": req.institution_label,
        "email_suffixes": json.dumps(
            ["@" + d if not d.startswith("@") else d for d in req.email_domains]
        ),
        "home_institution_keywords": json.dumps(home_keywords),
        "collaborating_institution_keywords": json.dumps(collab_keywords),
    }

    for key, value in config_pairs.items():
        existing = db.query(Institution).filter_by(config_key=key).first()
        if existing:
            existing.config_value = value
        else:
            db.add(Institution(config_key=key, config_value=value))
    db.commit()

    return {"status": "ok", "config_keys": list(config_pairs.keys())}


@router.get("")
def get_config(db: Session = Depends(get_db)):
    rows = db.query(Institution).all()
    config = {}
    for row in rows:
        try:
            config[row.config_key] = json.loads(row.config_value)
        except (json.JSONDecodeError, TypeError):
            config[row.config_key] = row.config_value
    return config
```

- [ ] **Step 2: Register router in api/main.py**

```python
# api/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import institution

app = FastAPI(title="ReCiter Desktop API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3002"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(institution.router)


@app.get("/api/health")
def health_check():
    return {"status": "ok"}
```

- [ ] **Step 3: Commit**

```bash
git add api/routers/ api/main.py
git commit -m "Add institution discovery and configuration endpoints"
```

---

### Task 6: Researcher API Endpoints

**Files:**
- Create: `api/routers/researchers.py`
- Modify: `api/main.py`

- [ ] **Step 1: Create api/routers/researchers.py**

```python
# api/routers/researchers.py
import io
import json
import tempfile
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func
import pandas as pd

from api.database import get_db
from api.models import Identity, PersonArticle, PersonArticleScore, Curation
from api.services.column_mapper import detect_mappings

router = APIRouter(prefix="/api/researchers", tags=["researchers"])


class ColumnMapping(BaseModel):
    original: str
    canonical: str | None


class ImportRequest(BaseModel):
    mappings: list[ColumnMapping]
    file_id: str
    import_gold_standard: bool = False


# In-memory temp store for uploaded files (replaced by proper storage later if needed)
_uploaded_files: dict[str, bytes] = {}


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    content = await file.read()
    file_id = f"upload_{id(content)}"
    _uploaded_files[file_id] = content

    # Parse headers
    filename = file.filename or "upload.csv"
    if filename.endswith((".xlsx", ".xls")):
        df = pd.read_excel(io.BytesIO(content), nrows=5)
    elif filename.endswith(".tsv"):
        df = pd.read_csv(io.BytesIO(content), sep="\t", nrows=5)
    else:
        df = pd.read_csv(io.BytesIO(content), nrows=5)

    headers = list(df.columns)
    mappings = detect_mappings(headers)
    preview_rows = df.head(3).fillna("").to_dict(orient="records")

    has_gold_standard = (
        mappings.get(next((h for h in headers if mappings.get(h) == "pmid"), "")) == "pmid"
        and mappings.get(next((h for h in headers if mappings.get(h) == "assertion"), "")) == "assertion"
    )
    gold_standard_count = 0
    if has_gold_standard:
        if filename.endswith((".xlsx", ".xls")):
            full_df = pd.read_excel(io.BytesIO(content))
        elif filename.endswith(".tsv"):
            full_df = pd.read_csv(io.BytesIO(content), sep="\t")
        else:
            full_df = pd.read_csv(io.BytesIO(content))
        assertion_col = next(h for h in headers if mappings.get(h) == "assertion")
        gold_standard_count = int(full_df[assertion_col].notna().sum())

    return {
        "file_id": file_id,
        "filename": filename,
        "row_count": len(pd.read_csv(io.BytesIO(content))) if not filename.endswith((".xlsx", ".xls")) else len(pd.read_excel(io.BytesIO(content))),
        "mappings": [
            {"original": h, "canonical": mappings.get(h), "sample": str(preview_rows[0].get(h, "")) if preview_rows else ""}
            for h in headers
        ],
        "preview": preview_rows,
        "has_gold_standard": has_gold_standard,
        "gold_standard_count": gold_standard_count,
    }


@router.post("/import")
def import_researchers(req: ImportRequest, db: Session = Depends(get_db)):
    content = _uploaded_files.get(req.file_id)
    if not content:
        raise HTTPException(status_code=404, detail="Upload not found. Please re-upload the file.")

    # Build column rename map: original → canonical
    rename_map = {m.original: m.canonical for m in req.mappings if m.canonical}

    # Read full file
    try:
        df = pd.read_excel(io.BytesIO(content))
    except Exception:
        try:
            df = pd.read_csv(io.BytesIO(content), sep="\t")
        except Exception:
            df = pd.read_csv(io.BytesIO(content))

    df = df.rename(columns=rename_map)
    df = df.fillna("")

    # Import identities
    identity_count = 0
    for _, row in df.iterrows():
        pid = str(row.get("person_id", "")).strip()
        fname = str(row.get("first_name", "")).strip()
        lname = str(row.get("last_name", "")).strip()
        if not pid or not fname or not lname:
            continue

        existing = db.query(Identity).filter_by(person_id=pid).first()
        if existing:
            existing.first_name = fname
            existing.last_name = lname
            existing.middle_name = str(row.get("middle_name", "")).strip()
            existing.primary_email = str(row.get("primary_email", "")).strip()
            existing.primary_institution = str(row.get("primary_institution", "")).strip()
            existing.department = str(row.get("department", "")).strip()
            existing.title = str(row.get("title", "")).strip()
            existing.orcid = str(row.get("orcid", "")).strip()
            existing.bachelor_year = int(row.get("bachelor_year", 0) or 0)
            existing.doctoral_year = int(row.get("doctoral_year", 0) or 0)
        else:
            db.add(Identity(
                person_id=pid,
                first_name=fname,
                last_name=lname,
                middle_name=str(row.get("middle_name", "")).strip(),
                primary_email=str(row.get("primary_email", "")).strip(),
                primary_institution=str(row.get("primary_institution", "")).strip(),
                department=str(row.get("department", "")).strip(),
                title=str(row.get("title", "")).strip(),
                orcid=str(row.get("orcid", "")).strip(),
                bachelor_year=int(row.get("bachelor_year", 0) or 0),
                doctoral_year=int(row.get("doctoral_year", 0) or 0),
            ))
        identity_count += 1

    # Import gold standard if requested
    curation_count = 0
    if req.import_gold_standard and "pmid" in df.columns and "assertion" in df.columns:
        for _, row in df.iterrows():
            pid = str(row.get("person_id", "")).strip()
            pmid = str(row.get("pmid", "")).strip()
            assertion = str(row.get("assertion", "")).strip().upper()
            if pid and pmid and assertion in ("ACCEPTED", "REJECTED"):
                existing_cur = db.query(Curation).filter_by(
                    person_id=pid, pmid=pmid
                ).first()
                if not existing_cur:
                    db.add(Curation(
                        person_id=pid, pmid=pmid,
                        assertion=assertion, source="import",
                    ))
                    curation_count += 1

    db.commit()
    del _uploaded_files[req.file_id]

    return {
        "identity_count": identity_count,
        "curation_count": curation_count,
    }


@router.get("")
def list_researchers(db: Session = Depends(get_db)):
    identities = db.query(Identity).order_by(Identity.last_name).all()

    # Get article counts per person
    article_counts = dict(
        db.query(PersonArticle.person_id, func.count(PersonArticle.pmid))
        .group_by(PersonArticle.person_id)
        .all()
    )

    # Get score counts per person
    score_counts = dict(
        db.query(PersonArticleScore.person_id, func.count(PersonArticleScore.pmid))
        .group_by(PersonArticleScore.person_id)
        .all()
    )

    return [
        {
            "person_id": i.person_id,
            "first_name": i.first_name,
            "last_name": i.last_name,
            "middle_name": i.middle_name,
            "department": i.department,
            "title": i.title,
            "article_count": article_counts.get(i.person_id, 0),
            "score_count": score_counts.get(i.person_id, 0),
        }
        for i in identities
    ]


@router.get("/{person_id}")
def get_researcher(person_id: str, db: Session = Depends(get_db)):
    identity = db.query(Identity).filter_by(person_id=person_id).first()
    if not identity:
        raise HTTPException(status_code=404, detail="Researcher not found")
    return {
        "person_id": identity.person_id,
        "first_name": identity.first_name,
        "last_name": identity.last_name,
        "middle_name": identity.middle_name,
        "primary_email": identity.primary_email,
        "primary_institution": identity.primary_institution,
        "department": identity.department,
        "title": identity.title,
        "orcid": identity.orcid,
        "bachelor_year": identity.bachelor_year,
        "doctoral_year": identity.doctoral_year,
    }
```

- [ ] **Step 2: Register router in api/main.py**

Add to imports and include:
```python
from api.routers import institution, researchers

app.include_router(researchers.router)
```

- [ ] **Step 3: Commit**

```bash
git add api/routers/researchers.py api/main.py
git commit -m "Add researcher upload, column mapping, and import endpoints"
```

---

### Task 7: Pipeline Runner Service

**Files:**
- Create: `api/services/pipeline_runner.py`

- [ ] **Step 1: Create pipeline runner**

```python
# api/services/pipeline_runner.py
"""
Orchestrates the scoring pipeline for multiple researchers concurrently.
Wraps existing core/ and features/ modules.
"""
import asyncio
import json
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from typing import AsyncGenerator

from sqlalchemy.orm import Session

from api.database import SessionLocal
from api.models import (
    Identity, Article, PersonArticle, PersonArticleScore, Curation,
)

# Add project root to path so core/ and features/ are importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from core.identity import Identity as CoreIdentity
from core.article import Article as CoreArticle, Author
from core.pubmed import efetch, esearch
from core.target_author import find_target_author
from core.feature_generator import generate_features
from core.scoring import score_articles
from core.config import load_config

logger = logging.getLogger(__name__)

# Adaptive worker pool
MAX_WORKERS = min(4, (os.cpu_count() or 2))


def _db_identity_to_core(db_identity: Identity) -> CoreIdentity:
    """Convert SQLAlchemy Identity to core.identity.Identity dataclass."""
    return CoreIdentity(
        person_id=db_identity.person_id,
        first_name=db_identity.first_name,
        last_name=db_identity.last_name,
        middle_name=db_identity.middle_name or "",
        primary_email=db_identity.primary_email or "",
        primary_institution=db_identity.primary_institution or "",
        department=db_identity.department or "",
        title=db_identity.title or "",
        orcid=db_identity.orcid or "",
        bachelor_year=db_identity.bachelor_year or 0,
        doctoral_year=db_identity.doctoral_year or 0,
    )


def _db_article_to_core(db_article: Article) -> CoreArticle:
    """Convert SQLAlchemy Article to core.article.Article dataclass."""
    authors = []
    if db_article.authors:
        for a in db_article.authors:
            authors.append(Author(
                first_name=a.get("first_name", ""),
                last_name=a.get("last_name", ""),
                initials=a.get("initials", ""),
                affiliation=a.get("affiliation", ""),
                orcid=a.get("orcid", ""),
            ))
    return CoreArticle(
        pmid=db_article.pmid,
        title=db_article.title or "",
        journal=db_article.journal or "",
        pub_year=db_article.pub_year or 0,
        authors=authors,
        doi=db_article.doi or "",
        abstract=db_article.abstract_text or "",
        mesh_headings=db_article.mesh_headings or [],
        keywords=db_article.keywords or [],
        grants=db_article.grants or [],
        publication_types=db_article.publication_types or [],
    )


def _process_one_researcher(
    person_id: str,
    mode: str,
    config: dict,
    model_dir: str,
) -> dict:
    """
    Process a single researcher through the full pipeline.
    Runs in a thread. Returns a result dict.
    """
    db = SessionLocal()
    try:
        identity = db.query(Identity).filter_by(person_id=person_id).first()
        if not identity:
            return {"person_id": person_id, "error": "Identity not found"}

        core_identity = _db_identity_to_core(identity)
        api_key = os.environ.get("PUBMED_API_KEY")

        # Phase 1: Retrieve articles
        person_articles = db.query(PersonArticle).filter_by(person_id=person_id).all()
        existing_pmids = {pa.pmid for pa in person_articles}

        if mode == "full" and not existing_pmids:
            # Search PubMed by name
            search_pmids = esearch(
                first_name=core_identity.first_name,
                last_name=core_identity.last_name,
                api_key=api_key,
            )
            new_pmids = [p for p in search_pmids if p not in existing_pmids]
            if new_pmids:
                articles = efetch(new_pmids, api_key=api_key)
                for art in articles:
                    existing_art = db.query(Article).filter_by(pmid=art.pmid).first()
                    if not existing_art:
                        db.add(Article(
                            pmid=art.pmid,
                            title=art.title,
                            journal=art.journal,
                            pub_year=art.pub_year,
                            doi=art.doi,
                            abstract_text=art.abstract,
                            authors=[{
                                "first_name": a.first_name,
                                "last_name": a.last_name,
                                "initials": a.initials,
                                "affiliation": a.affiliation,
                                "orcid": a.orcid,
                            } for a in art.authors],
                            mesh_headings=art.mesh_headings if hasattr(art, 'mesh_headings') else [],
                            keywords=art.keywords if hasattr(art, 'keywords') else [],
                            grants=art.grants if hasattr(art, 'grants') else [],
                            publication_types=art.publication_types if hasattr(art, 'publication_types') else [],
                        ))
                    existing_pa = db.query(PersonArticle).filter_by(
                        person_id=person_id, pmid=art.pmid
                    ).first()
                    if not existing_pa:
                        db.add(PersonArticle(
                            person_id=person_id, pmid=art.pmid, source="search"
                        ))
                db.commit()

        # Reload all articles for this person
        person_articles = db.query(PersonArticle).filter_by(person_id=person_id).all()
        pmids = [pa.pmid for pa in person_articles]
        db_articles = db.query(Article).filter(Article.pmid.in_(pmids)).all() if pmids else []
        core_articles = [_db_article_to_core(a) for a in db_articles]

        if not core_articles:
            return {
                "person_id": person_id,
                "article_count": 0,
                "scored_count": 0,
            }

        # Phase 2: Target author matching
        for art in core_articles:
            idx = find_target_author(art, core_identity)
            art.target_author_index = idx
            # Update DB
            pa = db.query(PersonArticle).filter_by(
                person_id=person_id, pmid=art.pmid
            ).first()
            if pa:
                pa.target_author_index = idx
        db.commit()

        # Phase 3: Feature generation
        curations = db.query(Curation).filter_by(person_id=person_id).all()
        has_curations = len(curations) > 0

        feature_rows = generate_features(
            identity=core_identity,
            articles=core_articles,
            config=config,
            curated_articles=core_articles if has_curations else None,
            curations={c.pmid: c.assertion for c in curations} if has_curations else None,
        )

        if not feature_rows:
            return {
                "person_id": person_id,
                "article_count": len(core_articles),
                "scored_count": 0,
            }

        # Phase 4: Scoring
        model_type = "feedbackIdentity" if has_curations else "identityOnly"
        scored_df = score_articles(feature_rows, model_type=model_type, model_dir=model_dir)

        # Save scores
        for _, row in scored_df.iterrows():
            pmid = str(row["pmid"])
            existing_score = db.query(PersonArticleScore).filter_by(
                person_id=person_id, pmid=pmid, model_type=model_type
            ).first()
            score_val = float(row.get("calibrated_score", 0))
            features_dict = {
                k: float(v) if isinstance(v, (int, float)) else v
                for k, v in row.items() if k not in ("pmid", "calibrated_score", "raw_score")
            }
            if existing_score:
                existing_score.calibrated_score = score_val
                existing_score.raw_score = float(row.get("raw_score", 0))
                existing_score.features = features_dict
            else:
                db.add(PersonArticleScore(
                    person_id=person_id,
                    pmid=pmid,
                    model_type=model_type,
                    calibrated_score=score_val,
                    raw_score=float(row.get("raw_score", 0)),
                    features=features_dict,
                ))
        db.commit()

        return {
            "person_id": person_id,
            "article_count": len(core_articles),
            "scored_count": len(scored_df),
            "score_min": float(scored_df["calibrated_score"].min()),
            "score_max": float(scored_df["calibrated_score"].max()),
        }
    except Exception as e:
        logger.exception(f"Error processing {person_id}")
        return {"person_id": person_id, "error": str(e)}
    finally:
        db.close()


async def run_pipeline(
    person_ids: list[str],
    mode: str = "full",
) -> AsyncGenerator[dict, None]:
    """
    Run the scoring pipeline for multiple researchers concurrently.
    Yields progress events as dicts.
    mode: "full" (retrieve + score) or "score_only" (score uploaded articles)
    """
    config = load_config()
    model_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "models", "wcm",
    )

    total = len(person_ids)
    completed = 0

    yield {
        "type": "started",
        "total": total,
        "mode": mode,
    }

    loop = asyncio.get_event_loop()
    executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)

    # Submit all tasks
    futures = {}
    for pid in person_ids:
        future = loop.run_in_executor(
            executor, _process_one_researcher, pid, mode, config, model_dir
        )
        futures[pid] = future
        yield {
            "type": "queued",
            "person_id": pid,
        }

    # Collect results as they complete
    for pid in person_ids:
        yield {
            "type": "processing",
            "person_id": pid,
            "phase": "running",
        }
        result = await futures[pid]
        completed += 1
        yield {
            "type": "complete_one",
            "person_id": pid,
            "completed": completed,
            "total": total,
            **result,
        }

    executor.shutdown(wait=False)
    yield {
        "type": "finished",
        "completed": completed,
        "total": total,
    }
```

- [ ] **Step 2: Commit**

```bash
git add api/services/pipeline_runner.py
git commit -m "Add pipeline runner service with concurrent processing"
```

---

### Task 8: Pipeline + Scores + Articles API Endpoints

**Files:**
- Create: `api/routers/pipeline.py`
- Create: `api/routers/scores.py`
- Create: `api/routers/articles.py`
- Modify: `api/main.py`

- [ ] **Step 1: Create api/routers/pipeline.py**

```python
# api/routers/pipeline.py
import json
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.database import get_db
from api.models import Identity
from api.services.pipeline_runner import run_pipeline

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


class PipelineRequest(BaseModel):
    person_ids: list[str] | None = None  # None = all researchers
    mode: str = "full"  # "full" or "score_only"


@router.post("/run")
async def run(req: PipelineRequest, db: Session = Depends(get_db)):
    if req.person_ids:
        person_ids = req.person_ids
    else:
        identities = db.query(Identity.person_id).all()
        person_ids = [i.person_id for i in identities]

    if not person_ids:
        return {"error": "No researchers found"}

    async def event_stream():
        async for event in run_pipeline(person_ids, mode=req.mode):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/status")
def status(db: Session = Depends(get_db)):
    from sqlalchemy import func
    from api.models import PersonArticle, PersonArticleScore

    total_researchers = db.query(Identity).count()
    total_articles = db.query(PersonArticle).count()
    total_scores = db.query(PersonArticleScore).count()
    scored_researchers = db.query(
        PersonArticleScore.person_id
    ).distinct().count()

    return {
        "total_researchers": total_researchers,
        "total_articles": total_articles,
        "total_scores": total_scores,
        "scored_researchers": scored_researchers,
    }
```

- [ ] **Step 2: Create api/routers/scores.py**

```python
# api/routers/scores.py
import csv
import io
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from api.database import get_db
from api.models import Identity, Article, PersonArticle, PersonArticleScore

router = APIRouter(prefix="/api/scores", tags=["scores"])


@router.get("/export")
def export_scores(
    person_id: str | None = Query(None),
    threshold: int = Query(0),
    db: Session = Depends(get_db),
):
    query = (
        db.query(PersonArticleScore, Article, Identity)
        .join(Article, PersonArticleScore.pmid == Article.pmid)
        .join(Identity, PersonArticleScore.person_id == Identity.person_id)
    )
    if person_id:
        query = query.filter(PersonArticleScore.person_id == person_id)

    results = query.order_by(
        PersonArticleScore.person_id,
        PersonArticleScore.calibrated_score.desc(),
    ).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "person_id", "first_name", "last_name", "pmid",
        "title", "journal", "year", "score", "pubmed_url",
    ])

    for r in results:
        score = round(r.PersonArticleScore.calibrated_score * 100) if r.PersonArticleScore.calibrated_score else 0
        if score >= threshold:
            writer.writerow([
                r.Identity.person_id,
                r.Identity.first_name,
                r.Identity.last_name,
                r.PersonArticleScore.pmid,
                r.Article.title,
                r.Article.journal,
                r.Article.pub_year,
                score,
                f"https://pubmed.ncbi.nlm.nih.gov/{r.PersonArticleScore.pmid}/",
            ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=reciter_scores.csv"},
    )


@router.get("/{person_id}")
def get_scores(person_id: str, db: Session = Depends(get_db)):
    scores = (
        db.query(PersonArticleScore, Article)
        .join(Article, PersonArticleScore.pmid == Article.pmid)
        .filter(PersonArticleScore.person_id == person_id)
        .order_by(PersonArticleScore.calibrated_score.desc())
        .all()
    )

    return [
        {
            "pmid": s.PersonArticleScore.pmid,
            "score": round(s.PersonArticleScore.calibrated_score * 100) if s.PersonArticleScore.calibrated_score else 0,
            "model_type": s.PersonArticleScore.model_type,
            "title": s.Article.title,
            "journal": s.Article.journal,
            "pub_year": s.Article.pub_year,
            "doi": s.Article.doi,
        }
        for s in scores
    ]
```

- [ ] **Step 3: Create api/routers/articles.py**

```python
# api/routers/articles.py
import io
import json
import os
from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import pandas as pd

from api.database import get_db
from api.models import Article, PersonArticle
from api.services.column_mapper import detect_mappings
from core.pubmed import efetch

router = APIRouter(prefix="/api/articles", tags=["articles"])


@router.post("/upload")
async def upload_pmids(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = await file.read()
    filename = file.filename or "pmids.csv"

    if filename.endswith((".xlsx", ".xls")):
        df = pd.read_excel(io.BytesIO(content))
    elif filename.endswith(".tsv"):
        df = pd.read_csv(io.BytesIO(content), sep="\t")
    else:
        df = pd.read_csv(io.BytesIO(content))

    mappings = detect_mappings(list(df.columns))
    rename_map = {orig: canon for orig, canon in mappings.items() if canon}
    df = df.rename(columns=rename_map)

    if "person_id" not in df.columns or "pmid" not in df.columns:
        return {"error": "File must contain person_id and pmid columns"}

    api_key = os.environ.get("PUBMED_API_KEY")
    pmid_list = [str(p) for p in df["pmid"].dropna().unique()]

    # Fetch metadata from PubMed
    articles = efetch(pmid_list, api_key=api_key)
    article_count = 0

    for art in articles:
        existing = db.query(Article).filter_by(pmid=art.pmid).first()
        if not existing:
            db.add(Article(
                pmid=art.pmid,
                title=art.title,
                journal=art.journal,
                pub_year=art.pub_year,
                doi=art.doi,
                abstract_text=art.abstract,
                authors=[{
                    "first_name": a.first_name,
                    "last_name": a.last_name,
                    "initials": a.initials,
                    "affiliation": a.affiliation,
                    "orcid": a.orcid,
                } for a in art.authors],
            ))
            article_count += 1

    # Link person-article relationships
    link_count = 0
    for _, row in df.iterrows():
        pid = str(row["person_id"]).strip()
        pmid = str(row["pmid"]).strip()
        if pid and pmid:
            existing = db.query(PersonArticle).filter_by(
                person_id=pid, pmid=pmid
            ).first()
            if not existing:
                db.add(PersonArticle(
                    person_id=pid, pmid=pmid, source="upload"
                ))
                link_count += 1

    db.commit()
    return {
        "articles_fetched": article_count,
        "links_created": link_count,
        "total_pmids": len(pmid_list),
    }


@router.get("/{person_id}")
def get_articles(person_id: str, db: Session = Depends(get_db)):
    results = (
        db.query(Article, PersonArticle)
        .join(PersonArticle, Article.pmid == PersonArticle.pmid)
        .filter(PersonArticle.person_id == person_id)
        .order_by(Article.pub_year.desc())
        .all()
    )

    return [
        {
            "pmid": r.Article.pmid,
            "title": r.Article.title,
            "journal": r.Article.journal,
            "pub_year": r.Article.pub_year,
            "source": r.PersonArticle.source,
        }
        for r in results
    ]
```

- [ ] **Step 4: Register all routers in api/main.py**

```python
# api/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import institution, researchers, articles, pipeline, scores

app = FastAPI(title="ReCiter Desktop API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3002"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(institution.router)
app.include_router(researchers.router)
app.include_router(articles.router)
app.include_router(pipeline.router)
app.include_router(scores.router)


@app.get("/api/health")
def health_check():
    return {"status": "ok"}
```

- [ ] **Step 5: Commit**

```bash
git add api/routers/ api/main.py
git commit -m "Add pipeline, scores, and articles API endpoints"
```

---

## Phase 3: Frontend

### Task 9: Next.js Scaffolding + Layout + Sidebar

**Files:**
- Modify: `frontend/app/layout.tsx`
- Create: `frontend/app/page.tsx`
- Create: `frontend/components/sidebar.tsx`
- Create: `frontend/lib/api.ts`
- Create: `frontend/lib/sse.ts`

- [ ] **Step 1: Install shadcn/ui**

```bash
cd frontend
npx shadcn@latest init -d
npx shadcn@latest add button card badge input label select slider table progress separator
```

- [ ] **Step 2: Create frontend/lib/api.ts**

```typescript
// frontend/lib/api.ts
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8090";

export async function apiFetch<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json();
}

export async function apiUpload<T>(
  path: string,
  file: File
): Promise<T> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Upload error ${res.status}: ${text}`);
  }
  return res.json();
}

export function apiExportUrl(path: string, params?: Record<string, string>): string {
  const url = new URL(`${API_BASE}${path}`);
  if (params) {
    Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
  }
  return url.toString();
}
```

- [ ] **Step 3: Create frontend/lib/sse.ts**

```typescript
// frontend/lib/sse.ts
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8090";

export function subscribeSSE(
  path: string,
  body: Record<string, unknown>,
  onEvent: (data: Record<string, unknown>) => void,
  onDone?: () => void
): () => void {
  const controller = new AbortController();

  (async () => {
    const res = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: controller.signal,
    });

    if (!res.ok || !res.body) {
      onDone?.();
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          try {
            const data = JSON.parse(line.slice(6));
            onEvent(data);
          } catch {
            // skip malformed JSON
          }
        }
      }
    }

    onDone?.();
  })().catch(() => onDone?.());

  return () => controller.abort();
}
```

- [ ] **Step 4: Create frontend/components/sidebar.tsx**

```tsx
// frontend/components/sidebar.tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: "home" },
  { href: "/setup", label: "Institution Setup", icon: "building" },
  { href: "/researchers", label: "Researchers", icon: "users" },
  { href: "/articles", label: "Articles", icon: "file-text" },
  { href: "/pipeline", label: "Pipeline", icon: "activity" },
  { href: "/results", label: "Results", icon: "bar-chart" },
];

const ICONS: Record<string, string> = {
  home: "\u2302",
  building: "\u2616",
  users: "\u263B",
  "file-text": "\u2637",
  activity: "\u2248",
  "bar-chart": "\u2261",
};

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-56 min-h-screen bg-gray-950 border-r border-gray-800 p-4 flex flex-col">
      <div className="mb-8">
        <h1 className="text-lg font-semibold text-white">ReCiter Desktop</h1>
        <p className="text-xs text-gray-500 mt-1">Author Disambiguation</p>
      </div>
      <nav className="flex flex-col gap-1">
        {NAV_ITEMS.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors",
              pathname === item.href
                ? "bg-gray-800 text-white"
                : "text-gray-400 hover:text-white hover:bg-gray-900"
            )}
          >
            <span className="text-base">{ICONS[item.icon]}</span>
            {item.label}
          </Link>
        ))}
      </nav>
    </aside>
  );
}
```

- [ ] **Step 5: Update frontend/app/layout.tsx**

```tsx
// frontend/app/layout.tsx
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/sidebar";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "ReCiter Desktop",
  description: "Author name disambiguation for your institution",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.className} bg-gray-950 text-gray-100`}>
        <div className="flex min-h-screen">
          <Sidebar />
          <main className="flex-1 p-8">{children}</main>
        </div>
      </body>
    </html>
  );
}
```

- [ ] **Step 6: Create placeholder frontend/app/page.tsx (Dashboard)**

```tsx
// frontend/app/page.tsx
export default function Dashboard() {
  return (
    <div>
      <h2 className="text-2xl font-semibold mb-2">Welcome to ReCiter Desktop</h2>
      <p className="text-gray-400">
        Score publications against researcher identities using machine learning.
      </p>
    </div>
  );
}
```

- [ ] **Step 7: Verify frontend builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no errors.

- [ ] **Step 8: Commit**

```bash
git add frontend/
git commit -m "Add Next.js scaffolding with sidebar layout and API/SSE utilities"
```

---

### Task 10: Dashboard Page

**Files:**
- Create: `frontend/components/status-card.tsx`
- Modify: `frontend/app/page.tsx`

- [ ] **Step 1: Create frontend/components/status-card.tsx**

```tsx
// frontend/components/status-card.tsx
"use client";

import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface StatusCardProps {
  label: string;
  value: string;
  isComplete: boolean;
  isNext: boolean;
}

export function StatusCard({ label, value, isComplete, isNext }: StatusCardProps) {
  return (
    <Card
      className={cn(
        "transition-colors",
        isNext && "border-blue-600 bg-blue-950/20",
        isComplete && "border-green-800",
        !isNext && !isComplete && "border-gray-800"
      )}
    >
      <CardContent className="p-4">
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs text-gray-500 uppercase tracking-wider">
            {label}
          </span>
          {isComplete && (
            <span className="text-green-500 text-sm">{"\u2713"}</span>
          )}
        </div>
        <p
          className={cn(
            "text-sm font-medium",
            isComplete ? "text-green-400" : isNext ? "text-blue-400" : "text-gray-500"
          )}
        >
          {value}
        </p>
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 2: Build full Dashboard page**

```tsx
// frontend/app/page.tsx
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { StatusCard } from "@/components/status-card";
import { apiFetch } from "@/lib/api";

interface DashboardState {
  institution: string | null;
  researcherCount: number;
  articleCount: number;
  scoreCount: number;
  scoredResearchers: number;
}

export default function Dashboard() {
  const [state, setState] = useState<DashboardState>({
    institution: null,
    researcherCount: 0,
    articleCount: 0,
    scoreCount: 0,
    scoredResearchers: 0,
  });

  useEffect(() => {
    async function load() {
      try {
        const config = await apiFetch<Record<string, unknown>>("/api/institution");
        const status = await apiFetch<{
          total_researchers: number;
          total_articles: number;
          total_scores: number;
          scored_researchers: number;
        }>("/api/pipeline/status");

        setState({
          institution: (config.institution_label as string) || null,
          researcherCount: status.total_researchers,
          articleCount: status.total_articles,
          scoreCount: status.total_scores,
          scoredResearchers: status.scored_researchers,
        });
      } catch {
        // API not available yet
      }
    }
    load();
  }, []);

  const hasInstitution = !!state.institution;
  const hasResearchers = state.researcherCount > 0;
  const hasArticles = state.articleCount > 0;
  const hasScores = state.scoreCount > 0;

  // Determine next step
  let nextHref = "/setup";
  let nextLabel = "Set Up Your Institution";
  if (hasInstitution && !hasResearchers) {
    nextHref = "/researchers";
    nextLabel = "Upload Researchers";
  } else if (hasResearchers && !hasScores) {
    nextHref = "/pipeline";
    nextLabel = "Run Pipeline";
  } else if (hasScores) {
    nextHref = "/results";
    nextLabel = "View Results";
  }

  return (
    <div className="max-w-4xl">
      <h2 className="text-2xl font-semibold mb-2">ReCiter Desktop</h2>
      <p className="text-gray-400 mb-8">
        Score publications against researcher identities using machine learning.
        Upload a researcher list, retrieve articles from PubMed, and get
        confidence scores for each article-researcher match.
      </p>

      <div className="grid grid-cols-4 gap-4 mb-8">
        <StatusCard
          label="Institution"
          value={state.institution || "Not configured"}
          isComplete={hasInstitution}
          isNext={!hasInstitution}
        />
        <StatusCard
          label="Researchers"
          value={hasResearchers ? `${state.researcherCount} loaded` : "Not uploaded"}
          isComplete={hasResearchers}
          isNext={hasInstitution && !hasResearchers}
        />
        <StatusCard
          label="Articles"
          value={hasArticles ? `${state.articleCount} retrieved` : "Not yet retrieved"}
          isComplete={hasArticles}
          isNext={hasResearchers && !hasArticles && !hasScores}
        />
        <StatusCard
          label="Scores"
          value={
            hasScores
              ? `${state.scoreCount} scored`
              : "Not yet scored"
          }
          isComplete={hasScores}
          isNext={hasArticles && !hasScores}
        />
      </div>

      <Link href={nextHref}>
        <Button size="lg">{nextLabel}</Button>
      </Link>

      {hasInstitution && (
        <Card className="mt-8 border-gray-800 bg-gray-900/50">
          <CardContent className="p-4">
            <p className="text-sm font-medium text-gray-300 mb-2">
              About Scoring Models
            </p>
            <p className="text-xs text-gray-500 leading-relaxed">
              Your scores are currently based on identity evidence alone (25
              features including name matching, email, affiliation, and more).
              Institutions that curate articles — accepting or rejecting
              individual matches — unlock a more powerful model with 43 features
              that learns from those decisions. Curation support is coming in a
              future release via Publication Manager.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/components/status-card.tsx frontend/app/page.tsx
git commit -m "Add dashboard page with status cards and guided next step"
```

---

### Task 11: Institution Setup Page

**Files:**
- Create: `frontend/app/setup/page.tsx`

- [ ] **Step 1: Create the setup page with 3-step flow**

```tsx
// frontend/app/setup/page.tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiFetch } from "@/lib/api";
import { subscribeSSE } from "@/lib/sse";

interface DiscoveredInstitution {
  name: string;
  count: number;
  keywords: string;
  classification: "home" | "collaborating" | "skip";
}

interface DiscoveredDomain {
  domain: string;
  count: number;
  selected: boolean;
}

export default function SetupPage() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [domain, setDomain] = useState("");
  const [institutionName, setInstitutionName] = useState("");
  const [statusMessages, setStatusMessages] = useState<string[]>([]);
  const [institutions, setInstitutions] = useState<DiscoveredInstitution[]>([]);
  const [emailDomains, setEmailDomains] = useState<DiscoveredDomain[]>([]);
  const [discovering, setDiscovering] = useState(false);
  const [saving, setSaving] = useState(false);

  function startDiscovery() {
    if (!domain.trim()) return;
    setDiscovering(true);
    setStatusMessages([]);
    setStep(2);

    subscribeSSE(
      "/api/institution/discover",
      { domain: domain.trim() },
      (event) => {
        if (event.type === "status") {
          setStatusMessages((prev) => [...prev, event.message as string]);
        } else if (event.type === "complete") {
          const insts = (event.institutions as Array<{
            name: string;
            count: number;
            keywords: string;
          }>).map((inst, i) => ({
            ...inst,
            classification: (i < 2 ? "home" : "collaborating") as "home" | "collaborating" | "skip",
          }));
          setInstitutions(insts);
          setEmailDomains(
            (event.email_domains as Array<{ domain: string; count: number }>).map(
              (d) => ({ ...d, selected: true })
            )
          );
          if (!institutionName && insts.length > 0) {
            setInstitutionName(insts[0].name);
          }
          setDiscovering(false);
          setStep(3);
        }
      },
      () => setDiscovering(false)
    );
  }

  async function saveConfig() {
    setSaving(true);
    try {
      await apiFetch("/api/institution/configure", {
        method: "POST",
        body: JSON.stringify({
          institutions: institutions
            .filter((i) => i.classification !== "skip")
            .map((i) => ({
              name: i.name,
              classification: i.classification,
              keywords: i.keywords,
            })),
          email_domains: emailDomains
            .filter((d) => d.selected)
            .map((d) => d.domain),
          institution_label: institutionName,
        }),
      });
      router.push("/");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="max-w-2xl">
      <h2 className="text-2xl font-semibold mb-2">Institution Setup</h2>
      <p className="text-gray-400 mb-6">
        Configure your institution by entering your email domain. We will discover
        your institutional profile from PubMed automatically.
      </p>

      {/* Step indicator */}
      <div className="flex gap-2 mb-8">
        {[1, 2, 3].map((s) => (
          <div
            key={s}
            className={`h-1 flex-1 rounded ${
              s <= step ? "bg-blue-600" : "bg-gray-800"
            }`}
          />
        ))}
      </div>

      {/* Step 1: Enter domain */}
      {step === 1 && (
        <Card className="border-gray-800">
          <CardContent className="p-6 space-y-4">
            <div>
              <Label htmlFor="domain">Institution email domain</Label>
              <Input
                id="domain"
                placeholder="e.g., fredhutch.org"
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
                className="mt-1"
              />
            </div>
            <div>
              <Label htmlFor="name">Institution name (optional)</Label>
              <Input
                id="name"
                placeholder="e.g., Fred Hutchinson Cancer Center"
                value={institutionName}
                onChange={(e) => setInstitutionName(e.target.value)}
                className="mt-1"
              />
            </div>
            <Button onClick={startDiscovery} disabled={!domain.trim()}>
              Discover
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Step 2: Discovery progress */}
      {step === 2 && (
        <Card className="border-gray-800">
          <CardContent className="p-6">
            <div className="space-y-2">
              {statusMessages.map((msg, i) => (
                <div key={i} className="flex items-center gap-2 text-sm">
                  <span className={i === statusMessages.length - 1 && discovering ? "text-blue-400" : "text-green-500"}>
                    {i === statusMessages.length - 1 && discovering ? "\u25CB" : "\u2713"}
                  </span>
                  <span className="text-gray-300">{msg}</span>
                </div>
              ))}
              {discovering && (
                <p className="text-gray-500 text-sm mt-4">Analyzing affiliations...</p>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Step 3: Classify institutions */}
      {step === 3 && (
        <div className="space-y-6">
          <Card className="border-gray-800">
            <CardContent className="p-6">
              <h3 className="text-sm font-medium text-gray-300 mb-4">
                Classify discovered institutions
              </h3>
              <div className="space-y-3">
                {institutions.map((inst, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between p-3 rounded bg-gray-900 border border-gray-800"
                  >
                    <div>
                      <p className="text-sm text-gray-200">{inst.name}</p>
                      <p className="text-xs text-gray-500">
                        {inst.count} mentions
                      </p>
                    </div>
                    <div className="flex gap-1">
                      {(["home", "collaborating", "skip"] as const).map((cls) => (
                        <button
                          key={cls}
                          onClick={() => {
                            const updated = [...institutions];
                            updated[i] = { ...updated[i], classification: cls };
                            setInstitutions(updated);
                          }}
                          className={`px-3 py-1 text-xs rounded ${
                            inst.classification === cls
                              ? cls === "home"
                                ? "bg-green-900 text-green-300"
                                : cls === "collaborating"
                                ? "bg-blue-900 text-blue-300"
                                : "bg-gray-700 text-gray-400"
                              : "bg-gray-800 text-gray-500 hover:bg-gray-700"
                          }`}
                        >
                          {cls === "home"
                            ? "Home"
                            : cls === "collaborating"
                            ? "Collaborating"
                            : "Skip"}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card className="border-gray-800">
            <CardContent className="p-6">
              <h3 className="text-sm font-medium text-gray-300 mb-4">
                Email domains
              </h3>
              <div className="space-y-2">
                {emailDomains.map((d, i) => (
                  <label
                    key={i}
                    className="flex items-center gap-3 text-sm cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={d.selected}
                      onChange={() => {
                        const updated = [...emailDomains];
                        updated[i] = { ...updated[i], selected: !d.selected };
                        setEmailDomains(updated);
                      }}
                      className="rounded border-gray-600"
                    />
                    <span className="text-gray-300">@{d.domain}</span>
                    <span className="text-gray-600 text-xs">
                      ({d.count} occurrences)
                    </span>
                  </label>
                ))}
              </div>
            </CardContent>
          </Card>

          <Button onClick={saveConfig} disabled={saving}>
            {saving ? "Saving..." : "Save Configuration"}
          </Button>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/app/setup/
git commit -m "Add institution setup page with 3-step discovery flow"
```

---

### Task 12: Researcher Upload Page

**Files:**
- Create: `frontend/components/file-upload.tsx`
- Create: `frontend/components/column-mapper.tsx`
- Create: `frontend/app/researchers/page.tsx`

- [ ] **Step 1: Create frontend/components/file-upload.tsx**

```tsx
// frontend/components/file-upload.tsx
"use client";

import { useCallback, useState } from "react";
import { Button } from "@/components/ui/button";

interface FileUploadProps {
  onFileSelected: (file: File) => void;
  description: string;
  accept?: string;
}

export function FileUpload({ onFileSelected, description, accept }: FileUploadProps) {
  const [dragging, setDragging] = useState(false);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) onFileSelected(file);
    },
    [onFileSelected]
  );

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      className={`border-2 border-dashed rounded-xl p-12 text-center transition-colors ${
        dragging ? "border-blue-500 bg-blue-950/20" : "border-gray-700"
      }`}
    >
      <p className="text-lg text-gray-300 mb-2 font-medium">
        Upload your researcher list
      </p>
      <p className="text-sm text-gray-500 mb-1 max-w-md mx-auto leading-relaxed">
        {description}
      </p>
      <p className="text-xs text-gray-600 mb-5">CSV, Excel (.xlsx, .xls), or TSV</p>
      <div className="flex items-center justify-center gap-3">
        <Button
          variant="default"
          onClick={() => {
            const input = document.createElement("input");
            input.type = "file";
            input.accept = accept || ".csv,.xlsx,.xls,.tsv";
            input.onchange = (e) => {
              const file = (e.target as HTMLInputElement).files?.[0];
              if (file) onFileSelected(file);
            };
            input.click();
          }}
        >
          Browse files
        </Button>
        <span className="text-gray-600 text-sm">or</span>
        <a href="#" className="text-sm text-blue-500 border-b border-dashed border-blue-500/30">
          Download sample template
        </a>
      </div>
      <p className="text-xs text-gray-600 mt-4">
        Column names are flexible — we recognize many common variations.
      </p>
    </div>
  );
}
```

- [ ] **Step 2: Create frontend/components/column-mapper.tsx**

```tsx
// frontend/components/column-mapper.tsx
"use client";

import { Button } from "@/components/ui/button";

interface Mapping {
  original: string;
  canonical: string | null;
  sample: string;
  selected: boolean;
}

interface ColumnMapperProps {
  mappings: Mapping[];
  onMappingChange: (index: number, canonical: string | null) => void;
  onToggle: (index: number) => void;
  onSelectAll: () => void;
  onDeselectAll: () => void;
}

const AVAILABLE_FIELDS = [
  "person_id", "first_name", "last_name", "middle_name",
  "primary_email", "primary_institution", "department", "title",
  "orcid", "bachelor_year", "doctoral_year", "pmid", "assertion",
];

export function ColumnMapper({
  mappings,
  onMappingChange,
  onToggle,
  onSelectAll,
  onDeselectAll,
}: ColumnMapperProps) {
  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-gray-400">
          We detected <strong className="text-gray-200">{mappings.length} columns</strong> in
          your file. Please confirm the mappings below.
        </p>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={onSelectAll}>
            Select All
          </Button>
          <Button variant="outline" size="sm" onClick={onDeselectAll}>
            Deselect All
          </Button>
        </div>
      </div>

      <div className="border border-gray-800 rounded-lg overflow-hidden">
        {/* Header */}
        <div className="grid grid-cols-[40px_180px_30px_200px_140px] gap-2 items-center px-4 py-2 bg-gray-900 text-xs text-gray-500 uppercase tracking-wider">
          <span />
          <span>Your Column</span>
          <span />
          <span>Maps To</span>
          <span>Sample</span>
        </div>

        {/* Rows */}
        {mappings.map((m, i) => (
          <div
            key={i}
            className={`grid grid-cols-[40px_180px_30px_200px_140px] gap-2 items-center px-4 py-3 border-t border-gray-800 ${
              !m.canonical ? "bg-amber-950/10" : ""
            }`}
          >
            <div className="flex justify-center">
              <input
                type="checkbox"
                checked={m.selected && !!m.canonical}
                onChange={() => onToggle(i)}
                className="rounded border-gray-600"
                disabled={!m.canonical}
              />
            </div>
            <code className="text-sm text-gray-300 bg-gray-800 px-2 py-0.5 rounded">
              {m.original}
            </code>
            <span className="text-gray-600 text-center">{"\u2192"}</span>
            {m.canonical ? (
              <span className="text-sm text-green-400">{m.canonical}</span>
            ) : (
              <select
                className="bg-gray-800 text-amber-400 border border-amber-800/30 rounded px-2 py-1 text-sm"
                value=""
                onChange={(e) =>
                  onMappingChange(i, e.target.value || null)
                }
              >
                <option value="">-- Select mapping --</option>
                {AVAILABLE_FIELDS.map((f) => (
                  <option key={f} value={f}>
                    {f}
                  </option>
                ))}
                <option value="__skip">Skip this column</option>
              </select>
            )}
            <span className="text-xs text-gray-600 font-mono truncate">
              {m.sample}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Create frontend/app/researchers/page.tsx**

```tsx
// frontend/app/researchers/page.tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { FileUpload } from "@/components/file-upload";
import { ColumnMapper } from "@/components/column-mapper";
import { apiUpload, apiFetch } from "@/lib/api";

interface MappingRow {
  original: string;
  canonical: string | null;
  sample: string;
  selected: boolean;
}

interface UploadResult {
  file_id: string;
  filename: string;
  row_count: number;
  mappings: Array<{ original: string; canonical: string | null; sample: string }>;
  preview: Array<Record<string, unknown>>;
  has_gold_standard: boolean;
  gold_standard_count: number;
}

export default function ResearchersPage() {
  const router = useRouter();
  const [uploadResult, setUploadResult] = useState<UploadResult | null>(null);
  const [mappings, setMappings] = useState<MappingRow[]>([]);
  const [importGoldStandard, setImportGoldStandard] = useState(true);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<{
    identity_count: number;
    curation_count: number;
  } | null>(null);

  async function handleFile(file: File) {
    const result = await apiUpload<UploadResult>("/api/researchers/upload", file);
    setUploadResult(result);
    setMappings(
      result.mappings.map((m) => ({
        ...m,
        selected: !!m.canonical,
      }))
    );
  }

  async function handleImport() {
    if (!uploadResult) return;
    setImporting(true);
    try {
      const result = await apiFetch<{
        identity_count: number;
        curation_count: number;
      }>("/api/researchers/import", {
        method: "POST",
        body: JSON.stringify({
          file_id: uploadResult.file_id,
          mappings: mappings
            .filter((m) => m.selected && m.canonical)
            .map((m) => ({ original: m.original, canonical: m.canonical })),
          import_gold_standard: importGoldStandard,
        }),
      });
      setImportResult(result);
    } finally {
      setImporting(false);
    }
  }

  // Success state
  if (importResult) {
    return (
      <div className="max-w-2xl">
        <h2 className="text-2xl font-semibold mb-6">Researchers</h2>
        <Card className="border-green-800 bg-green-950/20">
          <CardContent className="p-6 text-center">
            <p className="text-green-400 text-lg font-medium mb-2">
              {importResult.identity_count} researchers loaded
            </p>
            {importResult.curation_count > 0 && (
              <p className="text-green-500/70 text-sm">
                {importResult.curation_count} curation records imported
              </p>
            )}
            <Button className="mt-4" onClick={() => router.push("/pipeline")}>
              Continue to Pipeline
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-3xl">
      <h2 className="text-2xl font-semibold mb-2">Researchers</h2>
      <p className="text-gray-400 mb-6">
        Upload your researcher list to get started.
      </p>

      {!uploadResult ? (
        <FileUpload
          onFileSelected={handleFile}
          description="A spreadsheet with one row per researcher. At minimum, include a unique ID, first name, and last name. Optional: email, title, primary institution, department, doctoral year, ORCID."
        />
      ) : (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-400">
              {uploadResult.filename} — {uploadResult.row_count} rows
            </p>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setUploadResult(null);
                setMappings([]);
              }}
            >
              Upload different file
            </Button>
          </div>

          <ColumnMapper
            mappings={mappings}
            onMappingChange={(i, canonical) => {
              const updated = [...mappings];
              updated[i] = { ...updated[i], canonical, selected: !!canonical };
              setMappings(updated);
            }}
            onToggle={(i) => {
              const updated = [...mappings];
              updated[i] = { ...updated[i], selected: !updated[i].selected };
              setMappings(updated);
            }}
            onSelectAll={() =>
              setMappings(mappings.map((m) => ({ ...m, selected: !!m.canonical })))
            }
            onDeselectAll={() =>
              setMappings(mappings.map((m) => ({ ...m, selected: false })))
            }
          />

          {uploadResult.has_gold_standard && (
            <div className="bg-green-950/30 border border-green-800 rounded-lg p-4 flex items-center gap-3">
              <input
                type="checkbox"
                checked={importGoldStandard}
                onChange={() => setImportGoldStandard(!importGoldStandard)}
                className="rounded border-green-600"
              />
              <div>
                <p className="text-sm text-green-400">Curation data detected</p>
                <p className="text-xs text-green-500/70">
                  We found {uploadResult.gold_standard_count} accept/reject
                  records. Import this data to enable the more accurate scoring
                  model.
                </p>
              </div>
            </div>
          )}

          <div className="flex justify-end gap-3">
            <Button
              variant="outline"
              onClick={() => {
                setUploadResult(null);
                setMappings([]);
              }}
            >
              Cancel
            </Button>
            <Button onClick={handleImport} disabled={importing}>
              {importing
                ? "Importing..."
                : `Import ${uploadResult.row_count} Researchers`}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/components/file-upload.tsx frontend/components/column-mapper.tsx frontend/app/researchers/
git commit -m "Add researcher upload page with column mapper and gold standard detection"
```

---

### Task 13: Pipeline View Page

**Files:**
- Create: `frontend/components/pipeline-row.tsx`
- Create: `frontend/app/pipeline/page.tsx`

- [ ] **Step 1: Create frontend/components/pipeline-row.tsx**

```tsx
// frontend/components/pipeline-row.tsx
"use client";

import Link from "next/link";
import { Progress } from "@/components/ui/progress";

export type Phase = "queued" | "retrieving" | "matching" | "analyzing" | "scoring" | "complete" | "error";

const PHASE_COLORS: Record<Phase, string> = {
  queued: "text-gray-500",
  retrieving: "text-blue-400",
  matching: "text-purple-400",
  analyzing: "text-amber-400",
  scoring: "text-red-400",
  complete: "text-green-400",
  error: "text-red-500",
};

const PHASE_BORDERS: Record<Phase, string> = {
  queued: "border-l-gray-700",
  retrieving: "border-l-blue-500",
  matching: "border-l-purple-500",
  analyzing: "border-l-amber-500",
  scoring: "border-l-red-500",
  complete: "border-l-green-500",
  error: "border-l-red-600",
};

const PHASE_LABELS: Record<Phase, string> = {
  queued: "Queued",
  retrieving: "Retrieving from PubMed",
  matching: "Identifying target authors",
  analyzing: "Computing features",
  scoring: "Scoring",
  complete: "Complete",
  error: "Error",
};

interface PipelineRowProps {
  personId: string;
  name: string;
  phase: Phase;
  articleCount: number | null;
  scoreRange?: string;
  progress?: number;
}

export function PipelineRow({
  personId,
  name,
  phase,
  articleCount,
  scoreRange,
  progress,
}: PipelineRowProps) {
  const isActive = !["queued", "complete", "error"].includes(phase);

  return (
    <div
      className={`grid grid-cols-[200px_120px_100px_200px_80px] gap-2 items-center px-4 py-2.5 rounded-md border-l-[3px] ${
        PHASE_BORDERS[phase]
      } ${phase === "queued" ? "opacity-45" : ""}`}
    >
      <Link
        href={phase === "complete" ? `/results/${personId}` : "#"}
        className={`text-sm ${
          phase === "complete"
            ? "text-green-300 underline decoration-green-800"
            : "text-gray-200"
        }`}
      >
        {name}
      </Link>
      <span className="text-xs text-gray-600 font-mono">{personId}</span>
      <span className="text-sm text-gray-500">
        {articleCount ?? "\u2014"}
      </span>
      <div className="flex items-center gap-2">
        {isActive && (
          <span className={`text-xs animate-spin ${PHASE_COLORS[phase]}`}>
            {"\u25E0"}
          </span>
        )}
        {phase === "complete" && (
          <span className="text-green-500 text-sm">{"\u2713"}</span>
        )}
        <span className={`text-sm ${PHASE_COLORS[phase]}`}>
          {PHASE_LABELS[phase]}
        </span>
      </div>
      <div className="w-full">
        {isActive && progress !== undefined && (
          <Progress value={progress} className="h-1" />
        )}
        {phase === "complete" && scoreRange && (
          <span className="text-xs text-gray-600">{scoreRange}</span>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create frontend/app/pipeline/page.tsx**

```tsx
// frontend/app/pipeline/page.tsx
"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { PipelineRow, Phase } from "@/components/pipeline-row";
import { apiFetch } from "@/lib/api";
import { subscribeSSE } from "@/lib/sse";

interface ResearcherStatus {
  personId: string;
  name: string;
  phase: Phase;
  articleCount: number | null;
  scoreRange?: string;
}

export default function PipelinePage() {
  const [researchers, setResearchers] = useState<ResearcherStatus[]>([]);
  const [running, setRunning] = useState(false);
  const [completed, setCompleted] = useState(0);
  const [total, setTotal] = useState(0);
  const [totalArticles, setTotalArticles] = useState(0);
  const [totalScored, setTotalScored] = useState(0);
  const [mode, setMode] = useState<"full" | "score_only">("full");
  const [showCompleted, setShowCompleted] = useState(false);

  useEffect(() => {
    async function loadResearchers() {
      try {
        const list = await apiFetch<Array<{
          person_id: string;
          first_name: string;
          last_name: string;
          article_count: number;
          score_count: number;
        }>>("/api/researchers");
        setResearchers(
          list.map((r) => ({
            personId: r.person_id,
            name: `${r.first_name} ${r.last_name}`,
            phase: r.score_count > 0 ? "complete" as Phase : "queued" as Phase,
            articleCount: r.article_count || null,
          }))
        );
      } catch {
        // API not available
      }
    }
    loadResearchers();
  }, []);

  function startPipeline() {
    setRunning(true);
    setCompleted(0);
    const personIds = researchers.map((r) => r.personId);
    setTotal(personIds.length);

    subscribeSSE(
      "/api/pipeline/run",
      { person_ids: personIds, mode },
      (event) => {
        if (event.type === "queued") {
          setResearchers((prev) =>
            prev.map((r) =>
              r.personId === event.person_id ? { ...r, phase: "queued" } : r
            )
          );
        } else if (event.type === "processing") {
          setResearchers((prev) =>
            prev.map((r) =>
              r.personId === event.person_id
                ? { ...r, phase: "retrieving" }
                : r
            )
          );
        } else if (event.type === "complete_one") {
          const artCount = event.article_count as number;
          const scoredCount = event.scored_count as number;
          const scoreMin = event.score_min as number | undefined;
          const scoreMax = event.score_max as number | undefined;
          setCompleted(event.completed as number);
          setTotalArticles((prev) => prev + artCount);
          setTotalScored((prev) => prev + scoredCount);
          setResearchers((prev) =>
            prev.map((r) =>
              r.personId === event.person_id
                ? {
                    ...r,
                    phase: event.error ? "error" : "complete",
                    articleCount: artCount,
                    scoreRange:
                      scoreMin !== undefined && scoreMax !== undefined
                        ? `${Math.round(scoreMin * 100)}\u2013${Math.round(scoreMax * 100)}`
                        : undefined,
                  }
                : r
            )
          );
        } else if (event.type === "finished") {
          setRunning(false);
        }
      },
      () => setRunning(false)
    );
  }

  const completedResearchers = researchers.filter((r) => r.phase === "complete");
  const activeResearchers = researchers.filter(
    (r) => !["complete", "queued"].includes(r.phase)
  );
  const queuedResearchers = researchers.filter((r) => r.phase === "queued");

  return (
    <div className="max-w-4xl">
      <h2 className="text-2xl font-semibold mb-2">Processing Pipeline</h2>
      <p className="text-gray-400 mb-6">
        Run the scoring pipeline for all researchers.
      </p>

      {!running && completed === 0 && (
        <div className="flex items-center gap-4 mb-6">
          <div className="flex gap-2">
            <Button
              variant={mode === "full" ? "default" : "outline"}
              size="sm"
              onClick={() => setMode("full")}
            >
              Full Retrieval and Scoring
            </Button>
            <Button
              variant={mode === "score_only" ? "default" : "outline"}
              size="sm"
              onClick={() => setMode("score_only")}
            >
              Scoring Only
            </Button>
          </div>
          <Button onClick={startPipeline} disabled={researchers.length === 0}>
            Run Pipeline ({researchers.length} researchers)
          </Button>
        </div>
      )}

      {(running || completed > 0) && (
        <div className="mb-6">
          <div className="flex justify-between text-xs text-gray-500 mb-1">
            <span>Overall Progress</span>
            <span>
              {completed} of {total} researchers &bull; {totalArticles} articles
              &bull; {totalScored} scored
            </span>
          </div>
          <Progress value={total > 0 ? (completed / total) * 100 : 0} className="h-2" />
        </div>
      )}

      {/* Phase legend */}
      {(running || completed > 0) && (
        <div className="flex gap-4 mb-4 text-xs text-gray-500">
          <span><span className="text-green-500">{"\u25CF"}</span> Complete</span>
          <span><span className="text-blue-400">{"\u25CF"}</span> Retrieving</span>
          <span><span className="text-purple-400">{"\u25CF"}</span> Matching</span>
          <span><span className="text-amber-400">{"\u25CF"}</span> Analyzing</span>
          <span><span className="text-red-400">{"\u25CF"}</span> Scoring</span>
          <span><span className="text-gray-600">{"\u25CF"}</span> Queued</span>
        </div>
      )}

      {/* Completed section (collapsed) */}
      {completedResearchers.length > 0 && (
        <Card className="border-gray-800 mb-4">
          <CardContent className="p-0">
            <button
              className="w-full flex items-center justify-between px-4 py-3 text-sm"
              onClick={() => setShowCompleted(!showCompleted)}
            >
              <div className="flex items-center gap-2">
                <span className="text-green-500">{"\u2713"}</span>
                <span className="text-gray-300">
                  {completedResearchers.length} researchers complete
                </span>
              </div>
              <span className="text-gray-600 text-xs">
                {showCompleted ? "Hide" : "Show details"}{" "}
                {showCompleted ? "\u25B4" : "\u25BE"}
              </span>
            </button>
            {showCompleted && (
              <div className="border-t border-gray-800">
                {/* Column headers */}
                <div className="grid grid-cols-[200px_120px_100px_200px_80px] gap-2 px-4 py-2 text-[10px] text-gray-600 uppercase tracking-wider">
                  <span>Researcher</span>
                  <span>UID</span>
                  <span>Articles</span>
                  <span>Status</span>
                  <span>Scores</span>
                </div>
                {completedResearchers.map((r) => (
                  <PipelineRow key={r.personId} {...r} />
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Active rows */}
      {activeResearchers.length > 0 && (
        <div className="space-y-1 mb-4">
          {/* Column headers */}
          <div className="grid grid-cols-[200px_120px_100px_200px_80px] gap-2 px-4 py-2 text-[10px] text-gray-600 uppercase tracking-wider border-b border-gray-800">
            <span>Researcher</span>
            <span>UID</span>
            <span>Articles</span>
            <span>Status</span>
            <span>Progress</span>
          </div>
          {activeResearchers.map((r) => (
            <PipelineRow key={r.personId} {...r} />
          ))}
        </div>
      )}

      {/* Queued rows */}
      {queuedResearchers.length > 0 && running && (
        <div className="space-y-1">
          {queuedResearchers.slice(0, 5).map((r) => (
            <PipelineRow key={r.personId} {...r} />
          ))}
          {queuedResearchers.length > 5 && (
            <p className="text-center text-sm text-gray-600 py-2">
              ... and {queuedResearchers.length - 5} more queued
            </p>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/components/pipeline-row.tsx frontend/app/pipeline/
git commit -m "Add pipeline view page with per-researcher progress tracking"
```

---

### Task 14: Results Page

**Files:**
- Create: `frontend/components/score-badge.tsx`
- Create: `frontend/app/results/page.tsx`
- Create: `frontend/app/results/[personId]/page.tsx`

- [ ] **Step 1: Create frontend/components/score-badge.tsx**

```tsx
// frontend/components/score-badge.tsx
export function ScoreBadge({ score }: { score: number }) {
  let bg: string;
  let text: string;
  if (score >= 70) {
    bg = "bg-green-900/60";
    text = "text-green-400";
  } else if (score >= 30) {
    bg = "bg-amber-900/40";
    text = "text-amber-400";
  } else {
    bg = "bg-red-900/40";
    text = "text-red-400";
  }
  return (
    <span
      className={`inline-block w-12 text-center py-1 rounded text-sm font-semibold ${bg} ${text}`}
    >
      {score}
    </span>
  );
}
```

- [ ] **Step 2: Create frontend/app/results/page.tsx (researcher list)**

```tsx
// frontend/app/results/page.tsx
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { apiFetch, apiExportUrl } from "@/lib/api";

interface Researcher {
  person_id: string;
  first_name: string;
  last_name: string;
  article_count: number;
  score_count: number;
}

export default function ResultsPage() {
  const [researchers, setResearchers] = useState<Researcher[]>([]);

  useEffect(() => {
    apiFetch<Researcher[]>("/api/researchers").then(setResearchers).catch(() => {});
  }, []);

  const scored = researchers.filter((r) => r.score_count > 0);

  return (
    <div className="max-w-4xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-semibold">Results</h2>
          <p className="text-gray-400 text-sm">
            {scored.length} researchers scored
          </p>
        </div>
        {scored.length > 0 && (
          <a href={apiExportUrl("/api/scores/export")} download>
            <Button variant="outline">Export All Results (CSV)</Button>
          </a>
        )}
      </div>

      <div className="border border-gray-800 rounded-lg overflow-hidden">
        <div className="grid grid-cols-[200px_120px_100px_100px_100px] gap-2 px-4 py-2 bg-gray-900 text-xs text-gray-500 uppercase tracking-wider">
          <span>Researcher</span>
          <span>UID</span>
          <span>Articles</span>
          <span>Scored</span>
          <span />
        </div>
        {scored.map((r) => (
          <Link
            key={r.person_id}
            href={`/results/${r.person_id}`}
            className="grid grid-cols-[200px_120px_100px_100px_100px] gap-2 items-center px-4 py-3 border-t border-gray-800 hover:bg-gray-900/50 transition-colors"
          >
            <span className="text-sm text-gray-200">
              {r.first_name} {r.last_name}
            </span>
            <span className="text-xs text-gray-600 font-mono">
              {r.person_id}
            </span>
            <span className="text-sm text-gray-500">{r.article_count}</span>
            <span className="text-sm text-gray-500">{r.score_count}</span>
            <span className="text-xs text-blue-500">
              View articles {"\u2192"}
            </span>
          </Link>
        ))}
        {scored.length === 0 && (
          <div className="px-4 py-8 text-center text-gray-600">
            No scored researchers yet. Run the pipeline first.
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Create frontend/app/results/[personId]/page.tsx**

```tsx
// frontend/app/results/[personId]/page.tsx
"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { ScoreBadge } from "@/components/score-badge";
import { apiFetch, apiExportUrl } from "@/lib/api";

interface ScoredArticle {
  pmid: string;
  score: number;
  title: string;
  journal: string;
  pub_year: number;
  doi: string;
}

interface ResearcherInfo {
  person_id: string;
  first_name: string;
  last_name: string;
}

export default function ResearcherResultsPage() {
  const params = useParams();
  const personId = params.personId as string;

  const [researcher, setResearcher] = useState<ResearcherInfo | null>(null);
  const [articles, setArticles] = useState<ScoredArticle[]>([]);
  const [threshold, setThreshold] = useState(70);
  const [sortBy, setSortBy] = useState<"score" | "year" | "journal">("score");

  useEffect(() => {
    apiFetch<ResearcherInfo>(`/api/researchers/${personId}`)
      .then(setResearcher)
      .catch(() => {});
    apiFetch<ScoredArticle[]>(`/api/scores/${personId}`)
      .then(setArticles)
      .catch(() => {});
  }, [personId]);

  const sorted = [...articles].sort((a, b) => {
    if (sortBy === "score") return b.score - a.score;
    if (sortBy === "year") return (b.pub_year || 0) - (a.pub_year || 0);
    return (a.journal || "").localeCompare(b.journal || "");
  });

  const above = articles.filter((a) => a.score >= threshold).length;
  const below = articles.length - above;

  if (!researcher) return <div className="text-gray-500">Loading...</div>;

  return (
    <div className="max-w-5xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-semibold">
            {researcher.first_name} {researcher.last_name}
          </h2>
          <p className="text-gray-500 text-sm font-mono">{personId}</p>
          <p className="text-gray-400 text-sm mt-1">
            {articles.length} articles scored
          </p>
        </div>
        <a
          href={apiExportUrl("/api/scores/export", {
            person_id: personId,
            threshold: String(threshold),
          })}
          download
        >
          <Button variant="outline">Export CSV</Button>
        </a>
      </div>

      {/* Threshold slider */}
      <div className="flex items-center gap-4 mb-6">
        <span className="text-sm text-gray-500">Threshold:</span>
        <div className="w-48">
          <Slider
            value={[threshold]}
            onValueChange={(v) => setThreshold(v[0])}
            min={0}
            max={100}
            step={5}
          />
        </div>
        <span className="text-sm text-gray-300 font-mono w-8">{threshold}</span>
        <span className="text-sm text-green-500">{above} above</span>
        <span className="text-gray-600">|</span>
        <span className="text-sm text-red-400">{below} below</span>
      </div>

      {/* Sort */}
      <div className="flex gap-2 mb-4">
        {(["score", "year", "journal"] as const).map((s) => (
          <button
            key={s}
            onClick={() => setSortBy(s)}
            className={`text-xs px-3 py-1 rounded ${
              sortBy === s
                ? "bg-gray-800 text-gray-200"
                : "text-gray-500 hover:text-gray-300"
            }`}
          >
            {s.charAt(0).toUpperCase() + s.slice(1)}
          </button>
        ))}
      </div>

      {/* Article table */}
      <div className="border border-gray-800 rounded-lg overflow-hidden">
        <div className="grid grid-cols-[60px_1fr_180px_60px_60px] gap-2 px-4 py-2 bg-gray-900 text-xs text-gray-500 uppercase tracking-wider">
          <span>Score</span>
          <span>Title</span>
          <span>Journal</span>
          <span>Year</span>
          <span />
        </div>
        {sorted.map((a) => (
          <div
            key={a.pmid}
            className="grid grid-cols-[60px_1fr_180px_60px_60px] gap-2 items-center px-4 py-2.5 border-t border-gray-800/50"
          >
            <ScoreBadge score={a.score} />
            <span
              className={`text-sm ${
                a.score >= threshold ? "text-gray-200" : "text-gray-500"
              }`}
            >
              {a.title}
            </span>
            <span className="text-xs text-gray-500 truncate">{a.journal}</span>
            <span className="text-xs text-gray-500">{a.pub_year}</span>
            <a
              href={`https://pubmed.ncbi.nlm.nih.gov/${a.pmid}/`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-blue-500"
            >
              PubMed
            </a>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/components/score-badge.tsx frontend/app/results/
git commit -m "Add results pages with scored article table and threshold slider"
```

---

### Task 15: Articles Page (PMID Upload for Scoring Only Mode)

**Files:**
- Create: `frontend/app/articles/page.tsx`

- [ ] **Step 1: Create articles page**

```tsx
// frontend/app/articles/page.tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { FileUpload } from "@/components/file-upload";
import { apiUpload } from "@/lib/api";

export default function ArticlesPage() {
  const router = useRouter();
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<{
    articles_fetched: number;
    links_created: number;
    total_pmids: number;
  } | null>(null);

  async function handleFile(file: File) {
    setUploading(true);
    try {
      const res = await apiUpload<{
        articles_fetched: number;
        links_created: number;
        total_pmids: number;
      }>("/api/articles/upload", file);
      setResult(res);
    } finally {
      setUploading(false);
    }
  }

  if (result) {
    return (
      <div className="max-w-2xl">
        <h2 className="text-2xl font-semibold mb-6">Articles</h2>
        <Card className="border-green-800 bg-green-950/20">
          <CardContent className="p-6 text-center">
            <p className="text-green-400 text-lg font-medium mb-2">
              {result.total_pmids} PMIDs processed
            </p>
            <p className="text-green-500/70 text-sm">
              {result.articles_fetched} new articles fetched from PubMed &bull;{" "}
              {result.links_created} researcher-article links created
            </p>
            <Button className="mt-4" onClick={() => router.push("/pipeline")}>
              Continue to Pipeline
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-2xl">
      <h2 className="text-2xl font-semibold mb-2">Articles</h2>
      <p className="text-gray-400 mb-6">
        Upload a list of known PMIDs to score. Use this when you already have
        publication lists and just need scores (Scoring Only mode).
      </p>
      <p className="text-gray-500 text-sm mb-6">
        If you want to discover new articles from PubMed instead, skip this page
        and run the pipeline in Full Retrieval and Scoring mode.
      </p>

      {uploading ? (
        <Card className="border-gray-800">
          <CardContent className="p-8 text-center">
            <p className="text-gray-400">
              Uploading PMIDs and fetching metadata from PubMed...
            </p>
          </CardContent>
        </Card>
      ) : (
        <FileUpload
          onFileSelected={handleFile}
          description="A spreadsheet with person_id and pmid columns. Each row links a researcher to an article."
        />
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/app/articles/
git commit -m "Add articles page for PMID upload in scoring-only mode"
```

---

## Phase 4: Docker Integration

### Task 16: Dockerfiles + End-to-End Verification

**Files:**
- Modify: `api/Dockerfile`
- Modify: `frontend/Dockerfile`
- Modify: `docker-compose.yml`

- [ ] **Step 1: Finalize api/Dockerfile**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for PyMySQL
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/api

# core/, features/, models/, data/, config/ are mounted as volumes
ENV PYTHONPATH=/app

EXPOSE 8090

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8090", "--reload"]
```

- [ ] **Step 2: Finalize frontend/Dockerfile**

```dockerfile
FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production

COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000

CMD ["node", "server.js"]
```

- [ ] **Step 3: Update frontend/next.config.mjs for standalone output**

```javascript
// frontend/next.config.mjs
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
};

export default nextConfig;
```

- [ ] **Step 4: Build and verify Docker Compose**

Run:
```bash
cd /Users/paulalbert/Dropbox/GitHub/ReCiter-Desktop
docker compose up --build -d
```

Wait 15 seconds for containers to start, then verify:
```bash
# Health check
curl http://localhost:8090/api/health
# Expected: {"status":"ok"}

# Frontend
curl -s http://localhost:3002 | head -5
# Expected: HTML response
```

- [ ] **Step 5: Commit**

```bash
git add api/Dockerfile frontend/Dockerfile frontend/next.config.mjs docker-compose.yml
git commit -m "Finalize Docker setup for production builds"
```

- [ ] **Step 6: Verify end-to-end with Docker**

Run the full stack and verify the API returns proper responses:
```bash
# Check all containers are healthy
docker compose ps

# Test institution endpoint
curl http://localhost:8090/api/institution
# Expected: {} (empty config)

# Test researchers endpoint
curl http://localhost:8090/api/researchers
# Expected: [] (empty list)

# Test pipeline status
curl http://localhost:8090/api/pipeline/status
# Expected: {"total_researchers":0,"total_articles":0,"total_scores":0,"scored_researchers":0}
```

- [ ] **Step 7: Clean up**

```bash
docker compose down
```

- [ ] **Step 8: Final commit**

```bash
git add -A
git commit -m "ReCiter Desktop v1: complete Docker Compose application"
```

# ReCiter Desktop

Standalone web application for **author name disambiguation**. Upload a researcher roster, retrieve candidate articles from PubMed, and score each article with pre-trained machine-learning models — no Java stack required.

Built for librarians, research administrators, and bibliometricians at academic institutions.

![Article scores view showing confidence scores per publication](docs/screenshots/article-scores.png)

---

## Why this exists

The full [ReCiter](https://github.com/wcmc-its/reciter) platform is a powerful Java/AWS stack that takes weeks to stand up. ReCiter Desktop ships the same scoring engine — and the same models, trained on 900,000+ curated Weill Cornell article-researcher pairs — as a single `docker compose up`. You get production-grade disambiguation against your researcher list in minutes, with no AWS account, no Java tooling, and no infrastructure team.

---

## Quick start

1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop) (free for personal, educational, and small-business use).
2. Download or clone this repository.
3. **macOS:** double-click **`Start ReCiter.command`** in Finder.
   **Windows:** double-click **`Start ReCiter.bat`** in File Explorer.

The app opens in your default browser. To stop it, double-click **`Stop ReCiter.command`** (or `.bat`). Your data is preserved between runs.

The launcher picks free ports automatically, so a local MariaDB or another app on the default ports won't block startup.

> First-run note: the launcher pulls the MariaDB image (~150 MB) the first time. Subsequent starts take a few seconds.

Optional: set a free [NCBI API key](https://ncbiinsights.ncbi.nlm.nih.gov/2017/11/02/new-api-keys-for-the-e-utilities/) to lift the PubMed rate limit from 3 to 10 requests/sec. Export `PUBMED_API_KEY` in your shell profile before running the launcher.

### For developers

If you'd rather run the stack directly without the launcher:

```bash
git clone https://github.com/wcmc-its/ReCiter-Desktop.git
cd ReCiter-Desktop
docker compose up
```

Defaults: frontend on `3002`, MariaDB on `3306`. The backend is reached through the frontend's Next.js proxy at `/api/*` — it's not exposed to the host directly. Override frontend or DB ports with `FRONTEND_PORT` / `DB_PORT` environment variables.

For native dev (running `npm run dev` and `uvicorn` separately), the frontend proxies `/api/*` to `http://localhost:8090` by default. Set `API_INTERNAL_URL` to override.

---

## How it works

For each researcher × article pair the system:

1. **Retrieves** candidate articles from PubMed by name search
2. **Matches** the target author in the author list via a 19-step cascade
3. **Computes** evidence features — name match, email, institutional affiliation, journal subfield, degree-year discrepancy, gender, author count, co-authorship signals
4. **Scores** with a pre-trained XGBoost model, isotonic-calibrated to a true 0–100 probability

A score of 95 means there is approximately a 95% probability the article belongs to the researcher — not a relative ranking, but a calibrated probability you can threshold against.

---

## User workflow

| Step | Page | What happens |
|------|------|--------------|
| 1 | **Institution Setup** | Enter your email domain. The app samples PubMed, discovers the affiliated organizations and email domains used by your authors, and asks you to classify each as Home, Collaborating, or Skip. |
| 2 | **Researchers** | Upload a CSV / Excel / TSV roster, *or* click **Load sample data** to populate the app with five real Weill Cornell researchers (Cole, Lyden, Albert, Wheeler, Ma) plus ~1,000 curated accept/reject assertions — no file needed. Column names on uploads are flexible; the app auto-detects 30+ common variations. |
| 3 | **Articles** *(optional)* | Already have a list of PMIDs? Upload them for Scoring-Only mode. Skip if you want the app to discover articles for you. |
| 4 | **Retrieve & Score** | Run the pipeline — full retrieval-and-scoring or scoring-only. Watch per-researcher progress in real time. Re-runs only fetch newly added publications. |
| 5 | **Results** | Per-researcher scored articles with color-coded confidence, threshold slider, and CSV export. |

Want a clean slate? The dashboard has a **Reset application** link that wipes every researcher, article, score, and curation in one click. Useful after exploring with sample data before loading your own roster.

---

## Screenshots

| | |
|---|---|
| ![Dashboard](docs/screenshots/dashboard.png) | ![Institution Setup](docs/screenshots/setup.png) |
| **Dashboard** — live status, next-step prompt | **Setup** — domain entry, PubMed-driven discovery |
| ![Researchers](docs/screenshots/researchers.png) | ![Pipeline](docs/screenshots/pipeline.png) |
| **Researchers** — flexible CSV/Excel import | **Retrieve & Score** — per-researcher progress, worker count, activity log |
| ![Results](docs/screenshots/results.png) | ![Article Scores](docs/screenshots/article-scores.png) |
| **Results** — researcher list with article counts | **Article Scores** — histogram, threshold, confidence per article |

---

## Validation

The pre-trained models were developed at Weill Cornell Medicine on 900,000+ curated article-researcher pairs and externally validated at Fred Hutchinson Cancer Center (868 researchers, ~20,000 publications) **without retraining**.

| Metric | Identity-only model | Feedback model |
|--------|--------------------:|---------------:|
| Features | 42 | 72 |
| AUC | 0.978 | 0.9993 |
| Accuracy at 95% confidence | 99.57% | 99.99% |
| Articles requiring manual review | 18% | 2.3% |

The feedback model activates automatically when you import accept/reject data (an `assertion` column alongside `pmid`). Feedback features account for ~85% of its predictive importance — even partial curation imports cut manual-review burden by an order of magnitude.

**Score bands surfaced in the UI:**

| Range | Meaning | Action |
|-------|---------|--------|
| ≥ 95 | Likely match | Accept with minimal review |
| 30 – 95 | Review band | Curator confirms or rejects |
| < 30 | Unlikely match | Usually a common-name collision |

---

## For non-WCM institutions

ReCiter Desktop is designed to work against any researcher cohort without retraining the models. A few practical tips for cross-institutional runs:

- **Populate the ORCID column where available.** The pipeline now queries PubMed by `[auid]` and unions those PMIDs with the name-based candidate set, recovering articles where PubMed indexed the author under a misspelled or transliterated name. No effect when ORCID is blank.
- **Review the Institution Setup classifications carefully.** Home / Collaborating / Skip choices affect the affiliation feature. Department names should match (or have synonyms configured against) the [ScienceMetrix](https://www.science-metrix.com/) journal-subfield taxonomy used by the journal-subfield feature.
- **Pin the commit SHA you ran.** For reproducibility in papers or institutional reports, record the commit hash from `git rev-parse HEAD` alongside the run date. Algorithm improvements continue to land — pinning makes any future re-run diffable.
- **Parity with upstream ReCiter** (the full Java engine) is tracked in [`PARITY.md`](./PARITY.md) with a pinned SHA in [`.upstream-ref`](./.upstream-ref). Run `scripts/check-upstream-parity.sh` to surface upstream commits since the pin.
- **Large cohorts (~800+ researchers) currently take hours to retrieve.** Batched/parallelized retrieval is a known pending improvement.

---

## Operating modes

- **Full retrieval and scoring** — Search PubMed by researcher name, discover candidate articles, then score them. Use when you want to find publications you may not already know about.
- **Scoring only** — Upload a CSV of known PMIDs (`person_id`, `pmid`). The app fetches article metadata and scores them. No broad name search.
- **Incremental updates** — Re-running for previously scored researchers only retrieves newly added publications; existing scores are preserved.

---

## Researcher file format

CSV, Excel (`.xlsx`, `.xls`), or TSV — one row per researcher. Column names are matched against many common variants.

| Required field | Recognized column names |
|---|---|
| Person ID | `person_id`, `uid`, `emp_id`, `cwid`, `netid` |
| First name | `first_name`, `fname`, `first`, `givenname` |
| Last name | `last_name`, `lname`, `last`, `surname` |

| Optional field | Recognized column names |
|---|---|
| Middle name | `middle_name`, `middle`, `mi` |
| Email | `email`, `primary_email`, `email_address` |
| Title / rank | `title`, `rank`, `academic_title`, `position` |
| Institution | `institution`, `primary_institution` |
| Department | `department`, `dept`, `division` |
| Doctoral year | `doctoral_year`, `phd_year`, `degree_year` |
| ORCID | `orcid`, `orcid_id`, `orcid_url` |

| Curation field *(optional)* | Recognized column names |
|---|---|
| PMID | `pmid`, `pubmed_id` |
| Assertion | `assertion`, `status`, `user_assertion` |

Optional fields are not required for scoring but improve precision. Importing curation data switches the engine to the higher-accuracy feedback model.

---

## Architecture

```
launcher (.command / .bat)
  └── docker compose up
        ├── frontend   Next.js 14 ─── host :3002  (browser entry point)
        │     └── proxies /api/* to ─┐
        ├── api        FastAPI ──────┘  (docker network only, not host-exposed)
        └── db         MariaDB 11 ── host :3306
```

The browser only talks to the frontend. All `/api/*` calls are same-origin and rewritten through Next.js to the backend over the docker service network. This means there's no second host port to worry about and no CORS surface to attack from other localhost-served pages. The launcher floats the frontend and DB host ports automatically if the defaults are taken.

- **Frontend** — Next.js 14, Tailwind, shadcn/ui. Acts as the API proxy for the browser.
- **Backend** — FastAPI wrapping the Python scoring engine in `core/` and `features/`. Long-running work (institution discovery, retrieval, scoring) streams progress over Server-Sent Events.
- **Engine** — The same `core/` and `features/` code used in production at Weill Cornell.
- **ML** — XGBoost 3.2.0 + isotonic calibration. The XGBoost version is pinned; cross-version model loading causes score drift amplified by the calibrator's step function.
- **Database** — MariaDB 11, chosen for forward compatibility with [ReCiter Publication Manager](https://github.com/wcmc-its/reciter-publication-manager).

---

## Project structure

```
ReCiter-Desktop/
├── frontend/               Next.js app (pages, components, API client)
├── api/                    FastAPI backend
│   ├── routers/            HTTP endpoints
│   ├── services/           Discovery, column mapping, pipeline orchestration
│   └── models.py           SQLAlchemy ORM
├── core/                   Scoring engine (production code)
│   ├── scoring.py          XGBoost + isotonic calibration
│   ├── feature_generator.py
│   ├── target_author.py    19-step author matching cascade
│   └── pubmed.py           PubMed E-utilities client
├── features/               Per-feature calculators
├── models/wcm/             Pre-trained WCM production models (.joblib)
├── data/                   Lookup tables (name frequency, gender, journals)
├── config/default_config.yaml
└── docker-compose.yml
```

---

## API reference

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET  | `/api/health` | Health check |
| POST | `/api/institution/discover` | Auto-discover institution from PubMed *(SSE)* |
| POST | `/api/institution/configure` | Save institution configuration |
| GET  | `/api/institution` | Get current configuration |
| POST | `/api/researchers/upload` | Upload roster, return detected column mappings |
| POST | `/api/researchers/import` | Import with confirmed mappings |
| POST | `/api/researchers/load-sample` | Load bundled 5-researcher sample cohort *(SSE)* |
| GET  | `/api/researchers` | List all researchers |
| GET  | `/api/researchers/{id}` | Get researcher detail |
| POST | `/api/articles/upload` | Upload PMID CSV |
| GET  | `/api/articles/{id}` | Get articles for researcher |
| POST | `/api/pipeline/run` | Run scoring pipeline *(SSE)* |
| GET  | `/api/pipeline/status` | Get current pipeline state |
| GET  | `/api/scores/{id}` | Get scores for researcher |
| GET  | `/api/scores/export` | Export all scores as CSV |
| POST | `/api/reset` | Wipe all user data (researchers, articles, scores, curations, institution) — preserves API token |

---

## Development

Run each component on the host with hot reload:

```bash
# 1. Database — local MariaDB
docker run -d --name reciter-desktop-db \
  -p 3306:3306 \
  -e MARIADB_USER=reciter \
  -e MARIADB_PASSWORD=reciter_local \
  -e MARIADB_DATABASE=reciter_desktop \
  -e MARIADB_ALLOW_EMPTY_ROOT_PASSWORD=yes \
  -v reciter-desktop-data:/var/lib/mysql \
  mariadb:11

# 2. Bootstrap schema (first run only)
mariadb -h 127.0.0.1 -P 3306 -ureciter -preciter_local reciter_desktop < api/schema.sql

# 3. Backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8090

# 4. Frontend
cd frontend
npm install
npm run dev
```

The backend defaults to `mysql+pymysql://reciter:reciter_local@localhost:3306/reciter_desktop` — override with `DATABASE_URL`. After the one-time `schema.sql` bootstrap, Alembic migrations run on every backend start to apply any incremental schema changes. (`docker compose up` mounts `schema.sql` into MariaDB's init directory automatically, so this manual step is only needed for the bare `docker run` path above.)

On first run, the backend generates a per-install API token at `~/.reciter-desktop/api-token` (mode 600). All `/api/*` requests must carry it in the `X-Reciter-Token` header — the Next.js shell reads the file server-side and surfaces it to the browser through a same-origin route, so other localhost-served pages cannot drive-by call the API.

---

## Requirements

- Docker + Docker Compose *(for `docker compose up`)*
- Python 3.12+ *(for local development)*
- Node.js 20+ *(for local development)*
- XGBoost **3.2.0** — pinned; cross-version model loading produces incorrect scores

---

## Roadmap

- **In-app curation** — accept/reject articles directly, retraining feedback model on the fly
- **Local model training** — train on your institution's curation data
- **Scopus integration** — secondary retrieval source for higher recall
- **Publication Manager integration** — share a database with [reciter-publication-manager](https://github.com/wcmc-its/reciter-publication-manager) for institutional curation workflows

---

## Related projects

- [ReCiter](https://github.com/wcmc-its/reciter) — full Java-based author disambiguation engine
- [ReCiter Publication Manager](https://github.com/wcmc-its/reciter-publication-manager) — web UI for article curation
- [ReCiter Identity Model](https://github.com/wcmc-its/reciter-identity-model) — identity data model

---

## License

Apache 2.0

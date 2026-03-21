# ReCiter Desktop — AI Agent Guide

## Overview

Standalone Streamlit web application for author disambiguation without requiring the full ReCiter Java stack. Uses pre-trained CARE (Comprehensive Author Recognition Engine) XGBoost models to score articles against researcher identities. Designed for institutions to run locally.

**Repo**: `wcmc-its/ReCiter-Desktop`
**Runtime**: Python 3.14+, Streamlit 1.30+
**ML**: XGBoost 3.2.0 (CRITICAL: exact version match required)
**Database**: SQLite (local `~/.reciter-desktop/`)
**Status**: New repo, initial development

---

## Directory Structure

```
ReCiter-Desktop/
├── app.py                           # Streamlit entry point
├── pages/                           # Multi-page Streamlit app
│   ├── 1_Setup.py                  # Institution configuration
│   ├── 2_Researchers.py            # Upload/manage identities
│   ├── 3_Articles.py               # Retrieve from PubMed
│   ├── 4_Score.py                  # Run scoring pipeline
│   ├── 5_Curate.py                 # Accept/reject articles
│   ├── 6_Train.py                  # Train local model
│   └── 7_Export.py                 # Download results as CSV
├── core/                            # Core business logic
│   ├── config.py                   # YAML config management
│   ├── database.py                 # SQLite persistence
│   ├── identity.py                 # Researcher data model
│   ├── article.py                  # Article data model
│   ├── target_author.py            # Target author name matching
│   ├── preprocessing.py            # Feature engineering & scaling
│   ├── scoring.py                  # XGBoost + isotonic calibration
│   ├── pubmed.py                   # PubMed API integration
│   └── feature_generator.py        # Feature computation pipeline
├── features/                        # Individual feature calculators
│   ├── name_match.py              # Name matching evidence
│   ├── email_match.py             # Email matching
│   ├── affiliation.py             # Institutional affiliation
│   ├── organization.py            # Department/org unit
│   ├── journal_subfield.py        # Journal subfield evidence
│   ├── degree_year.py             # Education year discrepancy
│   ├── gender.py                  # Gender evidence
│   ├── article_size.py            # Article length
│   ├── author_count.py            # Co-author count
│   └── feedback.py                # User feedback weighting
├── models/                          # Pre-trained ML models
│   └── wcm/                       # WCM production models (.joblib)
├── config/
│   └── default_config.yaml         # Default scoring parameters
├── tests/                           # Unit tests
├── data/                            # Sample data
├── requirements.txt
└── venv/                           # Python virtual environment
```

---

## Scoring Pipeline

```
Feature rows (from feature_generator)
  → Select model: feedbackIdentity (if curations exist) or identityOnly
  → Preprocessing: derive features (firstNameFrequencyScore, etc.)
  → StandardScaler transform
  → XGBoost predict_proba → raw probability
  → IsotonicRegression calibration → 0-100 score
  → Return scored DataFrame
```

### Model Types

| Model | Features | When Used |
|-------|----------|-----------|
| `feedbackIdentity` | 43 (31 base + 12 derived) | User has accepted/rejected articles |
| `identityOnly` | 25 (19 base + 6 derived) | No curation data yet |

### Model Files (per type)

- `{type}Model.joblib` — XGBoost classifier
- `{type}Scaler.joblib` — StandardScaler
- `{type}Calibrator.joblib` — IsotonicRegression

**CRITICAL**: Models must be loaded with **XGBoost 3.2.0**. Cross-version loading causes score drift amplified by the isotonic calibrator step function.

---

## Configuration

### YAML Config System

- **Default**: `config/default_config.yaml` (distributed with repo)
- **User**: `~/.reciter-desktop/config.yaml` (created after Setup page)
- Deep merge: user config overlays defaults

### Key Config Sections

```yaml
institution:
  institution_label: ""
  email_suffixes: []            # e.g., ["@med.cornell.edu"]
  home_institution_keywords: [] # e.g., ["Weill Cornell"]

pubmed:
  api_key: ""                   # NCBI API key (10 req/sec vs 3)
  batch_size: 200

name_scoring:                   # Weights from ReCiter application.properties
  first_name: { full_exact: 1.852, ... }
  last_name: { full_exact: 0.664, ... }
  middle_name: { full_exact: 1.588, ... }

scoring:
  default_threshold: 70
  target_author_missing_penalty_percent: 35
```

---

## Streamlit Pages

1. **Setup**: Configure institution name, email domains, PubMed API key
2. **Researchers**: Upload CSV with identities (person_id, names, email, dept)
3. **Articles**: Batch retrieve from PubMed with rate limiting
4. **Score**: Run XGBoost pipeline, adjust threshold, view feature importance
5. **Curate**: Accept/reject scored articles (stored in SQLite)
6. **Train**: Retrain model on local curation data with evaluation metrics
7. **Export**: Download results as CSV with filters

---

## Dependencies (requirements.txt)

```
streamlit>=1.30.0
xgboost==3.2.0           # MUST be exact version
scikit-learn>=1.3.0
pandas>=2.0.0
numpy>=1.24.0
scipy>=1.10.0
requests>=2.28.0
pyyaml>=6.0
joblib>=1.3.0
python-Levenshtein>=0.21.0
```

---

## Running

```bash
cd ~/Dropbox/GitHub/ReCiter-Desktop

# Create/activate venv
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run
streamlit run app.py
# Opens at http://localhost:8501
```

---

## Local Storage

- Config: `~/.reciter-desktop/config.yaml`
- Database: `~/.reciter-desktop/reciter.db` (SQLite, WAL mode)

---

## Tests

```bash
cd ~/Dropbox/GitHub/ReCiter-Desktop
python -m pytest tests/
```

Test files: `test_name_match.py`, `test_target_author.py`, `test_feedback.py`, `test_scoring.py`

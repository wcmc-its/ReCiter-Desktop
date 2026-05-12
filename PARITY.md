# Upstream Parity

ReCiter-Desktop is a Python re-implementation of a slice of the upstream Java [ReCiter](https://github.com/wcmc-its/ReCiter) engine. The two cannot share code, so this document records which files mirror upstream behavior and how to detect drift.

## Mirrored slice

| Desktop file | Upstream counterpart(s) | What is mirrored |
|---|---|---|
| `core/pubmed.py` | `reciter.algorithm.cluster.article.retrieval.strategy.AbstractRetrievalStrategy`, `application.properties` (`searchStrategy-*-threshold`) | Cascading lenient → strict → skip retrieval strategy and threshold values |
| `core/scoring.py` | `reciter.algorithm.article.score.predictor.NeuralNetworkModelArticlesScorer`, ReCiter---Scoring Lambda | Feature pipeline → XGBoost model → calibrator, including the feedback-cap safety net |
| `core/preprocessing.py` | ReCiter---Scoring Lambda preprocessing | 72 feedback features + 47 identity-only features and their derivations |
| `core/feature_generator.py` | `reciter.algorithm.evidence.*` feature evidence generators | Per-evidence feature emission |
| `core/article.py` | `reciter.model.article.ReCiterArticle` | Article data model fields consumed by feature generation |
| `models/wcm/*.joblib` | ReCiter---Scoring production Lambda model artifacts | Trained XGBoost models + scalers + calibrators (binary copies) |
| `config/default_config.yaml` (`retrieval` section) | `application.properties` (`searchStrategy-*-threshold`) | Threshold values used at runtime |

Files **not** in this list are Desktop-original (FastAPI/Next.js UI, MariaDB schema, launcher scripts, sample-data loader, etc.) and are not subject to parity checks.

## Pinned upstream SHA

The last upstream commit reviewed for parity is recorded in [`.upstream-ref`](./.upstream-ref). Bump it whenever you sync changes from upstream — even if the change is N/A and you decide not to port it (record the rationale in this file's changelog below).

## Checking for drift

Run the check script to list upstream commits that touch parity-relevant paths since the pinned SHA:

```bash
scripts/check-upstream-parity.sh
```

By default it inspects `~/Dropbox/GitHub/ReCiter`. Override with `RECITER_REPO=/path/to/reciter` if needed.

Output is a one-line-per-commit log plus a `--stat` summary of the diff. If the output is empty, the pin is current.

## Parity changelog

Append entries as you sync. Newest first.

### 2026-05-12 — pin bumped to `f90aee5e`

Reviewed all commits in `f90aee5..` (since the 2026-04 alignment) for parity impact:

- `cffc6a81` (Apr 25) — **applied**. Raised `lenient_threshold` 2000→3000 and `strict_threshold` 1000→1500 in `core/pubmed.py` defaults. `config/default_config.yaml` and `api/services/pipeline_runner.py` were already on 3000/1500.
- `0c75df92` (May 8) — **N/A**. Bugs were in `SecondInitialRetrievalStrategy` and `AbstractNameRetrievalStrategy`, neither of which exists in Desktop. Desktop's `_build_author_term` cannot produce a `()` query because `_esearch_fetch_ids` requires a non-empty `first_name`/`last_name`.
- `181eceff` — **N/A**. Desktop's `_parse_article` does not read `CommentsCorrections`.
- `c50d5a5b` / `f59f4fcd` / `72e9c1a9` (pmc-release-date) — **deferred**. Desktop scoring does not currently use `pmc_release_date`. Re-evaluate if/when ReCiter---Scoring adds it as a feature.
- `e78508fd`, `2632bc04`, `2e11b461`, `07391ac2` (ArticleProvenance, FeedbackLog, retrieval-src) — **N/A**. Provenance tracking is a server-side concern; Desktop persists curations via its own MariaDB schema.

### 2026-04-04 — initial alignment (`ae7c7c9`)

Commit `ae7c7c9` aligned `core/preprocessing.py`, `core/scoring.py`, and `models/wcm/*.joblib` with the production Lambda. Feature computation and calibrated scores verified identical at that point. Pin was implicit (no `.upstream-ref` file yet).

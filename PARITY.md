# Upstream Parity

ReCiter-Desktop is a Python re-implementation of a slice of the upstream Java [ReCiter](https://github.com/wcmc-its/ReCiter) engine. The two cannot share code, so this document records which files mirror upstream behavior and how to detect drift.

## Mirrored slice

| Desktop file | Upstream counterpart(s) | What is mirrored |
|---|---|---|
| `core/pubmed.py` | `reciter.xml.retriever.pubmed.AbstractRetrievalStrategy`, `OrcidRetrievalStrategy`, `application.properties` (`searchStrategy-*-threshold`) | Cascading lenient → strict → skip name retrieval + asserted-ORCID retrieval; threshold values |
| `core/scoring.py` | `reciter.algorithm.article.score.predictor.NeuralNetworkModelArticlesScorer`, ReCiter---Scoring Lambda | Feature pipeline → XGBoost model → calibrator, including the feedback-cap safety net |
| `core/preprocessing.py` | ReCiter---Scoring Lambda preprocessing | 72 feedback features + 47 identity-only features and their derivations |
| `core/feature_generator.py` | `reciter.algorithm.evidence.*` feature evidence generators | Per-evidence feature emission |
| `features/feedback.py` | `reciter.algorithm.evidence.article.feedback.strategy.*` | 12 feedback dimensions, sigmoid + LOO + informed-absence pattern |
| `features/journal_subfield.py` | `JournalCategoryStrategy`, `JournalSubFieldFeedbackStrategy`, ScienceMetrix lookup | Article → journal subfield resolution + dept matching |
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

### 2026-05-13 (b) — incremental-update parity: EDAT date filter + ORCID-added-later handling

Two incremental-mode gaps surfaced while reviewing Desktop's update flow against upstream's. Both fixed in this commit.

**Applied:**

- `PubMedQuery.java:45` — upstream's incremental query window uses `((start:end[EDAT]) OR (start:end[DP]))`, catching both publication date AND PubMed entry date. Desktop's `core/pubmed.py` was using `[PDAT]` alone (publication date only), silently missing late-indexed articles on update runs (e.g., 2024-published article indexed in PubMed in 2026). Ported via new `_incremental_date_filter()` helper applied to both `search_by_name` and `search_by_orcid` queries.
- *Desktop-only:* first-time ORCID retrieval for a person now ignores `mindate`. Without this, a researcher whose ORCID was added to the identity record after their first pipeline run would never have their pre-mindate ORCID-keyed articles retrieved. Tracked via new `retrieval_log.last_orcid_retrieval_date` column (migration `004`). No upstream counterpart — upstream does ORCID retrieval through the same date-windowed cascade and doesn't have a "first ORCID run" notion since ORCID is treated as part of the identity from initial scoring.

### 2026-05-13 — 6-month retrospective audit + ORCID retrieval port

Widened the script allowlist (added `xml/retriever/pubmed/`, `algorithm/util/ArticleTranslator.java`, `algorithm/cluster/ReCiterCluster.java`, `engine/`). Reviewed all commits in the 2025-11-13 → 2026-05-13 window. Pin remains `f90aee5e` (upstream HEAD).

**Applied:**

- `7dfa0754` (2026-02-21) — *new retrieval strategy.* Added `search_by_orcid()` to `core/pubmed.py` and wired it into `api/services/pipeline_runner.py`. Implements the **asserted** ORCID source from upstream `OrcidRetrievalStrategy`: when `identity.orcid` is set, runs an `<orcid>[auid]` PubMed query and unions the PMIDs into the candidate set. Catches articles where PubMed has a misspelled or transliterated author name.
- `0c75df92` part 3 (2026-05-08) — *defensive empty-query guard.* `esearch_count()` now short-circuits empty/whitespace/`()` terms before round-tripping PubMed. Parts 1-2 of the commit remain N/A (Desktop has no `SecondInitialRetrievalStrategy` / `AbstractNameRetrievalStrategy`).

**Bug-fix spot-checks (verified Desktop already correct by architecture, no port needed):**

- `4ae4dbce` (2026-03-11) — ISSN double-counting in `JournalSubFieldFeedbackStrategy`. Desktop's `journal_subfield.py:get_journal_subfield()` already returns a single subfield per article (first ISSN match wins), and `features/feedback.py:224` calls it once. Cannot double-count by construction.
- `57fd7506` (2026-03-11) — LOO violations in `OrcidCoauthorFeedbackStrategy` and `CitesFeedbackStrategy`. Desktop routes both dimensions through the unified `_compute_dimension_score` / `_compute_multi_dimension_score` helpers in `features/feedback.py`, which exclude the candidate article by PMID (correct LOO via filter, not via subtraction). No bespoke per-dimension code paths exist.
- `6b3ace7b` (2026-03-09) — null-safe guards for non-journal (`PubmedBookArticle`) records. Desktop's `_parse_article` only handles `PubmedArticle` elements; `PubmedBookArticle` records are silently dropped before feature generation. Different behavior than upstream (drops vs scores-with-nulls) but not crash-prone. Acceptable for now; revisit if Desktop adds book-article support.

**Deferred or N/A:**

- `4ae4dbce` part (b) — *Scopus ISSN fallback in `ArticleTranslator`.* Desktop has no Scopus integration; cannot port without standing up a Scopus client. Deferred. Marginal impact: ScienceMetrix subfield match rate could be lower for articles where PubMed only has an electronic ISSN and ScienceMetrix only has the print ISSN.
- GoldStandard chunk / dedup commits `2b29bd75`, `a5b50347`, `8b05cc30`, `a8542586` (Apr 25) — N/A. Upstream's GoldStandard retrieval re-pulls already-curated PMIDs in chunks. Desktop persists curations locally and never re-retrieves them.
- ArticleProvenance / FeedbackLog commits `e78508fd`, `2632bc04`, `2e11b461`, `07391ac2`, `425ac64b` — N/A. Server-side provenance tracking. Desktop has its own MariaDB curation schema.
- pmc-release-date `c50d5a5b` — deferred (Desktop scoring doesn't use it).
- `181eceff` (CommentsCorrections) — N/A (`_parse_article` doesn't read that field).
- Feature-list additions before April 4: `BibliographicCouplingFeedbackStrategy` (`073689c0`), `feedbackScoreJournalTitleSimilarity` (`28a6d663`), `feedbackScoreTextSimilarity` (`3eb3b196`), V3 scoring (`0a862727`, `36479ca8`), first-name frequency (`6f88fcde`), target-author 7 new matching steps (`017b118d`), multi-match disambiguation (`053bcfce`), reversed-name swap (`e0ada7ab`), co-author dedup within article (`3e8a3bbb`), informed-absence penalties (`f30a33d9`) — assumed incorporated via the April 4 alignment commit `ae7c7c9`, which copied production Lambda preprocessing + models. Not individually spot-checked. **Open audit item:** if Desktop's calibrated scores diverge from production for the WCM cohort, this is where to look first.

### 2026-05-12 — pin bumped to `f90aee5e`

Reviewed all commits in `f90aee5..` (since the 2026-04 alignment) for parity impact:

- `cffc6a81` (Apr 25) — **applied**. Raised `lenient_threshold` 2000→3000 and `strict_threshold` 1000→1500 in `core/pubmed.py` defaults. `config/default_config.yaml` and `api/services/pipeline_runner.py` were already on 3000/1500.
- `0c75df92` (May 8) — **N/A**. Bugs were in `SecondInitialRetrievalStrategy` and `AbstractNameRetrievalStrategy`, neither of which exists in Desktop. Desktop's `_build_author_term` cannot produce a `()` query because `_esearch_fetch_ids` requires a non-empty `first_name`/`last_name`.
- `181eceff` — **N/A**. Desktop's `_parse_article` does not read `CommentsCorrections`.
- `c50d5a5b` / `f59f4fcd` / `72e9c1a9` (pmc-release-date) — **deferred**. Desktop scoring does not currently use `pmc_release_date`. Re-evaluate if/when ReCiter---Scoring adds it as a feature.
- `e78508fd`, `2632bc04`, `2e11b461`, `07391ac2` (ArticleProvenance, FeedbackLog, retrieval-src) — **N/A**. Provenance tracking is a server-side concern; Desktop persists curations via its own MariaDB schema.

### 2026-04-04 — initial alignment (`ae7c7c9`)

Commit `ae7c7c9` aligned `core/preprocessing.py`, `core/scoring.py`, and `models/wcm/*.joblib` with the production Lambda. Feature computation and calibrated scores verified identical at that point. Pin was implicit (no `.upstream-ref` file yet).

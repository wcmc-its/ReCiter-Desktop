# Feature Research

**Domain:** Research author disambiguation pipeline — retrieval parity & performance (v2.0 milestone)
**Researched:** 2026-04-05
**Confidence:** HIGH (Java source read directly from ~/Dropbox/GitHub/ReCiter/; Python pipeline read directly)

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features the paper validation workflow requires. Missing these = results are not reproducible against the Java ReCiter baseline.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Affiliation-filtered search (AffiliationRetrievalStrategy) | ReCiter triggers this when lenient count > 2000; without it Desktop retrieves fewer candidates for common names | HIGH | Query: `LastName FI[au] AND (keyword1[affiliation] OR keyword2[affiliation])`. Uses `home_institution_keywords` from config — already stored in DB from setup flow |
| AffiliationInDbRetrievalStrategy | ReCiter also runs per-researcher institution strings when strict mode is active | MEDIUM | Query: `LastName FI[au] AND (InstitutionName[affiliation])`. Uses `identity.institutions`. Desktop identity currently has only `primary_institution` string — need to confirm if a single-institution query is sufficient |
| Compound/derived name detection → strict-only mode | Names with spaces or hyphens trigger `useStrictQueryOnly=true` in Java; without this, common names like "Garcia Lopez" run only a lenient search that may return 10,000 unrelated results | HIGH | Java: `identityAuthorNames()` line 877–883, `deriveAdditionalName()` lines 916–933. Condition: last name has space/hyphen AND both parts >= 4 chars. Python pre-processing step needed before `search_by_name` |
| Compound name quoting in strict path | Already done for lenient; must be verified for the strict path | LOW | `_build_author_term(full_name=True)` uses same `" " in last_name` check — verify it covers hyphen too. Java: `contsructAuthorQuery()` lines 168–172 |
| `retrieve_known` mode PubMed fetch | When PMIDs are uploaded, full PubMed XML must be fetched before scoring; currently maps to `score_only` which skips metadata fetch | MEDIUM | `score_only` path in `pipeline_runner.py` skips `fetch_articles`. Need a `retrieve_known` branch that calls `fetch_articles(pmids)` for any pmid lacking stored metadata |
| `update` mode end-to-end validation | Incremental retrieval using `mindate` from `retrieval_log` is wired but described as untested in milestone doc | LOW | Code present at lines 119–122 of `pipeline_runner.py`. Needs integration test with a known researcher on a second run |
| Historical pipeline runs — `pipeline_run` table | Downstream stats/results pages need a run concept for reproducibility claims in the paper | MEDIUM | Schema: `(run_id PK, started_at, finished_at, mode, researcher_count, article_count, status)`. Add `run_id FK` to `person_article_score`. Migrate existing scores as run #1 |
| Run selector on Results and Stats pages | Users reviewing paper results need to reference a specific run's scores | MEDIUM | Dropdown on `/results` and `/stats`; default to latest run. Requires `run_id` on `person_article_score` |

### Differentiators (Competitive Advantage)

Features that distinguish Desktop from a naive name search and justify the paper's parity claims.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| `asyncio.as_completed` ordering for parallel pipeline | Shows researchers completing as they finish instead of submission order; makes the UI responsive for large rosters | LOW | Current code awaits futures in submission order (lines 347–361 of `pipeline_runner.py`). Replace inner loop with `asyncio.as_completed` — two-line change with immediate UX impact |
| Dynamic `MAX_WORKERS` based on API key presence | With API key: 9 req/sec budget → more parallelism is safe; without: 2.5 req/sec → fewer workers prevent 429 errors | LOW | Current: `min(4, cpu_count)`. Change to: `8 if api_key else 3`. NCBI rates: 10/sec with key, 3/sec without; Desktop uses 9 and 2.5 with headroom |
| Run comparison view (side-by-side score deltas, overlaid ROC) | Enables before/after comparison after model or data changes; useful for paper figures | HIGH | Requires historical runs schema first. Nice-to-have for paper, not blocking |
| Per-researcher export button on Results listing | Librarians want per-person CSV without downloading the full dataset | LOW | Backend already has score export logic; needs a button on the listing row |
| Source labeling (candidate vs known) in results detail | Distinguishes articles found by PubMed search from those uploaded as known assertions | LOW | `person_article.source` already stores "search" vs "upload". Show a label chip in the article list |
| Search/filter on Results listing | Score-range filter + researcher name search on the `/results` index page | LOW | Frontend-only filtering on already-loaded researcher list; no backend changes needed |
| Dashboard surfaced metrics (last run date, overall AUC, total researchers) | Makes the home page useful as a status board instead of just a nav hub | LOW | All values already available from `/api/pipeline/status`; frontend change only |
| Institution name display on setup page | Setup currently reconstructs institution name from keywords; storing and displaying the original label is more trustworthy | LOW | Store `institution_label` at setup time; display it on the setup summary card |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Full 8-strategy retrieval for all researchers by default | Maximizes recall; matches Java ReCiter perfectly | For 500 researchers without API key, 8 strategies × 500 researchers = ~4,000 API calls taking 20+ minutes; also most strategies (grants, known relationships, department) require fields rarely present in uploaded identity CSVs | Run FirstNameInitial for everyone; trigger affiliation strategies only when lenient count > threshold or when institution keywords are configured. This is exactly what Java does — each supplementary strategy is conditional |
| Real-time calibration updates during pipeline run | Feels dynamic and responsive | Stats require a full join across all curations + scores; partial results produce unstable AUC estimates and mislead users | Compute stats once at pipeline completion. Already established as out-of-scope in PROJECT.md |
| Automatic re-score after curation import | Convenience — import assertions and immediately see updated scores | Couples two distinct operations; makes it hard to audit which scores correspond to which curation set | Keep import and pipeline as separate explicit user actions. The pipeline CTA already surfaces on the stats page after assertions are imported |
| Unlimited retmax (no threshold cap) | Some prolific researchers might be missed by the 2000 cap | Removing the cap for a common name like "Wang J" returns 50,000+ results; efetch at 200/batch would take hours and likely trigger NCBI throttling | The strict fallback (1000 cap) is the correct mechanism for high-volume names. Thresholds match Java's `DEFAULT_THRESHOLD=2000` and `STRICT_THRESHOLD=1000` exactly |
| Per-researcher stats drill-down (AUC per person) | Seems granular and useful for debugging | Individual researchers have too few curations for stable AUC curves; displaying per-person AUC misleads users into trusting unreliable numbers | Aggregate stats across the run. Per-researcher score histogram already exists on the results detail page |

---

## Feature Dependencies

```
[Compound/derived name detection]
    └──enables──> [useStrictQueryOnly flag = true]
                      └──triggers──> [Affiliation strategies as supplementary search]

[Historical pipeline_run table + run_id on person_article_score]
    └──required by──> [Run selector on Results page]
    └──required by──> [Run selector on Stats page]
    └──required by──> [Run comparison view]
    └──required by──> [Pre-computed per-run AUC at completion]

[Dynamic MAX_WORKERS]
    └──depends on──> [API key available at pipeline start time]
                     (already retrieved via get_pubmed_api_key in _process_one_researcher)

[asyncio.as_completed ordering]
    └──independent — two-line change, no dependencies]

[Affiliation-filtered search]
    └──depends on──> [home_institution_keywords in institution config]
                     (already stored in DB from setup flow)
    └──conditional on──> [useStrictQueryOnly = true OR lenient count > threshold]

[retrieve_known mode PubMed fetch]
    └──independent of retrieval strategy changes]
    └──required by──> [Accurate scoring for PMID-upload-only researchers]

[update mode end-to-end]
    └──depends on──> [retrieval_log.last_retrieval_date populated correctly]
                     (already written in pipeline_runner.py line 183)
```

### Dependency Notes

- **Affiliation strategy requires institution keywords**: `home_institution_keywords` must be non-empty. Desktop already prompts for this in setup. If empty, the strategy must be silently skipped — same as Java's `if identity.getInstitutions() != null` guard at line 287 of `AliasReCiterRetrievalEngine`.
- **Historical runs require DB migration**: Adding `run_id` to `person_article_score` is a breaking schema change. Existing scores must be migrated as `run_id = 1` to avoid null FK violations. Plan migration script alongside schema definition.
- **Run selector requires historical runs**: Cannot build the UI without the data model. Phase ordering is strict — schema first, then selector.
- **Derived name detection must run before `search_by_name`**: The `useStrictQueryOnly` flag is determined by pre-processing identity names. This step must happen in `_process_one_researcher` before the search call, not inside `search_by_name`.

---

## MVP Definition

Context: this is a subsequent milestone on a working v1.0 product. "MVP" here means minimum to satisfy the paper validation goal (retrieval parity + reproducibility).

### Paper Validation Minimum

- [ ] **`asyncio.as_completed` ordering** — two-line change, no risk, immediate UX improvement
- [ ] **Dynamic MAX_WORKERS based on API key** — prevents 429 throttling in parallel runs
- [ ] **Affiliation-filtered search (AffiliationRetrievalStrategy)** — single biggest retrieval gap between Desktop and Java for researchers at named institutions
- [ ] **Compound/derived name detection and strict-only mode** — required for researchers with hyphenated or multi-word last names; affects a meaningful fraction of any roster
- [ ] **`retrieve_known` mode PubMed fetch** — without this, PMID-upload researchers have no metadata and score poorly

### Add After First Phase

- [ ] **Historical pipeline runs schema + run selector** — needed for reproducibility; medium complexity; requires migration
- [ ] **`update` mode integration test** — code present, needs validation against known test set
- [ ] **Per-researcher export button + source labeling** — low complexity, high librarian value
- [ ] **Search/filter on Results listing** — frontend-only, low complexity
- [ ] **Dashboard metrics** — frontend-only, data already available

### Future Consideration

- [ ] **Full 8-strategy cascade** (grant, department, known relationship, second initial) — adds marginal recall; implement only if parity testing reveals a gap vs Java on the 20-researcher test set
- [ ] **Run comparison view with overlaid ROC** — valuable but high complexity; defer until historical runs are stable
- [ ] **DepartmentRetrievalStrategy** — requires `organizational_units` field on identity, not currently in the identity CSV schema

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| asyncio.as_completed ordering | MEDIUM | LOW | P1 |
| Dynamic MAX_WORKERS | HIGH | LOW | P1 |
| Affiliation-filtered search | HIGH | HIGH | P1 |
| Compound/derived name detection | HIGH | MEDIUM | P1 |
| retrieve_known PubMed fetch | HIGH | MEDIUM | P1 |
| Historical pipeline_run table | HIGH | MEDIUM | P1 |
| Run selector on Results/Stats | MEDIUM | MEDIUM | P2 |
| update mode end-to-end test | HIGH | LOW | P2 |
| Per-researcher export button | MEDIUM | LOW | P2 |
| Source labeling (candidate vs known) | LOW | LOW | P2 |
| Search/filter on Results listing | MEDIUM | LOW | P2 |
| Dashboard metrics | LOW | LOW | P2 |
| Institution name display fix | LOW | LOW | P2 |
| Run comparison view | MEDIUM | HIGH | P3 |
| Full 8-strategy cascade | MEDIUM | HIGH | P3 |
| DepartmentRetrievalStrategy | LOW | MEDIUM | P3 |

**Priority key:**
- P1: Must have for paper validation
- P2: Should have, add during milestone implementation
- P3: Nice to have, future milestone

---

## Retrieval Strategy Reference (from Java source — read directly)

This section documents the exact Java cascade for Desktop implementation. Read from `AliasReCiterRetrievalEngine.java` and `AbstractRetrievalStrategy.java`.

### Condition Logic (from `AliasReCiterRetrievalEngine.retrieveData`)

```
1. Always run: GoldStandardRetrievalStrategy (fetch PubMed XML for known/rejected PMIDs)
2. If identity.orcid != null AND != "NOT SET": OrcidRetrievalStrategy
3. Always run: EmailRetrievalStrategy
4. Always run: FirstNameInitialRetrievalStrategy
   Lenient query: LastName FI[au]
   → Count lenient results (esearch count-only call)
   → If count <= 2000: fetch lenient results; queryType = LENIENT_LOOKUP
   → If count > 2000: set useStrictQueryOnly = true; queryType = STRICT_EXCEEDS_THRESHOLD_LOOKUP
                       store raw eSearchCount for ArticleSizeStrategy scoring

5. If useStrictQueryOnly == true OR lenient count > 2000:
   a. If identity.institutions non-empty: AffiliationInDbRetrievalStrategy
      Query: LastName FI[au] AND (InstitutionName[affiliation])
   b. AffiliationRetrievalStrategy (home institution keywords from config)
      Query: LastName FI[au] AND (keyword1[affiliation] OR keyword2[affiliation])
   c. If identity.organizationalUnits non-empty: DepartmentRetrievalStrategy
   d. If identity.grants non-empty: GrantRetrievalStrategy
   e. FullNameRetrievalStrategy
      Strict query: LastName FullFirstName[au]
   f. If identity.knownRelationships non-empty: KnownRelationshipRetrievalStrategy
   g. SecondInitialRetrievalStrategy

6. useStrictQueryOnly is ALSO set to true if DERIVED names exist (compound name check runs
   before the FirstNameInitial step).
```

### Thresholds Confirmed

| Threshold | Java value | Desktop default | Match? |
|-----------|------------|-----------------|--------|
| `DEFAULT_THRESHOLD` (lenient) | 2000 (`AbstractRetrievalStrategy.java` line 75) | 2000 (config) | Yes |
| `STRICT_THRESHOLD` | 1000 (`AbstractRetrievalStrategy.java` line 81) | 1000 (config) | Yes |

### Compound Name Detection Rules (from `identityAuthorNames()` and `deriveAdditionalName()`)

Trigger `useStrictQueryOnly = true` when any of these apply to primary or alternate name:
- `lastName.contains(" ") || lastName.contains("-")` AND both parts after split >= 4 chars
- `firstName.contains(" ") || firstName.contains(".")` (e.g., "W. Clay")
- `firstName.length() == 1 && middleName != null` (single-initial first name with middle name)

Derived name examples from `deriveAdditionalName()`:
- "Garcia Lopez" → also search `Garcia J[au]` OR `Lopez J[au]`
- "W. Clay Bracken" → also search `Clay B[au]` (middle as first) or `W B[au]`

Quoting rule (from `contsructAuthorQuery()` lines 161–163, 168–172):
- Lenient: if `lastName.contains(" ") || lastName.contains("-")` → `"De la Cruz J"[au]`
- Strict: if lastName OR firstName has space/hyphen → `"Garcia Lopez Maria"[au]`

### Desktop Retrieval Gap Summary

| Strategy | Java | Desktop | Gap |
|----------|------|---------|-----|
| FirstNameInitialRetrievalStrategy (lenient) | Yes | Yes | None |
| FirstNameInitialRetrievalStrategy (strict) | Yes | Yes | None — `search_by_name` strict path does `LastName FullFirstName[au]` |
| Lenient/strict thresholds | 2000/1000 | 2000/1000 | None |
| Compound name quoting (lenient) | Yes | Yes | None — `_build_author_term` line 292–293 |
| Compound name quoting (strict) | Yes | Partial | Verify: `_build_author_term(full_name=True)` checks `" " in last_name` — confirm hyphen is also covered |
| Derived name splitting → strict-only mode | Yes | No | **Gap** — needs pre-processing in `_process_one_researcher` |
| AffiliationRetrievalStrategy | Yes (conditional on threshold) | No | **Gap** — highest priority for paper parity |
| AffiliationInDbRetrievalStrategy | Yes (conditional) | No | **Gap** — medium priority |
| FullNameRetrievalStrategy | Yes (strict mode) | Partial | `search_by_name` strict path covers this for the primary name |
| OrcidRetrievalStrategy | Yes (if orcid set) | No | Medium priority — orcid field already in identity model |
| GoldStandardRetrievalStrategy | Yes | Partial (retrieve_known incomplete) | `retrieve_known` needs PubMed fetch wiring |
| EmailRetrievalStrategy | Yes | No | Low priority — PubMed email field rarely populated |
| DepartmentRetrievalStrategy | Yes (conditional) | No | Low priority — requires org unit field not in current CSV schema |
| GrantRetrievalStrategy | Yes (conditional) | No | Low priority — grant IDs rarely on identity records |

### Parallel Processing — Current vs Target

Current code (`pipeline_runner.py` lines 334–361):
- Submits all researchers to `ThreadPoolExecutor` concurrently (good)
- Awaits futures in **submission order** (not completion order) — means UI blocks on slowest researcher in each batch
- `MAX_WORKERS = min(4, cpu_count)` — ignores API key presence

Target behavior (from Java: `ExecutorService.newWorkStealingPool(15)` line 122 of `AliasReCiterRetrievalEngine`):
- Java uses work-stealing pool of 15 threads for retrieval
- Python equivalent: `asyncio.as_completed` for yield ordering + higher `MAX_WORKERS` with API key

Fix is two independent changes:
1. Replace `for pid in person_ids: result = await futures[pid]` with `for future in asyncio.as_completed(futures.values()):`
2. Set `MAX_WORKERS = 8 if api_key else 3` at pipeline start time

---

## Sources

- `/Users/paulalbert/Dropbox/GitHub/ReCiter/src/main/java/reciter/xml/retriever/engine/AliasReCiterRetrievalEngine.java` — primary retrieval orchestration; `identityAuthorNames()`, `deriveAdditionalName()`, `retrieveData()` cascade (read directly, HIGH confidence)
- `/Users/paulalbert/Dropbox/GitHub/ReCiter/src/main/java/reciter/xml/retriever/pubmed/AbstractRetrievalStrategy.java` — `DEFAULT_THRESHOLD=2000`, `STRICT_THRESHOLD=1000`, lenient/strict decision tree (read directly, HIGH confidence)
- `/Users/paulalbert/Dropbox/GitHub/ReCiter/src/main/java/reciter/xml/retriever/pubmed/PubMedQueryType.java` — `contsructAuthorQuery()` compound name quoting logic (read directly, HIGH confidence)
- `/Users/paulalbert/Dropbox/GitHub/ReCiter/src/main/java/reciter/xml/retriever/pubmed/AffiliationRetrievalStrategy.java` — home institution keyword query construction (read directly, HIGH confidence)
- `/Users/paulalbert/Dropbox/GitHub/ReCiter/src/main/java/reciter/xml/retriever/pubmed/AffiliationInDbRetrievalStrategy.java` — per-researcher institution query (read directly, HIGH confidence)
- `/Users/paulalbert/Dropbox/GitHub/ReCiter/src/main/java/reciter/xml/retriever/pubmed/FirstNameInitialRetrievalStrategy.java` — lenient query construction (read directly, HIGH confidence)
- `/Users/paulalbert/Dropbox/GitHub/ReCiter/src/main/java/reciter/xml/retriever/pubmed/FullNameRetrievalStrategy.java` — strict query construction (read directly, HIGH confidence)
- `/Users/paulalbert/Dropbox/GitHub/ReCiter-Desktop/core/pubmed.py` — current Desktop retrieval implementation (read directly, HIGH confidence)
- `/Users/paulalbert/Dropbox/GitHub/ReCiter-Desktop/api/services/pipeline_runner.py` — current parallel pipeline orchestration (read directly, HIGH confidence)
- `/Users/paulalbert/Dropbox/GitHub/ReCiter-Desktop/docs/milestones/milestone-2-pipeline-parity.md` — milestone requirements (read directly, HIGH confidence)
- `/Users/paulalbert/Dropbox/GitHub/ReCiter-Desktop/.planning/PROJECT.md` — project context and out-of-scope constraints (read directly, HIGH confidence)

---
*Feature research for: ReCiter Desktop v2.0 — Pipeline Parity & Performance milestone*
*Researched: 2026-04-05*

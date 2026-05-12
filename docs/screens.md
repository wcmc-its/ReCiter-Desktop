# ReCiter Desktop — Screen Reference

ASCII mockups of all application screens.

---

## 1. Dashboard

The home screen adapts based on progress. Shows numbered status cards and a guided next-step button.

```
+------------------------------------------------------------------+
| * ReCiter Desktop                                                |
+----------+-------------------------------------------------------+
| NAVIG.   |                                                       |
|          |  ReCiter Desktop                                      |
| Dashboard|  Score publications against researcher identities     |
| Inst.Set.|  using machine learning.                              |
| Research.|                                                       |
| Articles |  +-------------+ +-------------+ +-------------+ +---+-------+
| Pipeline |  | (1) INSTIT. | | (2) RESEAR. | | (3) ARTICLES| | (4) SCORES|
| Results  |  | Not config. | | Not uploaded| | Not yet ret.| | Not yet   |
| FAQ      |  +-------------+ +-------------+ +-------------+ +-----------+
|          |                                                       |
|          |  [ Set Up Your Institution ]                          |
|          |                                                       |
|          |  +--------------------------------------------------+ |
|          |  | About Scoring Models                              | |
|          |  | Your scores are based on identity evidence alone  | |
|          |  | (25 features). Curating articles unlocks a more   | |
|          |  | powerful 43-feature model.                        | |
|          |  +--------------------------------------------------+ |
+----------+-------------------------------------------------------+
```

After completing steps, cards show green checkmarks and counts:

```
  +(v) INSTIT. + +(v) RESEAR. + +(3) ARTICLES+ +(4) SCORES +
  | Fred Hutch | | 47 loaded  | | Not yet ret.| | Not yet    |
  +------------+ +------------+ +-------------+ +------------+
```

---

## 2. Institution Setup

Three-step wizard: Enter Domain, Discover, Classify.

### Step 1: Enter Domain

```
+----------+-------------------------------------------------------+
| NAVIG.   |                                                       |
|          |  Institution Setup                                    |
| Dashboard|  Configure your institution by entering your email    |
| *Inst.S.*|  domain. We will discover your profile from PubMed.  |
| Research.|                                                       |
| ...      |  (1) Enter Domain ------- (2) Discover ------ (3) Classify
|          |                                                       |
|          |  +--------------------------------------------------+ |
|          |  | Institution email domain                          | |
|          |  | [ e.g., fredhutch.org                           ] | |
|          |  |                                                  | |
|          |  | Institution name (optional)                      | |
|          |  | [ e.g., Fred Hutchinson Cancer Center           ] | |
|          |  |                                                  | |
|          |  | [ Discover ]                                     | |
|          |  +--------------------------------------------------+ |
+----------+-------------------------------------------------------+
```

### Step 2: Discovery Progress

```
|          |  (v) Enter Domain ------- (2) Discover ------ (3) Classify
|          |                                                       |
|          |  +--------------------------------------------------+ |
|          |  | v Searching PubMed for fredhutch.org...           | |
|          |  | v 412 articles found                              | |
|          |  | v 3 email domains discovered                     | |
|          |  | o Analyzing affiliations...                       | |
|          |  +--------------------------------------------------+ |
```

### Step 3: Classify Institutions

```
|          |  (v) Enter Domain ------- (v) Discover ------ (3) Classify
|          |                                                       |
|          |  +--------------------------------------------------+ |
|          |  | Classify discovered institutions                  | |
|          |  |                                                  | |
|          |  | Fred Hutchinson Cancer Center    [Home] Col Skip  | |
|          |  |   412 mentions                                   | |
|          |  |                                                  | |
|          |  | University of Washington        Home [Col] Skip  | |
|          |  |   89 mentions                                    | |
|          |  |                                                  | |
|          |  | Seattle Children's Hospital     Home Col [Skip]  | |
|          |  |   34 mentions                                    | |
|          |  +--------------------------------------------------+ |
|          |                                                       |
|          |  +--------------------------------------------------+ |
|          |  | Email domains                                    | |
|          |  | [x] @fredhutch.org  (423 occurrences)            | |
|          |  | [x] @uw.edu         (87 occurrences)             | |
|          |  | [x] @fhcrc.org      (12 occurrences)             | |
|          |  +--------------------------------------------------+ |
|          |                                                       |
|          |  [ Save Configuration ]                               |
```

---

## 3. Researchers

### Upload State

```
+----------+-------------------------------------------------------+
| NAVIG.   |                                                       |
|          |  Researchers                                          |
| Dashboard|  Upload your researcher list to get started.          |
| Inst.Set.|                                                       |
| *Resear.*|  + - - - - - - - - - - - - - - - - - - - - - - - - + |
| ...      |  |                                                  | |
|          |  |       Upload your researcher list                | |
|          |  |                                                  | |
|          |  |  A spreadsheet with one row per researcher.      | |
|          |  |  At minimum: unique ID, first name, last name.   | |
|          |  |  Optional: email, title, institution, dept,      | |
|          |  |  doctoral year, ORCID.                           | |
|          |  |                                                  | |
|          |  |  CSV, Excel (.xlsx, .xls), or TSV                | |
|          |  |                                                  | |
|          |  |  [ Browse files ]  or  Download sample template   | |
|          |  |                                                  | |
|          |  |  Column names are flexible -- we recognize       | |
|          |  |  many common variations.                         | |
|          |  + - - - - - - - - - - - - - - - - - - - - - - - - + |
+----------+-------------------------------------------------------+
```

### Column Mapping State

```
|          |  fredhutch_researchers.csv -- 47 rows    [Upload different file]
|          |                                                       |
|          |  We detected 8 columns. Confirm mappings.  [Select All] [Deselect]
|          |                                                       |
|          |  +--------------------------------------------------+ |
|          |  |    YOUR COLUMN     -->  MAPS TO       SAMPLE     | |
|          |  |----|--------------|-----|------------|------------| |
|          |  | [x] emp_id        -->  Person ID     jsmith42    | |
|          |  | [x] fname         -->  First Name    Jane        | |
|          |  | [x] lname         -->  Last Name     Smith       | |
|          |  | [x] middle_init   -->  Middle Name   A           | |
|          |  | [x] email_addr    -->  Email         jsmith@...  | |
|          |  | [x] division      -->  Department    Clinical R. | |
|          |  | [x] phd_year      -->  Doctoral Year 2008        | |
|          |  | [ ] orcid_url     -->  [Select...v]  0000-0001.. | |
|          |  +--------------------------------------------------+ |
|          |                                                       |
|          |  +--------------------------------------------------+ |
|          |  | (v) Curation data detected                       | |
|          |  | We found 1,427 accept/reject records.            | |
|          |  | Import this data to enable the more accurate     | |
|          |  | scoring model.                                   | |
|          |  +--------------------------------------------------+ |
|          |                                                       |
|          |                      [Cancel]  [ Import 47 Researchers ]
```

### Success State

```
|          |  +--------------------------------------------------+ |
|          |  |         47 researchers loaded                    | |
|          |  |     1,427 curation records imported              | |
|          |  |                                                  | |
|          |  |          [ Continue to Pipeline ]                | |
|          |  +--------------------------------------------------+ |
```

---

## 4. Articles (Scoring Only Mode)

```
+----------+-------------------------------------------------------+
| NAVIG.   |                                                       |
|          |  Articles                                             |
| Dashboard|  Upload a list of known PMIDs to score. Use this     |
| ...      |  when you already have publication lists and just     |
| *Article*|  need scores (Scoring Only mode).                     |
| ...      |                                                       |
|          |  If you want to discover new articles from PubMed,    |
|          |  skip this and run the pipeline in Full Retrieval     |
|          |  and Scoring mode.                                    |
|          |                                                       |
|          |  + - - - - - - - - - - - - - - - - - - - - - - - - + |
|          |  |  A spreadsheet with person_id and pmid columns.  | |
|          |  |  Each row links a researcher to an article.       | |
|          |  |                                                  | |
|          |  |  [ Browse files ]  or  Download sample template   | |
|          |  + - - - - - - - - - - - - - - - - - - - - - - - - + |
+----------+-------------------------------------------------------+
```

---

## 5. Processing Pipeline

### Before Running

```
+----------+-------------------------------------------------------+
| NAVIG.   |                                                       |
|          |  Processing Pipeline                                  |
| Dashboard|  Run the scoring pipeline for all researchers.        |
| ...      |                                                       |
| *Pipelin*|  [Full Retrieval and Scoring]  [Scoring Only]         |
| ...      |                                                       |
|          |  [ Run Pipeline (47 researchers) ]                    |
+----------+-------------------------------------------------------+
```

### During Processing

```
|          |  Processing Pipeline                                  |
|          |                                                       |
|          |  Overall Progress                                     |
|          |  12 of 47 researchers * 1,847 articles * 823 scored   |
|          |  [==========>                                       ] |
|          |                                                       |
|          |  * Complete  * Retrieving  * Matching  * Analyzing  * Scoring
|          |                                                       |
|          |  RESEARCHER         UID        ARTICLES STATUS     PROG
|          |  ----------------------------------------------------------------
|          |  Dr. Maria Lopez    ml4523     67       Scoring     [====]
|          |  Dr. Tom Park       tp8901     203      Analyzing   [==  ]
|          |  Dr. Sarah Kim      sk2210     156      Matching    [=== ]
|          |  Dr. Michael Torres mt7744     --       Retrieving  [==  ]
|          |  Dr. Lisa Wang      lw3389     --       Queued
|          |  Dr. James Wilson   jw0012     --       Queued
|          |  ... and 33 more queued                               |
|          |                                                       |
|          |  -----------------------------------------------      |
|          |  v 12 complete                            [Show v]    |
```

### After Re-run (Incremental)

```
|          |  [Update (new publications only)]  [Scoring Only]     |
|          |                                                       |
|          |  Only newly added publications since the last run     |
|          |  will be retrieved and scored. Previously scored       |
|          |  articles are kept.                                   |
|          |                                                       |
|          |  [ Run Pipeline (47 researchers) ]                    |
```

---

## 6. Results — Researcher List

```
+----------+-------------------------------------------------------+
| NAVIG.   |                                                       |
|          |  Results                        [Export All Results]   |
| Dashboard|  47 researchers scored                                |
| ...      |                                                       |
| *Results*|  RESEARCHER         UID       ARTICLES  SCORED        |
| ...      |  ---------------------------------------------------------
|          |  Jane Smith         js1234    142       142    View -> |
|          |  Robert Chen        rc5678    89        89     View -> |
|          |  Angela Rivera      ar9012    211       211    View -> |
|          |  Maria Lopez        ml4523    67        67     View -> |
|          |  ...                                                  |
+----------+-------------------------------------------------------+
```

---

## 7. Results — Researcher Detail

```
+----------+-------------------------------------------------------+
| NAVIG.   |                                                       |
|          |  Jane Smith                          [Export CSV]      |
| Dashboard|  js1234                                               |
| ...      |  142 articles scored                                  |
| *Results*|                                                       |
| ...      |  Threshold: [------|--------] 70   87 above | 55 below
|          |                                                       |
|          |  Sort: [Score] [Year] [Journal]                        |
|          |                                                       |
|          |  SCORE  TITLE                            JOURNAL  YEAR  LINK
|          |  ----------------------------------------------------------------
|          |  [98]   Machine learning approaches      JAMIA    2024  PubMed
|          |         for author name disambiguation                 |
|          |  [95]   Evaluating institutional          Sciento. 2023  PubMed
|          |         publication records...                         |
|          |  [52]   A systematic review of NLP        BMC Med  2022  PubMed
|          |         in clinical informatics...                     |
|          |  [12]   Genomic variants in pediatric     Blood    2021  PubMed
|          |         acute lymphoblastic leukemia...                |
|          |  [ 3]   Cardiovascular outcomes in        Lancet   2020  PubMed
|          |         patients with type 2 diabetes...               |
|          |  ... 137 more articles                                |
+----------+-------------------------------------------------------+

  Score color key:  [##] >= 70 green  |  [##] 30-70 amber  |  [##] < 30 red
```

---

## 8. FAQ

```
+----------+-------------------------------------------------------+
| NAVIG.   |                                                       |
|          |  Frequently Asked Questions                           |
| Dashboard|  Common questions about ReCiter Desktop and the       |
| ...      |  scoring pipeline.                                    |
| *FAQ*    |                                                       |
| ...      |  +--------------------------------------------------+ |
|          |  | What is ReCiter Desktop?                     [v]  | |
|          |  +--------------------------------------------------+ |
|          |  +--------------------------------------------------+ |
|          |  | How does the scoring work?                   [v]  | |
|          |  +--------------------------------------------------+ |
|          |  +--------------------------------------------------+ |
|          |  | What is the difference between 'Full         [^]  | |
|          |  | Retrieval' and 'Scoring Only'?                    | |
|          |  |                                                  | |
|          |  | In Full Retrieval and Scoring mode, the system   | |
|          |  | searches PubMed by researcher name to discover   | |
|          |  | candidate publications, then scores them. In     | |
|          |  | Scoring Only mode, you upload a list of known    | |
|          |  | PMIDs and the system scores just those articles.  | |
|          |  +--------------------------------------------------+ |
|          |  +--------------------------------------------------+ |
|          |  | What do I need to get started?                [v] | |
|          |  +--------------------------------------------------+ |
|          |  +--------------------------------------------------+ |
|          |  | What format should my researcher file be in? [v]  | |
|          |  +--------------------------------------------------+ |
|          |  ... (15 questions total)                              |
+----------+-------------------------------------------------------+
```

---

## Navigation Flow

```
  Dashboard ──> Institution Setup ──> Researchers ──> Pipeline ──> Results
      |                                    |              |
      |                                    v              v
      |                               Articles       Results/[id]
      |                          (Scoring Only mode)
      v
     FAQ
```

"""
pubmed.py — PubMed E-utilities API client.

Thin wrapper around NCBI efetch/esearch with rate limiting and XML parsing.
"""

import logging
import threading
import time
import xml.etree.ElementTree as ET
from typing import Callable, List, Optional

import requests

from core.article import Article, Author, MeshHeading

_log = logging.getLogger(__name__)

EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"

_BATCH_SIZE = 200


class _TokenBucket:
    """Thread-safe token bucket rate limiter.

    Allows concurrent requests up to `rate` per second. Each call to
    acquire() blocks only if tokens are exhausted, letting multiple
    threads make simultaneous PubMed calls.
    """

    def __init__(self, rate: float):
        self.rate = rate
        self.tokens = rate
        self.max_tokens = rate
        self.last_refill = time.monotonic()
        self.lock = threading.Lock()

    def set_rate(self, rate: float):
        with self.lock:
            self.rate = rate
            self.max_tokens = rate
            self.tokens = min(self.tokens, rate)

    def acquire(self):
        while True:
            with self.lock:
                now = time.monotonic()
                elapsed = now - self.last_refill
                self.tokens = min(self.max_tokens, self.tokens + elapsed * self.rate)
                self.last_refill = now
                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return
            time.sleep(0.05)  # Brief sleep before retry


# Global bucket — default to no-key rate (3/sec), upgraded when API key detected
_bucket = _TokenBucket(rate=2.5)
_bucket_configured_for_key = False


def _rate_limit(api_key: str = ""):
    """Acquire a token before making a PubMed request.

    With API key: allows ~9 concurrent requests/sec.
    Without: ~2.5 requests/sec.
    """
    global _bucket_configured_for_key
    if api_key and not _bucket_configured_for_key:
        _bucket.set_rate(9.0)
        _bucket_configured_for_key = True
    elif not api_key and _bucket_configured_for_key:
        _bucket.set_rate(2.5)
        _bucket_configured_for_key = False
    _bucket.acquire()


def _parse_author(author_el: ET.Element, rank: int) -> Author:
    """Parse a single author element from PubMed XML."""
    last_name = (author_el.findtext("LastName") or "").strip()
    fore_name = (author_el.findtext("ForeName") or "").strip()
    initials = (author_el.findtext("Initials") or "").strip()

    # Extract first name from ForeName (may include middle name)
    first_name = fore_name.split()[0] if fore_name else ""

    affiliation_el = author_el.find(".//AffiliationInfo/Affiliation")
    affiliation = (affiliation_el.text or "").strip() if affiliation_el is not None else ""

    # ORCID from Identifier
    orcid = ""
    for ident in author_el.findall("Identifier"):
        if ident.get("Source") == "ORCID":
            orcid = (ident.text or "").strip()
            # Normalize: strip URL prefix
            if orcid.startswith("http"):
                orcid = orcid.rstrip("/").split("/")[-1]

    return Author(
        first_name=first_name,
        last_name=last_name,
        initials=initials,
        affiliation=affiliation,
        orcid=orcid,
        rank=rank,
    )


def _parse_mesh(mesh_el: ET.Element) -> MeshHeading:
    """Parse a MeshHeading element."""
    desc_el = mesh_el.find("DescriptorName")
    descriptor = (desc_el.text or "").strip() if desc_el is not None else ""
    major = desc_el.get("MajorTopicYN", "N") == "Y" if desc_el is not None else False

    qualifiers = []
    for qual_el in mesh_el.findall("QualifierName"):
        qualifiers.append((qual_el.text or "").strip())
        if qual_el.get("MajorTopicYN") == "Y":
            major = True

    return MeshHeading(
        descriptor_name=descriptor,
        qualifier_names=qualifiers,
        major_topic=major,
    )


def _parse_article(article_el: ET.Element) -> Optional[Article]:
    """Parse a PubmedArticle element into an Article object."""
    medline = article_el.find("MedlineCitation")
    if medline is None:
        return None

    pmid_el = medline.find("PMID")
    pmid = int(pmid_el.text) if pmid_el is not None and pmid_el.text else 0
    if not pmid:
        return None

    art = medline.find("Article")
    if art is None:
        return None

    title = (art.findtext("ArticleTitle") or "").strip()
    abstract_el = art.find("Abstract/AbstractText")
    abstract = (abstract_el.text or "").strip() if abstract_el is not None else ""

    # Journal info
    journal_el = art.find("Journal")
    journal_title = ""
    journal_issn = []
    if journal_el is not None:
        journal_title = (journal_el.findtext("Title") or "").strip()
        issn_el = journal_el.find("ISSN")
        if issn_el is not None and issn_el.text:
            journal_issn.append(issn_el.text.strip())
        # Also check MedlineJournalInfo for NlmUniqueID-based ISSN
        medline_ji = medline.find("MedlineJournalInfo")
        if medline_ji is not None:
            nlm_id = medline_ji.findtext("NlmUniqueID")
            if nlm_id:
                pass  # NLM ID stored separately if needed

    # Publication date
    pub_year = 0
    pub_date = ""
    pub_date_el = art.find("Journal/JournalIssue/PubDate")
    if pub_date_el is not None:
        year_text = pub_date_el.findtext("Year") or ""
        if year_text.isdigit():
            pub_year = int(year_text)
        medline_date = pub_date_el.findtext("MedlineDate") or ""
        if not pub_year and medline_date:
            # Extract year from MedlineDate like "2023 Jan-Feb"
            parts = medline_date.split()
            if parts and parts[0].isdigit():
                pub_year = int(parts[0])

    # Authors
    authors = []
    author_list = art.find("AuthorList")
    if author_list is not None:
        for i, author_el in enumerate(author_list.findall("Author")):
            authors.append(_parse_author(author_el, rank=i + 1))

    # MeSH headings
    mesh_headings = []
    mesh_list = medline.find("MeshHeadingList")
    if mesh_list is not None:
        for mesh_el in mesh_list.findall("MeshHeading"):
            mesh_headings.append(_parse_mesh(mesh_el))

    # Keywords
    keywords = []
    for kw_list in medline.findall("KeywordList"):
        for kw_el in kw_list.findall("Keyword"):
            if kw_el.text:
                keywords.append(kw_el.text.strip())

    # Grants
    grants = []
    grant_list = art.find("GrantList")
    if grant_list is not None:
        for grant_el in grant_list.findall("Grant"):
            grant_id = grant_el.findtext("GrantID") or ""
            if grant_id:
                grants.append(grant_id.strip())

    # Publication types
    pub_types = []
    for pt_el in art.findall("PublicationTypeList/PublicationType"):
        if pt_el.text:
            pub_types.append(pt_el.text.strip())

    # DOI
    doi = ""
    for eid in art.findall("ELocationID"):
        if eid.get("EIdType") == "doi":
            doi = (eid.text or "").strip()

    return Article(
        pmid=pmid,
        title=title,
        journal_title=journal_title,
        journal_issn=journal_issn,
        pub_year=pub_year,
        pub_date=pub_date,
        authors=authors,
        mesh_headings=mesh_headings,
        keywords=keywords,
        grants=grants,
        publication_types=pub_types,
        doi=doi,
        abstract=abstract,
    )


def fetch_articles(
    pmids: List[int],
    api_key: str = "",
    on_batch: Optional[Callable[[dict], None]] = None,
) -> List[Article]:
    """Fetch article metadata from PubMed by PMID, in batches of 200.

    If `on_batch` is provided, it's invoked after each batch with:
        {batch, batches, fetched, total, error?: str}
    """
    articles = []
    total = len(pmids)
    batches = (total + _BATCH_SIZE - 1) // _BATCH_SIZE if total else 0
    for i in range(0, total, _BATCH_SIZE):
        batch = pmids[i : i + _BATCH_SIZE]
        batch_idx = i // _BATCH_SIZE + 1
        _rate_limit(api_key)

        params = {
            "db": "pubmed",
            "id": ",".join(str(p) for p in batch),
            "rettype": "xml",
            "retmode": "xml",
        }
        if api_key:
            params["api_key"] = api_key

        batch_error: Optional[str] = None
        try:
            resp = requests.get(EFETCH_URL, params=params, timeout=30)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
            for article_el in root.findall("PubmedArticle"):
                article = _parse_article(article_el)
                if article:
                    articles.append(article)
        except requests.RequestException as e:
            batch_error = f"PubMed request failed: {e}"
            _log.error(f"PubMed efetch failed for batch {batch_idx}: {e}")
        except ET.ParseError as e:
            batch_error = f"PubMed returned invalid XML: {e}"
            _log.error(f"Failed to parse PubMed XML for batch {batch_idx}: {e}")

        _log.info(f"Fetched {len(articles)} articles so far ({i + len(batch)}/{total} PMIDs)")

        if on_batch:
            event = {
                "batch": batch_idx,
                "batches": batches,
                "fetched": len(articles),
                "total": total,
            }
            if batch_error:
                event["error"] = batch_error
            on_batch(event)

    return articles


def _build_author_term(last_name: str, first_name: str, full_name: bool = False) -> str:
    """Build a PubMed [au] search term.

    Matches ReCiter's PubMedQueryBuilder:
    - full_name=False (lenient): LastName FirstInitial[au]
    - full_name=True  (strict):  LastName FirstName[au]

    Compound names (spaces/hyphens) are quoted.
    """
    if full_name:
        name_part = f"{last_name} {first_name}"
    else:
        name_part = f"{last_name} {first_name[0]}" if first_name else last_name

    if " " in last_name or "-" in last_name:
        return f'"{name_part}"[au]'
    return f"{name_part}[au]"


def _incremental_date_filter(mindate: str) -> str:
    """Build a PubMed date filter that matches upstream's incremental window.

    Upstream ReCiter (PubMedQuery.java) uses both Entry Date (EDAT) AND
    Publication Date (DP/PDAT) so late-indexed articles — pub_year in the
    past, indexed in PubMed recently — are not silently missed on
    incremental update runs. PDAT alone would skip them.
    """
    if not mindate:
        return ""
    return (
        f' AND (("{mindate}"[EDAT] : "3000"[EDAT])'
        f' OR ("{mindate}"[PDAT] : "3000"[PDAT]))'
    )


def esearch_count(query: str, api_key: str = "") -> int:
    """Get the result count for an esearch query without fetching IDs.

    This is the equivalent of ReCiter's getNumberOfResults() —
    a cheap count-only call used to decide strict vs lenient strategy.
    """
    # Mirrors AbstractRetrievalStrategy guard from upstream 0c75df92:
    # short-circuit empty or "()" terms instead of round-tripping PubMed.
    stripped = (query or "").strip()
    if not stripped or stripped == "()":
        _log.info(f"Skipping degenerate count query [{stripped}]")
        return 0
    _rate_limit(api_key)
    params = {
        "db": "pubmed",
        "term": query,
        "rettype": "count",
        "retmode": "xml",
    }
    if api_key:
        params["api_key"] = api_key

    try:
        resp = requests.get(ESEARCH_URL, params=params, timeout=30)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        count_text = root.findtext("Count")
        count = int(count_text) if count_text and count_text.isdigit() else 0
        _log.info(f"esearch count for '{query}': {count}")
        return count
    except (requests.RequestException, ET.ParseError) as e:
        _log.error(f"esearch count failed for '{query}': {e}")
        return 0


def _esearch_fetch_ids(query: str, max_results: int, api_key: str = "") -> List[int]:
    """Execute an esearch and return all PMIDs, paginating if needed."""
    pmids: List[int] = []
    retstart = 0
    batch = min(max_results, 10000)  # PubMed max retmax is 100000

    while retstart < max_results:
        _rate_limit(api_key)
        params = {
            "db": "pubmed",
            "term": query,
            "retmax": min(batch, max_results - retstart),
            "retstart": retstart,
            "rettype": "uilist",
            "retmode": "xml",
        }
        if api_key:
            params["api_key"] = api_key

        try:
            resp = requests.get(ESEARCH_URL, params=params, timeout=30)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
        except (requests.RequestException, ET.ParseError) as e:
            _log.error(f"esearch fetch failed at retstart={retstart}: {e}")
            break

        batch_ids = []
        for id_el in root.findall(".//IdList/Id"):
            if id_el.text and id_el.text.isdigit():
                batch_ids.append(int(id_el.text))

        if not batch_ids:
            break
        pmids.extend(batch_ids)
        retstart += len(batch_ids)

        # If we got fewer than requested, we've exhausted results
        if len(batch_ids) < batch:
            break

    return pmids


def search_by_name(
    first_name: str,
    last_name: str,
    affiliation: str = "",
    api_key: str = "",
    lenient_threshold: int = 3000,
    strict_threshold: int = 1500,
    mindate: str = "",
) -> dict:
    """Search PubMed using ReCiter's exact cascading retrieval strategy.

    Decision tree (matches AbstractRetrievalStrategy.retrievePubMedArticles):
    1. Build lenient query: LastName FirstInitial[au]
    2. esearch count for lenient query
    3. If count <= lenient_threshold (3000): fetch all lenient results
    4. If count > lenient_threshold:
       a. Build strict query: LastName FullFirstName[au]
       b. esearch count for strict query
       c. If strict count <= strict_threshold (1500): fetch strict results
       d. If strict count > strict_threshold: skip (too ambiguous)

    Returns a dict with retrieval metadata:
        {
            "pmids": [...],
            "query_type": "lenient" | "strict" | "skipped",
            "lenient_query": str,
            "lenient_count": int,
            "strict_query": str | None,
            "strict_count": int | None,
        }
    """
    lenient_base = _build_author_term(last_name, first_name, full_name=False)
    strict_base = _build_author_term(last_name, first_name, full_name=True)

    # Append date filter for incremental retrieval (ONLY_NEWLY_ADDED_PUBLICATIONS).
    # Uses EDAT OR PDAT (matches upstream PubMedQuery.java) so late-indexed
    # articles are not silently missed on update runs.
    date_filter = _incremental_date_filter(mindate)
    lenient_query = lenient_base + date_filter
    strict_query = strict_base + date_filter

    result = {
        "pmids": [],
        "query_type": "skipped",
        "lenient_query": lenient_query,
        "lenient_count": 0,
        "strict_query": strict_query,
        "strict_count": None,
        "mindate": mindate or None,
    }

    # Step 1: lenient count
    lenient_count = esearch_count(lenient_query, api_key)
    result["lenient_count"] = lenient_count

    if lenient_count == 0:
        result["query_type"] = "lenient"
        _log.info(f"Search '{lenient_query}': 0 results")
        return result

    if lenient_count <= lenient_threshold:
        # Step 2a: lenient count is manageable — fetch all
        pmids = _esearch_fetch_ids(lenient_query, lenient_count, api_key)
        result["pmids"] = pmids
        result["query_type"] = "lenient"
        _log.info(
            f"Search '{lenient_query}': {lenient_count} count, "
            f"fetched {len(pmids)} (lenient, under threshold {lenient_threshold})"
        )
        return result

    # Step 2b: lenient count exceeds threshold — try strict
    _log.info(
        f"Search '{lenient_query}': {lenient_count} count exceeds "
        f"lenient threshold {lenient_threshold}, switching to strict"
    )
    strict_count = esearch_count(strict_query, api_key)
    result["strict_count"] = strict_count

    if strict_count <= strict_threshold:
        # Step 3a: strict count is manageable — fetch all
        pmids = _esearch_fetch_ids(strict_query, strict_count, api_key)
        result["pmids"] = pmids
        result["query_type"] = "strict"
        _log.info(
            f"Search '{strict_query}': {strict_count} count, "
            f"fetched {len(pmids)} (strict, under threshold {strict_threshold})"
        )
        return result

    # Step 3b: strict count also too high — skip
    _log.warning(
        f"Search '{strict_query}': {strict_count} count exceeds "
        f"strict threshold {strict_threshold}, skipping retrieval"
    )
    result["query_type"] = "skipped"
    return result


def _normalize_orcid(orcid: str) -> str:
    """Strip URL prefixes and whitespace from an ORCID."""
    if not orcid:
        return ""
    o = orcid.strip()
    for prefix in ("https://orcid.org/", "http://orcid.org/", "orcid.org/"):
        if o.startswith(prefix):
            o = o[len(prefix):]
            break
    return o.strip().strip("/")


def search_by_orcid(orcid: str, api_key: str = "", mindate: str = "") -> dict:
    """Search PubMed by ORCID using the [auid] qualifier.

    Mirrors upstream OrcidRetrievalStrategy (commit 7dfa0754): a precise
    retrieval path that catches articles where the author's name in PubMed
    is misspelled or transliterated differently from the identity record.
    Lenient and strict are equivalent because [auid] is inherently precise,
    so no threshold cascade is needed.

    Returns:
        {
            "pmids": [...],
            "query": str,
            "count": int,
            "orcid": str | None,
        }
        An empty/invalid ORCID returns count=0 and an empty pmids list.
    """
    normalized = _normalize_orcid(orcid)
    result = {"pmids": [], "query": "", "count": 0, "orcid": normalized or None}
    if not normalized:
        return result

    query = f"{normalized}[auid]" + _incremental_date_filter(mindate)
    result["query"] = query

    count = esearch_count(query, api_key)
    result["count"] = count
    if count == 0:
        _log.info(f"ORCID search '{query}': 0 results")
        return result

    pmids = _esearch_fetch_ids(query, count, api_key)
    result["pmids"] = pmids
    _log.info(f"ORCID search '{query}': {count} count, fetched {len(pmids)}")
    return result

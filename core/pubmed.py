"""
pubmed.py — PubMed E-utilities API client.

Thin wrapper around NCBI efetch/esearch with rate limiting and XML parsing.
"""

import logging
import time
import xml.etree.ElementTree as ET
from typing import List, Optional

import requests

from core.article import Article, Author, MeshHeading

_log = logging.getLogger(__name__)

EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"

_BATCH_SIZE = 200
_last_request_time = 0.0


def _rate_limit(api_key: str = ""):
    """Enforce rate limiting between requests."""
    global _last_request_time
    interval = 0.1 if api_key else 0.34  # 10/sec with key, 3/sec without
    elapsed = time.time() - _last_request_time
    if elapsed < interval:
        time.sleep(interval - elapsed)
    _last_request_time = time.time()


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


def fetch_articles(pmids: List[int], api_key: str = "") -> List[Article]:
    """Fetch article metadata from PubMed by PMID, in batches of 200."""
    articles = []
    for i in range(0, len(pmids), _BATCH_SIZE):
        batch = pmids[i : i + _BATCH_SIZE]
        _rate_limit(api_key)

        params = {
            "db": "pubmed",
            "id": ",".join(str(p) for p in batch),
            "rettype": "xml",
            "retmode": "xml",
        }
        if api_key:
            params["api_key"] = api_key

        try:
            resp = requests.get(EFETCH_URL, params=params, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            _log.error(f"PubMed efetch failed for batch starting at index {i}: {e}")
            continue

        try:
            root = ET.fromstring(resp.content)
        except ET.ParseError as e:
            _log.error(f"Failed to parse PubMed XML: {e}")
            continue

        for article_el in root.findall("PubmedArticle"):
            article = _parse_article(article_el)
            if article:
                articles.append(article)

        _log.info(f"Fetched {len(articles)} articles so far ({i + len(batch)}/{len(pmids)} PMIDs)")

    return articles


def search_by_name(
    first_name: str,
    last_name: str,
    affiliation: str = "",
    api_key: str = "",
    max_results: int = 2000,
) -> List[int]:
    """Search PubMed by author name, optionally filtered by affiliation."""
    _rate_limit(api_key)

    # Build search term
    author_term = f"{last_name} {first_name[0] if first_name else ''}[Author]"
    if affiliation:
        search_term = f"({author_term}) AND ({affiliation}[Affiliation])"
    else:
        search_term = author_term

    params = {
        "db": "pubmed",
        "term": search_term,
        "retmax": max_results,
        "rettype": "uilist",
        "retmode": "xml",
    }
    if api_key:
        params["api_key"] = api_key

    try:
        resp = requests.get(ESEARCH_URL, params=params, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        _log.error(f"PubMed esearch failed: {e}")
        return []

    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError as e:
        _log.error(f"Failed to parse esearch XML: {e}")
        return []

    pmids = []
    for id_el in root.findall(".//IdList/Id"):
        if id_el.text and id_el.text.isdigit():
            pmids.append(int(id_el.text))

    count_el = root.findtext("Count")
    total = int(count_el) if count_el and count_el.isdigit() else len(pmids)
    _log.info(f"PubMed search '{search_term}': {total} total, returning {len(pmids)}")

    return pmids

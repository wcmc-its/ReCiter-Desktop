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
            domain = match.group(1).lower().rstrip(".")
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

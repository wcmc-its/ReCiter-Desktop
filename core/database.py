"""
database.py — SQLite persistence layer.

Stores identities, articles, person-article associations,
curations, and cached scores.
"""

import json
import logging
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core.article import Article, Author, MeshHeading
from core.identity import Identity

_log = logging.getLogger(__name__)

_DB_DIR = Path.home() / ".reciter-desktop"
_DB_PATH = _DB_DIR / "reciter.db"


def get_connection() -> sqlite3.Connection:
    """Get a database connection, creating the DB and tables if needed."""
    _DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _create_tables(conn)
    return conn


def _create_tables(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS identities (
            person_id TEXT PRIMARY KEY,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            middle_name TEXT DEFAULT '',
            primary_email TEXT DEFAULT '',
            primary_institution TEXT DEFAULT '',
            department TEXT DEFAULT '',
            title TEXT DEFAULT '',
            orcid TEXT DEFAULT '',
            bachelor_year INTEGER DEFAULT 0,
            doctoral_year INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS articles (
            pmid INTEGER PRIMARY KEY,
            title TEXT DEFAULT '',
            journal_title TEXT DEFAULT '',
            journal_issn TEXT DEFAULT '[]',
            pub_year INTEGER DEFAULT 0,
            pub_date TEXT DEFAULT '',
            authors_json TEXT DEFAULT '[]',
            mesh_json TEXT DEFAULT '[]',
            keywords_json TEXT DEFAULT '[]',
            grants_json TEXT DEFAULT '[]',
            publication_types_json TEXT DEFAULT '[]',
            doi TEXT DEFAULT '',
            abstract TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS person_articles (
            person_id TEXT NOT NULL,
            pmid INTEGER NOT NULL,
            PRIMARY KEY (person_id, pmid),
            FOREIGN KEY (person_id) REFERENCES identities(person_id),
            FOREIGN KEY (pmid) REFERENCES articles(pmid)
        );

        CREATE TABLE IF NOT EXISTS curations (
            person_id TEXT NOT NULL,
            pmid INTEGER NOT NULL,
            assertion TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (person_id, pmid),
            FOREIGN KEY (person_id) REFERENCES identities(person_id),
            FOREIGN KEY (pmid) REFERENCES articles(pmid)
        );

        CREATE TABLE IF NOT EXISTS scores (
            person_id TEXT NOT NULL,
            pmid INTEGER NOT NULL,
            model_type TEXT NOT NULL,
            model_dir TEXT NOT NULL,
            raw_score REAL,
            calibrated_score REAL,
            features_json TEXT DEFAULT '{}',
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (person_id, pmid, model_type, model_dir),
            FOREIGN KEY (person_id) REFERENCES identities(person_id),
            FOREIGN KEY (pmid) REFERENCES articles(pmid)
        );
    """)
    conn.commit()


# ── Identity CRUD ────────────────────────────────────────────────────────────

def save_identity(conn: sqlite3.Connection, identity: Identity):
    conn.execute("""
        INSERT OR REPLACE INTO identities
        (person_id, first_name, last_name, middle_name, primary_email,
         primary_institution, department, title, orcid, bachelor_year, doctoral_year)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        identity.person_id, identity.first_name, identity.last_name,
        identity.middle_name, identity.primary_email, identity.primary_institution,
        identity.department, identity.title, identity.orcid,
        identity.bachelor_year, identity.doctoral_year,
    ))
    conn.commit()


def save_identities(conn: sqlite3.Connection, identities: List[Identity]):
    for identity in identities:
        save_identity(conn, identity)


def get_identity(conn: sqlite3.Connection, person_id: str) -> Optional[Identity]:
    row = conn.execute(
        "SELECT * FROM identities WHERE person_id = ?", (person_id,)
    ).fetchone()
    if row is None:
        return None
    return Identity(
        person_id=row["person_id"],
        first_name=row["first_name"],
        last_name=row["last_name"],
        middle_name=row["middle_name"],
        primary_email=row["primary_email"],
        primary_institution=row["primary_institution"],
        department=row["department"],
        title=row["title"],
        orcid=row["orcid"],
        bachelor_year=row["bachelor_year"],
        doctoral_year=row["doctoral_year"],
    )


def get_all_identities(conn: sqlite3.Connection) -> List[Identity]:
    rows = conn.execute("SELECT * FROM identities ORDER BY person_id").fetchall()
    return [
        Identity(
            person_id=r["person_id"], first_name=r["first_name"],
            last_name=r["last_name"], middle_name=r["middle_name"],
            primary_email=r["primary_email"],
            primary_institution=r["primary_institution"],
            department=r["department"], title=r["title"],
            orcid=r["orcid"], bachelor_year=r["bachelor_year"],
            doctoral_year=r["doctoral_year"],
        )
        for r in rows
    ]


def delete_identity(conn: sqlite3.Connection, person_id: str):
    conn.execute("DELETE FROM curations WHERE person_id = ?", (person_id,))
    conn.execute("DELETE FROM scores WHERE person_id = ?", (person_id,))
    conn.execute("DELETE FROM person_articles WHERE person_id = ?", (person_id,))
    conn.execute("DELETE FROM identities WHERE person_id = ?", (person_id,))
    conn.commit()


# ── Article CRUD ─────────────────────────────────────────────────────────────

def _article_to_row(article: Article) -> tuple:
    authors_json = json.dumps([
        {
            "first_name": a.first_name, "last_name": a.last_name,
            "initials": a.initials, "affiliation": a.affiliation,
            "orcid": a.orcid, "rank": a.rank,
        }
        for a in article.authors
    ])
    mesh_json = json.dumps([
        {
            "descriptor_name": m.descriptor_name,
            "qualifier_names": m.qualifier_names,
            "major_topic": m.major_topic,
        }
        for m in article.mesh_headings
    ])
    return (
        article.pmid, article.title, article.journal_title,
        json.dumps(article.journal_issn), article.pub_year, article.pub_date,
        authors_json, mesh_json, json.dumps(article.keywords),
        json.dumps(article.grants), json.dumps(article.publication_types),
        article.doi, article.abstract,
    )


def save_articles(conn: sqlite3.Connection, articles: List[Article]):
    for article in articles:
        row = _article_to_row(article)
        conn.execute("""
            INSERT OR REPLACE INTO articles
            (pmid, title, journal_title, journal_issn, pub_year, pub_date,
             authors_json, mesh_json, keywords_json, grants_json,
             publication_types_json, doi, abstract)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, row)
    conn.commit()


def _row_to_article(row: sqlite3.Row) -> Article:
    authors_data = json.loads(row["authors_json"])
    authors = [
        Author(
            first_name=a["first_name"], last_name=a["last_name"],
            initials=a.get("initials", ""), affiliation=a.get("affiliation", ""),
            orcid=a.get("orcid", ""), rank=a.get("rank", 0),
        )
        for a in authors_data
    ]
    mesh_data = json.loads(row["mesh_json"])
    mesh_headings = [
        MeshHeading(
            descriptor_name=m["descriptor_name"],
            qualifier_names=m.get("qualifier_names", []),
            major_topic=m.get("major_topic", False),
        )
        for m in mesh_data
    ]
    return Article(
        pmid=row["pmid"],
        title=row["title"],
        journal_title=row["journal_title"],
        journal_issn=json.loads(row["journal_issn"]),
        pub_year=row["pub_year"],
        pub_date=row["pub_date"],
        authors=authors,
        mesh_headings=mesh_headings,
        keywords=json.loads(row["keywords_json"]),
        grants=json.loads(row["grants_json"]),
        publication_types=json.loads(row["publication_types_json"]),
        doi=row["doi"],
        abstract=row["abstract"],
    )


def get_articles_for_person(conn: sqlite3.Connection, person_id: str) -> List[Article]:
    rows = conn.execute("""
        SELECT a.* FROM articles a
        JOIN person_articles pa ON a.pmid = pa.pmid
        WHERE pa.person_id = ?
        ORDER BY a.pub_year DESC, a.pmid DESC
    """, (person_id,)).fetchall()
    articles = [_row_to_article(r) for r in rows]

    # Load curations
    curations = get_curations(conn, person_id)
    for article in articles:
        article.user_assertion = curations.get(article.pmid, "")

    return articles


def get_article(conn: sqlite3.Connection, pmid: int) -> Optional[Article]:
    row = conn.execute("SELECT * FROM articles WHERE pmid = ?", (pmid,)).fetchone()
    if row is None:
        return None
    return _row_to_article(row)


def link_person_articles(conn: sqlite3.Connection, person_id: str, pmids: List[int]):
    for pmid in pmids:
        conn.execute(
            "INSERT OR IGNORE INTO person_articles (person_id, pmid) VALUES (?, ?)",
            (person_id, pmid),
        )
    conn.commit()


# ── Curation CRUD ────────────────────────────────────────────────────────────

def save_curation(conn: sqlite3.Connection, person_id: str, pmid: int, assertion: str):
    conn.execute("""
        INSERT OR REPLACE INTO curations (person_id, pmid, assertion)
        VALUES (?, ?, ?)
    """, (person_id, pmid, assertion))
    # Invalidate cached scores
    conn.execute(
        "DELETE FROM scores WHERE person_id = ?", (person_id,)
    )
    conn.commit()


def save_curations_batch(
    conn: sqlite3.Connection, person_id: str, curations: Dict[int, str]
):
    for pmid, assertion in curations.items():
        conn.execute("""
            INSERT OR REPLACE INTO curations (person_id, pmid, assertion)
            VALUES (?, ?, ?)
        """, (person_id, pmid, assertion))
    conn.execute("DELETE FROM scores WHERE person_id = ?", (person_id,))
    conn.commit()


def get_curations(conn: sqlite3.Connection, person_id: str) -> Dict[int, str]:
    rows = conn.execute(
        "SELECT pmid, assertion FROM curations WHERE person_id = ?", (person_id,)
    ).fetchall()
    return {r["pmid"]: r["assertion"] for r in rows}


# ── Score cache ──────────────────────────────────────────────────────────────

def save_scores(
    conn: sqlite3.Connection,
    person_id: str,
    model_type: str,
    model_dir: str,
    score_data: List[Dict],
):
    for row in score_data:
        features = {k: v for k, v in row.items()
                    if k not in ("pmid", "raw_score", "calibrated_score")}
        conn.execute("""
            INSERT OR REPLACE INTO scores
            (person_id, pmid, model_type, model_dir, raw_score, calibrated_score, features_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            person_id, row["pmid"], model_type, model_dir,
            row.get("raw_score", 0), row.get("calibrated_score", 0),
            json.dumps(features),
        ))
    conn.commit()


def get_cached_scores(
    conn: sqlite3.Connection, person_id: str, model_type: str, model_dir: str
) -> Optional[List[Dict]]:
    rows = conn.execute("""
        SELECT pmid, raw_score, calibrated_score, features_json
        FROM scores
        WHERE person_id = ? AND model_type = ? AND model_dir = ?
    """, (person_id, model_type, model_dir)).fetchall()
    if not rows:
        return None
    return [
        {
            "pmid": r["pmid"],
            "raw_score": r["raw_score"],
            "calibrated_score": r["calibrated_score"],
            **json.loads(r["features_json"]),
        }
        for r in rows
    ]


# ── Statistics ───────────────────────────────────────────────────────────────

def get_person_stats(conn: sqlite3.Connection, person_id: str) -> Dict:
    article_count = conn.execute(
        "SELECT COUNT(*) as cnt FROM person_articles WHERE person_id = ?",
        (person_id,),
    ).fetchone()["cnt"]

    curations = get_curations(conn, person_id)
    accepted = sum(1 for v in curations.values() if v == "ACCEPTED")
    rejected = sum(1 for v in curations.values() if v == "REJECTED")

    return {
        "total_articles": article_count,
        "accepted": accepted,
        "rejected": rejected,
        "pending": article_count - accepted - rejected,
        "acceptance_rate": accepted / max(accepted + rejected, 1),
    }

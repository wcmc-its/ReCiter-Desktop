#!/usr/bin/env python3
"""Generate sample researcher + assertion CSVs from reciterdb.

One-shot. Re-run to refresh the bundled sample data when the upstream
curations drift. Reads via ~/.my.cnf — no credentials in code.

Outputs:
  frontend/public/sample/sample-researchers.csv
  frontend/public/sample/sample-articles.csv

Rules:
  - Researchers: 5 fixed CWIDs (see SAMPLE_COHORT). primary_institution
    hard-coded to "Weill Cornell Medicine". email/orcid/year fields left
    blank so the institutional-profile lookup fills them at run time.
  - Assertions: pulled from person_article where userAssertion is
    ACCEPTED or REJECTED. Drops the 2 oldest and 2 newest ACCEPTED per
    researcher (ordered by publicationDateStandardized asc, pmid asc as
    tiebreaker). Keeps every REJECTED.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

try:
    import pymysql  # type: ignore
except ImportError:  # pragma: no cover
    print("pymysql is required: pip install pymysql", file=sys.stderr)
    sys.exit(1)


REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "frontend" / "public" / "sample"

SAMPLE_COHORT = ["ccole", "dcl2001", "paa2013", "tew2004", "xim2002"]
INSTITUTION = "Weill Cornell Medicine"


def read_my_cnf() -> dict[str, str]:
    """Parse ~/.my.cnf [client] section for host/user/password/database."""
    path = Path.home() / ".my.cnf"
    if not path.exists():
        raise SystemExit(f"~/.my.cnf not found; cannot connect to reciterdb")
    cfg: dict[str, str] = {}
    in_client = False
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            in_client = line.lower() == "[client]"
            continue
        if in_client and "=" in line:
            k, v = (s.strip() for s in line.split("=", 1))
            cfg[k] = v
    return cfg


def connect():
    cfg = read_my_cnf()
    return pymysql.connect(
        host=cfg["host"],
        user=cfg["user"],
        password=cfg.get("password", ""),
        database=cfg.get("database", "reciterdb"),
        cursorclass=pymysql.cursors.DictCursor,
        charset="utf8mb4",
    )


def fetch_researchers(conn) -> list[dict]:
    placeholders = ",".join(["%s"] * len(SAMPLE_COHORT))
    sql = f"""
        SELECT cwid, givenName, surname, primaryAcademicDepartment, primaryTitle
        FROM identity
        WHERE cwid IN ({placeholders})
    """
    with conn.cursor() as cur:
        cur.execute(sql, SAMPLE_COHORT)
        rows = cur.fetchall()
    by_cwid = {r["cwid"]: r for r in rows}
    missing = [c for c in SAMPLE_COHORT if c not in by_cwid]
    if missing:
        raise SystemExit(f"Missing identities in reciterdb: {missing}")
    # Preserve cohort order so the CSV is deterministic across runs.
    return [by_cwid[c] for c in SAMPLE_COHORT]


def fetch_assertions(conn) -> list[tuple[str, str, str]]:
    """Return (person_id, pmid, assertion) tuples, ACCEPTED trimmed."""
    placeholders = ",".join(["%s"] * len(SAMPLE_COHORT))
    sql = f"""
        WITH ranked AS (
            SELECT
                personIdentifier,
                pmid,
                userAssertion,
                publicationDateStandardized,
                ROW_NUMBER() OVER (
                    PARTITION BY personIdentifier
                    ORDER BY publicationDateStandardized ASC, pmid ASC
                ) AS rn_old,
                ROW_NUMBER() OVER (
                    PARTITION BY personIdentifier
                    ORDER BY publicationDateStandardized DESC, pmid DESC
                ) AS rn_new
            FROM person_article
            WHERE personIdentifier IN ({placeholders})
              AND userAssertion = 'ACCEPTED'
        )
        SELECT personIdentifier, pmid, userAssertion
        FROM ranked
        WHERE rn_old > 2 AND rn_new > 2
        UNION ALL
        SELECT personIdentifier, pmid, userAssertion
        FROM person_article
        WHERE personIdentifier IN ({placeholders})
          AND userAssertion = 'REJECTED'
        ORDER BY 1, 3, 2
    """
    with conn.cursor() as cur:
        cur.execute(sql, SAMPLE_COHORT + SAMPLE_COHORT)
        rows = cur.fetchall()
    return [(r["personIdentifier"], str(r["pmid"]), r["userAssertion"]) for r in rows]


def write_researchers(rows: list[dict], path: Path) -> None:
    header = [
        "person_id", "first_name", "last_name", "middle_name",
        "primary_email", "primary_institution", "department", "title",
        "orcid", "bachelor_year", "doctoral_year",
    ]
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        for r in rows:
            w.writerow([
                r["cwid"],
                r.get("givenName") or "",
                r.get("surname") or "",
                "",
                "",
                INSTITUTION,
                r.get("primaryAcademicDepartment") or "",
                r.get("primaryTitle") or "",
                "",
                "",
                "",
            ])


def write_assertions(rows: list[tuple[str, str, str]], path: Path) -> None:
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["person_id", "pmid", "assertion"])
        w.writerows(rows)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    conn = connect()
    try:
        researchers = fetch_researchers(conn)
        assertions = fetch_assertions(conn)
    finally:
        conn.close()

    researchers_path = OUT_DIR / "sample-researchers.csv"
    articles_path = OUT_DIR / "sample-articles.csv"
    write_researchers(researchers, researchers_path)
    write_assertions(assertions, articles_path)

    print(f"Wrote {researchers_path.relative_to(REPO_ROOT)} ({len(researchers)} rows)")
    print(f"Wrote {articles_path.relative_to(REPO_ROOT)} ({len(assertions)} rows)")

    by_person: dict[str, dict[str, int]] = {}
    for pid, _, assertion in assertions:
        by_person.setdefault(pid, {"ACCEPTED": 0, "REJECTED": 0})[assertion] += 1
    print()
    print(f"{'person_id':<10} {'ACCEPTED':>9} {'REJECTED':>9}")
    for pid in SAMPLE_COHORT:
        counts = by_person.get(pid, {"ACCEPTED": 0, "REJECTED": 0})
        print(f"{pid:<10} {counts['ACCEPTED']:>9} {counts['REJECTED']:>9}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

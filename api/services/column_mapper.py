"""Auto-detect CSV column mappings using alias matching."""

CANONICAL_FIELDS = [
    "person_id", "first_name", "last_name", "middle_name",
    "primary_email", "primary_institution", "department", "title",
    "orcid", "bachelor_year", "doctoral_year", "pmid", "assertion",
]

_ALIASES: dict[str, str] = {
    # person_id
    "personid": "person_id", "person_id": "person_id", "uid": "person_id",
    "userid": "person_id", "employeeid": "person_id", "empid": "person_id",
    "emp_id": "person_id", "cwid": "person_id", "netid": "person_id", "id": "person_id",
    # first_name
    "firstname": "first_name", "first_name": "first_name", "fname": "first_name",
    "first": "first_name", "givenname": "first_name",
    # last_name
    "lastname": "last_name", "last_name": "last_name", "lname": "last_name",
    "last": "last_name", "surname": "last_name", "familyname": "last_name",
    # middle_name
    "middlename": "middle_name", "middle_name": "middle_name",
    "middleinitial": "middle_name", "middle_initial": "middle_name",
    "middle": "middle_name", "mi": "middle_name", "middleinit": "middle_name",
    # primary_email
    "email": "primary_email", "primaryemail": "primary_email",
    "primary_email": "primary_email", "emailaddress": "primary_email",
    "email_address": "primary_email",
    # primary_institution
    "institution": "primary_institution", "primaryinstitution": "primary_institution",
    "primary_institution": "primary_institution",
    # department
    "department": "department", "dept": "department", "division": "department",
    "organizationalunit": "department", "organizational_unit": "department",
    "org_unit": "department",
    # title
    "title": "title", "rank": "title", "academictitle": "title",
    "academic_title": "title", "jobtitle": "title", "job_title": "title",
    "position": "title",
    # orcid
    "orcid": "orcid", "orcidid": "orcid", "orcid_id": "orcid",
    "orcidurl": "orcid", "orcid_url": "orcid",
    # bachelor_year
    "bacheloryear": "bachelor_year", "bachelor_year": "bachelor_year",
    "bsyear": "bachelor_year", "bs_year": "bachelor_year",
    # doctoral_year
    "doctoralyear": "doctoral_year", "doctoral_year": "doctoral_year",
    "phdyear": "doctoral_year", "phd_year": "doctoral_year",
    "degreeyear": "doctoral_year", "degree_year": "doctoral_year",
    # gold standard
    "pmid": "pmid", "pubmedid": "pmid", "pubmed_id": "pmid",
    "assertion": "assertion", "assertionstatus": "assertion",
    "assertion_status": "assertion", "userassertion": "assertion",
    "user_assertion": "assertion", "status": "assertion",
}


def _normalize(header: str) -> str:
    return header.lower().strip().replace("-", "").replace(".", "").replace(" ", "")


def detect_mappings(headers: list[str]) -> dict[str, str | None]:
    used_fields: set[str] = set()
    result: dict[str, str | None] = {}
    for header in headers:
        normalized = _normalize(header)
        canonical = _ALIASES.get(normalized)
        if canonical and canonical not in used_fields:
            result[header] = canonical
            used_fields.add(canonical)
        else:
            result[header] = None
    return result

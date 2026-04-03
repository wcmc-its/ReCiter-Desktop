from api.services.institution_discovery import (
    generate_keywords,
    extract_email_domains,
    extract_institution_names,
)

def test_generate_keywords():
    result = generate_keywords("Fred Hutchinson Cancer Center")
    assert "fred" in result
    assert "hutchinson" in result
    assert "cancer" in result
    assert "|" in result

def test_generate_keywords_removes_stopwords():
    result = generate_keywords("University of Washington School of Medicine")
    assert "of" not in result.split("|")
    assert "washington" in result

def test_extract_email_domains_from_affiliations():
    affiliations = [
        "Fred Hutchinson Cancer Center, jsmith@fredhutch.org",
        "University of Washington, jdoe@uw.edu",
        "Fred Hutchinson Cancer Center, bchen@fredhutch.org",
    ]
    domains = extract_email_domains(affiliations)
    assert ("fredhutch.org", 2) in [(d, c) for d, c in domains]

def test_extract_institution_names():
    affiliations = [
        "Department of Medicine, Fred Hutchinson Cancer Center, Seattle, WA, USA",
        "Division of Oncology, Fred Hutchinson Cancer Center, Seattle, WA, USA",
        "Department of Biostatistics, University of Washington, Seattle, WA, USA",
    ]
    institutions = extract_institution_names(affiliations)
    names = [name for name, count in institutions]
    assert any("Fred Hutchinson" in n for n in names)

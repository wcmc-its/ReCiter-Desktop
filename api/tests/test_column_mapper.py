from api.services.column_mapper import detect_mappings, CANONICAL_FIELDS

def test_exact_match():
    headers = ["person_id", "first_name", "last_name"]
    mappings = detect_mappings(headers)
    assert mappings["person_id"] == "person_id"
    assert mappings["first_name"] == "first_name"
    assert mappings["last_name"] == "last_name"

def test_alias_match():
    headers = ["emp_id", "fname", "lname", "phd_year"]
    mappings = detect_mappings(headers)
    assert mappings["emp_id"] == "person_id"
    assert mappings["fname"] == "first_name"
    assert mappings["lname"] == "last_name"
    assert mappings["phd_year"] == "doctoral_year"

def test_unmapped_columns():
    headers = ["person_id", "first_name", "last_name", "favorite_color"]
    mappings = detect_mappings(headers)
    assert mappings.get("favorite_color") is None

def test_gold_standard_detection():
    headers = ["person_id", "first_name", "last_name", "pmid", "assertion"]
    mappings = detect_mappings(headers)
    assert mappings["pmid"] == "pmid"
    assert mappings["assertion"] == "assertion"

def test_title_and_institution_aliases():
    headers = ["uid", "fname", "lname", "rank", "primary_institution"]
    mappings = detect_mappings(headers)
    assert mappings["rank"] == "title"
    assert mappings["primary_institution"] == "primary_institution"

def test_case_insensitive():
    headers = ["Person_ID", "First_Name", "Last_Name"]
    mappings = detect_mappings(headers)
    assert mappings["Person_ID"] == "person_id"

def test_canonical_fields_has_required():
    assert "person_id" in CANONICAL_FIELDS
    assert "first_name" in CANONICAL_FIELDS
    assert "last_name" in CANONICAL_FIELDS

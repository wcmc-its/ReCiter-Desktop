from api.models import Identity, Article, PersonArticle, PersonArticleScore, Curation, Institution


def test_identity_columns():
    cols = {c.name for c in Identity.__table__.columns}
    assert "person_id" in cols
    assert "first_name" in cols
    assert "last_name" in cols
    assert "middle_name" in cols
    assert "primary_email" in cols
    assert "primary_institution" in cols
    assert "department" in cols
    assert "title" in cols
    assert "orcid" in cols
    assert "doctoral_year" in cols
    assert "bachelor_year" in cols


def test_article_columns():
    cols = {c.name for c in Article.__table__.columns}
    assert "pmid" in cols
    assert "title" in cols
    assert "journal" in cols
    assert "pub_year" in cols
    assert "authors" in cols
    assert "mesh_headings" in cols


def test_person_article_composite_pk():
    pk_cols = [c.name for c in PersonArticle.__table__.primary_key.columns]
    assert "person_id" in pk_cols
    assert "pmid" in pk_cols


def test_score_composite_pk():
    pk_cols = [c.name for c in PersonArticleScore.__table__.primary_key.columns]
    assert "person_id" in pk_cols
    assert "pmid" in pk_cols
    assert "model_type" in pk_cols

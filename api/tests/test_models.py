from api.models import Identity, Article, PersonArticle, PersonArticleScore, Curation, Institution, PipelineRun, RetrievalLog


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


def test_pipeline_run_columns():
    cols = {c.name for c in PipelineRun.__table__.columns}
    assert "run_id" in cols
    assert "mode" in cols
    assert "status" in cols
    assert "total_researchers" in cols
    assert "total_articles" in cols
    assert "researchers_succeeded" in cols
    assert "researchers_failed" in cols
    assert "started_at" in cols
    assert "completed_at" in cols
    assert "created_at" in cols


def test_pipeline_run_pk():
    pk_cols = [c.name for c in PipelineRun.__table__.primary_key.columns]
    assert "run_id" in pk_cols


def test_pipeline_run_status_enum():
    status_col = PipelineRun.__table__.columns["status"]
    enums = list(status_col.type.enums)
    assert "PENDING" in enums
    assert "RUNNING" in enums
    assert "COMPLETED" in enums
    assert "PARTIAL" in enums
    assert "FAILED" in enums


def test_pipeline_run_mode_enum():
    mode_col = PipelineRun.__table__.columns["mode"]
    enums = list(mode_col.type.enums)
    assert "full" in enums
    assert "update" in enums
    assert "score_only" in enums


def test_run_id_on_person_article_score():
    cols = {c.name: c for c in PersonArticleScore.__table__.columns}
    assert "run_id" in cols
    col = cols["run_id"]
    assert col.nullable is True
    fk_targets = [fk.target_fullname for fk in col.foreign_keys]
    assert "pipeline_run.run_id" in fk_targets


def test_run_id_on_retrieval_log():
    cols = {c.name: c for c in RetrievalLog.__table__.columns}
    assert "run_id" in cols
    col = cols["run_id"]
    assert col.nullable is True
    fk_targets = [fk.target_fullname for fk in col.foreign_keys]
    assert "pipeline_run.run_id" in fk_targets

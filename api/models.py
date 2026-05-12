from sqlalchemy import (
    Column, String, Text, Integer, Float, Enum, ForeignKey, JSON, TIMESTAMP,
)
from sqlalchemy.sql import func
from api.database import Base


class PipelineRun(Base):
    __tablename__ = "pipeline_run"
    run_id = Column(Integer, autoincrement=True, primary_key=True)
    mode = Column(Enum("full", "update", "score_only"), nullable=False)
    status = Column(
        Enum("PENDING", "RUNNING", "COMPLETED", "PARTIAL", "FAILED"),
        nullable=False,
        server_default="PENDING",
    )
    total_researchers = Column(Integer, nullable=False, server_default="0")
    total_articles = Column(Integer, nullable=False, server_default="0")
    researchers_succeeded = Column(Integer, nullable=False, server_default="0")
    researchers_failed = Column(Integer, nullable=False, server_default="0")
    started_at = Column(TIMESTAMP, nullable=True)
    completed_at = Column(TIMESTAMP, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())


class Institution(Base):
    __tablename__ = "institution"
    config_key = Column(String(255), primary_key=True)
    config_value = Column(Text, nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())


class Identity(Base):
    __tablename__ = "identity"
    person_id = Column(String(128), primary_key=True)
    first_name = Column(String(128), nullable=False)
    last_name = Column(String(128), nullable=False)
    middle_name = Column(String(128), default="")
    primary_email = Column(String(256), default="")
    primary_institution = Column(String(256), default="")
    department = Column(String(256), default="")
    title = Column(String(256), default="")
    orcid = Column(String(64), default="")
    bachelor_year = Column(Integer, default=0)
    doctoral_year = Column(Integer, default=0)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())


class Article(Base):
    __tablename__ = "article"
    pmid = Column(String(20), primary_key=True)
    title = Column(Text)
    journal = Column(String(512))
    pub_year = Column(Integer)
    doi = Column(String(128))
    abstract_text = Column(Text)
    authors = Column(JSON)
    mesh_headings = Column(JSON)
    keywords = Column(JSON)
    grants = Column(JSON)
    publication_types = Column(JSON)
    created_at = Column(TIMESTAMP, server_default=func.now())


class PersonArticle(Base):
    __tablename__ = "person_article"
    person_id = Column(String(128), ForeignKey("identity.person_id", ondelete="CASCADE"), primary_key=True)
    pmid = Column(String(20), ForeignKey("article.pmid", ondelete="CASCADE"), primary_key=True)
    target_author_index = Column(Integer, default=-1)
    source = Column(Enum("upload", "search"), default="search")
    created_at = Column(TIMESTAMP, server_default=func.now())


class RetrievalLog(Base):
    __tablename__ = "retrieval_log"
    person_id = Column(String(128), ForeignKey("identity.person_id", ondelete="CASCADE"), primary_key=True)
    last_retrieval_date = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    articles_found = Column(Integer, default=0)
    run_id = Column(Integer, ForeignKey("pipeline_run.run_id", ondelete="SET NULL"), nullable=True)


class PersonArticleScore(Base):
    __tablename__ = "person_article_score"
    person_id = Column(String(128), ForeignKey("identity.person_id", ondelete="CASCADE"), primary_key=True)
    pmid = Column(String(20), ForeignKey("article.pmid", ondelete="CASCADE"), primary_key=True)
    model_type = Column(Enum("identityOnly", "feedbackIdentity"), primary_key=True, nullable=False)
    raw_score = Column(Float)
    calibrated_score = Column(Float)
    features = Column(JSON)
    scored_at = Column(TIMESTAMP, server_default=func.now())
    run_id = Column(Integer, ForeignKey("pipeline_run.run_id", ondelete="SET NULL"), nullable=True)


class ArticleImportRun(Base):
    __tablename__ = "article_import_run"
    run_id = Column(Integer, autoincrement=True, primary_key=True)
    status = Column(
        Enum("RUNNING", "COMPLETED", "PARTIAL", "FAILED"),
        nullable=False,
        server_default="RUNNING",
    )
    total_pmids = Column(Integer, nullable=False, server_default="0")
    imported_pmids = Column(Integer, nullable=False, server_default="0")
    person_count = Column(Integer, nullable=False, server_default="0")
    file_id = Column(String(64), nullable=True)
    filename = Column(String(512), nullable=True)
    mappings_json = Column(JSON, nullable=True)
    import_gold_standard = Column(Integer, nullable=False, server_default="1")
    error_message = Column(Text, nullable=True)
    started_at = Column(TIMESTAMP, nullable=True)
    completed_at = Column(TIMESTAMP, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())


class Curation(Base):
    __tablename__ = "curation"
    person_id = Column(String(128), ForeignKey("identity.person_id", ondelete="CASCADE"), primary_key=True)
    pmid = Column(String(20), ForeignKey("article.pmid", ondelete="CASCADE"), primary_key=True)
    assertion = Column(Enum("ACCEPTED", "REJECTED"), nullable=False)
    source = Column(Enum("import"), default="import")
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

from sqlalchemy import (
    Column, String, Text, Integer, Float, Enum, ForeignKey, JSON, TIMESTAMP,
)
from sqlalchemy.sql import func
from api.database import Base


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


class PersonArticleScore(Base):
    __tablename__ = "person_article_score"
    person_id = Column(String(128), ForeignKey("identity.person_id", ondelete="CASCADE"), primary_key=True)
    pmid = Column(String(20), ForeignKey("article.pmid", ondelete="CASCADE"), primary_key=True)
    model_type = Column(Enum("identityOnly", "feedbackIdentity"), primary_key=True, nullable=False)
    raw_score = Column(Float)
    calibrated_score = Column(Float)
    features = Column(JSON)
    scored_at = Column(TIMESTAMP, server_default=func.now())


class Curation(Base):
    __tablename__ = "curation"
    person_id = Column(String(128), ForeignKey("identity.person_id", ondelete="CASCADE"), primary_key=True)
    pmid = Column(String(20), ForeignKey("article.pmid", ondelete="CASCADE"), primary_key=True)
    assertion = Column(Enum("ACCEPTED", "REJECTED"), nullable=False)
    source = Column(Enum("import", "manual"), default="import")
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

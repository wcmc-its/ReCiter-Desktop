CREATE TABLE IF NOT EXISTS institution (
    config_key VARCHAR(255) PRIMARY KEY,
    config_value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS identity (
    person_id VARCHAR(128) PRIMARY KEY,
    first_name VARCHAR(128) NOT NULL,
    last_name VARCHAR(128) NOT NULL,
    middle_name VARCHAR(128) DEFAULT '',
    primary_email VARCHAR(256) DEFAULT '',
    primary_institution VARCHAR(256) DEFAULT '',
    department VARCHAR(256) DEFAULT '',
    title VARCHAR(256) DEFAULT '',
    orcid VARCHAR(64) DEFAULT '',
    bachelor_year INT DEFAULT 0,
    doctoral_year INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS article (
    pmid VARCHAR(20) PRIMARY KEY,
    title TEXT,
    journal VARCHAR(512),
    pub_year INT,
    doi VARCHAR(128),
    abstract_text TEXT,
    authors JSON,
    mesh_headings JSON,
    keywords JSON,
    grants JSON,
    publication_types JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS person_article (
    person_id VARCHAR(128),
    pmid VARCHAR(20),
    target_author_index INT DEFAULT -1,
    source ENUM('upload', 'search') DEFAULT 'search',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (person_id, pmid),
    FOREIGN KEY (person_id) REFERENCES identity(person_id) ON DELETE CASCADE,
    FOREIGN KEY (pmid) REFERENCES article(pmid) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS person_article_score (
    person_id VARCHAR(128),
    pmid VARCHAR(20),
    model_type ENUM('identityOnly', 'feedbackIdentity') NOT NULL,
    raw_score FLOAT,
    calibrated_score FLOAT,
    features JSON,
    scored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (person_id, pmid, model_type),
    FOREIGN KEY (person_id) REFERENCES identity(person_id) ON DELETE CASCADE,
    FOREIGN KEY (pmid) REFERENCES article(pmid) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS retrieval_log (
    person_id VARCHAR(128) PRIMARY KEY,
    last_retrieval_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    articles_found INT DEFAULT 0,
    FOREIGN KEY (person_id) REFERENCES identity(person_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS curation (
    person_id VARCHAR(128),
    pmid VARCHAR(20),
    assertion ENUM('ACCEPTED', 'REJECTED') NOT NULL,
    source ENUM('import', 'manual') DEFAULT 'import',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (person_id, pmid),
    FOREIGN KEY (person_id) REFERENCES identity(person_id) ON DELETE CASCADE,
    FOREIGN KEY (pmid) REFERENCES article(pmid) ON DELETE CASCADE
);

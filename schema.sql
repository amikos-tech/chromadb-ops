--- Embedding Queue ---

--- chromadb/migrations/embeddings_queue/00001-embeddings.sqlite.SQL
CREATE TABLE embeddings_queue (
    seq_id INTEGER PRIMARY KEY,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    operation INTEGER NOT NULL,
    topic TEXT NOT NULL,
    id TEXT NOT NULL,
    vector BLOB,
    encoding TEXT,
    metadata TEXT
);


--- chromadb/migrations/embeddings_queue/00002-embeddings-queue-config.sqlite.SQL

CREATE TABLE embeddings_queue_config (
    id INTEGER PRIMARY KEY,
    config_json_str TEXT
);

--- Metadata DB ---

--- chromadb/migrations/metadb/00001-embedding-metadata.sqlite.sql
CREATE TABLE embeddings (
    id INTEGER PRIMARY KEY,
    segment_id TEXT NOT NULL,
    embedding_id TEXT NOT NULL,
    seq_id BLOB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (segment_id, embedding_id)
);

CREATE TABLE embedding_metadata (
    id INTEGER REFERENCES embeddings(id),
    key TEXT NOT NULL,
    string_value TEXT,
    int_value INTEGER,
    float_value REAL,
    PRIMARY KEY (id, key)
);

CREATE TABLE max_seq_id (
    segment_id TEXT PRIMARY KEY,
    seq_id BLOB NOT NULL
);

CREATE VIRTUAL TABLE embedding_fulltext USING fts5(id, string_value);

--- chromadb/migrations/metadb/00002-embedding-metadata.sqlite.sql
-- SQLite does not support adding check with alter table, as a result, adding a check
-- involve creating a new table and copying the data over. It is over kill with adding
-- a boolean type column. The application write to the table needs to ensure the data
-- integrity.
ALTER TABLE embedding_metadata ADD COLUMN bool_value INTEGER;


--- chromadb/migrations/metadb/00003-full-text-tokenize.sqlite.sql
CREATE VIRTUAL TABLE embedding_fulltext_search USING fts5(string_value, tokenize='trigram');
INSERT INTO embedding_fulltext_search (rowid, string_value) SELECT rowid, string_value FROM embedding_metadata;
DROP TABLE embedding_fulltext;


--- chromadb/migrations/metadb/00004-metadata-indices.sqlite.sql

CREATE INDEX IF NOT EXISTS embedding_metadata_int_value ON embedding_metadata (key, int_value) WHERE int_value IS NOT NULL;
CREATE INDEX IF NOT EXISTS embedding_metadata_float_value ON embedding_metadata (key, float_value) WHERE float_value IS NOT NULL;
CREATE INDEX IF NOT EXISTS embedding_metadata_string_value ON embedding_metadata (key, string_value) WHERE string_value IS NOT NULL;


--- SYSDB ---

--- chromadb/migrations/sysdb/00001-collections.sqlite.SQL
CREATE TABLE collections (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    topic TEXT NOT NULL,
    UNIQUE (name)
);

CREATE TABLE collection_metadata (
    collection_id TEXT REFERENCES collections(id) ON DELETE CASCADE,
    key TEXT NOT NULL,
    str_value TEXT,
    int_value INTEGER,
    float_value REAL,
    PRIMARY KEY (collection_id, key)
);

--- chromadb/migrations/sysdb/00002-segments.sqlite.sql

CREATE TABLE segments (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    scope TEXT NOT NULL,
    topic TEXT,
    collection TEXT REFERENCES collection(id)
);

CREATE TABLE segment_metadata (
    segment_id TEXT  REFERENCES segments(id) ON DELETE CASCADE,
    key TEXT NOT NULL,
    str_value TEXT,
    int_value INTEGER,
    float_value REAL,
    PRIMARY KEY (segment_id, key)
);


--- chromadb/migrations/sysdb/00003-collection-dimension.sqlite.sql
ALTER TABLE collections ADD COLUMN dimension INTEGER;

--- chromadb/migrations/sysdb/00004-tenants-databases.sqlite.sql

CREATE TABLE IF NOT EXISTS tenants (
    id TEXT PRIMARY KEY,
    UNIQUE (id)
);

CREATE TABLE IF NOT EXISTS databases (
    id TEXT PRIMARY KEY, -- unique globally
    name TEXT NOT NULL, -- unique per tenant
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    UNIQUE (tenant_id, name) -- Ensure that a tenant has only one database with a given name
);

CREATE TABLE IF NOT EXISTS collections_tmp (
    id TEXT PRIMARY KEY, -- unique globally
    name TEXT NOT NULL, -- unique per database
    topic TEXT NOT NULL,
    dimension INTEGER,
    database_id TEXT NOT NULL REFERENCES databases(id) ON DELETE CASCADE,
    UNIQUE (name, database_id)
);

-- Create default tenant and database
INSERT OR REPLACE INTO tenants (id) VALUES ('default_tenant'); -- The default tenant id is 'default_tenant' others are UUIDs
INSERT OR REPLACE INTO databases (id, name, tenant_id) VALUES ('00000000-0000-0000-0000-000000000000', 'default_database', 'default_tenant');

INSERT OR REPLACE INTO collections_tmp (id, name, topic, dimension, database_id)
    SELECT id, name, topic, dimension, '00000000-0000-0000-0000-000000000000' FROM collections;
DROP TABLE collections;
ALTER TABLE collections_tmp RENAME TO collections;


--- chromadb/migrations/sysdb/00005-remove-topic.sqlite.sql

-- Remove the topic column from the Collections and Segments tables

ALTER TABLE collections DROP COLUMN topic;
ALTER TABLE segments DROP COLUMN topic;


--- chromadb/migrations/sysdb/00006-collection-segment-metadata.sqlite.SQL
-- SQLite does not support adding check with alter table, as a result, adding a check
-- involve creating a new table and copying the data over. It is over kill with adding
-- a boolean type column. The application write to the table needs to ensure the data
-- integrity.
ALTER TABLE collection_metadata ADD COLUMN bool_value INTEGER;
ALTER TABLE segment_metadata ADD COLUMN bool_value INTEGER;


--- chromadb/migrations/sysdb/00007-collection-config.sqlite.sql

-- Stores collection configuration dictionaries.
ALTER TABLE collections ADD COLUMN config_json_str TEXT;


--- chromadb/migrations/sysdb/00008-maintenance-log.sqlite.SQL

-- Records when database maintenance operations are performed.
-- At time of creation, this table is only used to record vacuum operations.
CREATE TABLE maintenance_log (
  id INT PRIMARY KEY,
  timestamp INT NOT NULL,
  operation TEXT NOT NULL
);

--- chromadb/migrations/sysdb/00009-segment-collection-not-null.sqlite.sql

-- This makes segments.collection non-nullable.
CREATE TABLE segments_temp (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    scope TEXT NOT NULL,
    collection TEXT REFERENCES collection(id) NOT NULL
);

INSERT INTO segments_temp SELECT * FROM segments;
DROP TABLE segments;
ALTER TABLE segments_temp RENAME TO segments;

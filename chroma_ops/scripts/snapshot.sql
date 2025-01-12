create table embeddings_queue
(
    seq_id     INTEGER primary key,
    created_at TIMESTAMP default CURRENT_TIMESTAMP not null,
    operation  INTEGER                             not null,
    topic      TEXT                                not null,
    id         TEXT                                not null,
    vector     BLOB,
    encoding   TEXT,
    metadata   TEXT
);

create table max_seq_id
(
    segment_id TEXT
        primary key,
    seq_id     BLOB not null
);

create table embeddings
(
    id           INTEGER
        primary key,
    segment_id   TEXT                                not null,
    embedding_id TEXT                                not null,
    seq_id       BLOB                                not null,
    created_at   TIMESTAMP default CURRENT_TIMESTAMP not null,
    unique (segment_id, embedding_id)
);

create table embedding_metadata
(
    id           INTEGER
        references embeddings,
    key          TEXT not null,
    string_value TEXT,
    int_value    INTEGER,
    float_value  REAL,
    bool_value   INTEGER,
    primary key (id, key)
);

-- we don't necessarily need indices
create index embedding_metadata_float_value
    on embedding_metadata (key, float_value)
    where float_value IS NOT NULL;

create index embedding_metadata_int_value
    on embedding_metadata (key, int_value)
    where int_value IS NOT NULL;

create index embedding_metadata_string_value
    on embedding_metadata (key, string_value)
    where string_value IS NOT NULL;


create table segments
(
    id         TEXT
        primary key,
    type       TEXT not null,
    scope      TEXT not null,
    collection TEXT not null
        references collections (id)
);

create table segment_metadata
(
    segment_id  TEXT
        references segments
            on delete cascade,
    key         TEXT not null,
    str_value   TEXT,
    int_value   INTEGER,
    float_value REAL,
    bool_value  INTEGER,
    primary key (segment_id, key)
);

create table collections
(
    id              TEXT
        primary key,
    name            TEXT not null,
    dimension       INTEGER,
    database_id     TEXT not null,
    database_name   TEXT not null,
    tenant_id       TEXT not null,
    config_json_str TEXT,
    unique (name, database_id)
);

create table collection_metadata
(
    collection_id TEXT
        references collections
            on delete cascade,
    key           TEXT not null,
    str_value     TEXT,
    int_value     INTEGER,
    float_value   REAL,
    bool_value    INTEGER,
    primary key (collection_id, key)
);


create table hnsw_segment_data
(
    id INTEGER primary key,
    segment_id TEXT not null,
    filename TEXT,
    data BLOB,
    sha256 TEXT,
    created_at TIMESTAMP default CURRENT_TIMESTAMP not null,
    unique (segment_id, filename)
);

-- name: GetSegments :many
SELECT * FROM segments WHERE scope = 'VECTOR';


-- name: AddDummyVectorSegment :exec
INSERT INTO segments (id, type, scope,collection) VALUES (?,'urn:chroma:segment/vector/hnsw-local-persisted','VECTOR',?)
RETURNING *;

-- name: DropFTS :exec
DROP TABLE IF EXISTS embedding_fulltext_search;


-- name: CreateFTS :exec
CREATE VIRTUAL TABLE IF NOT EXISTS embedding_fulltext_search USING fts5(string_value, tokenize='trigram');
INSERT INTO embedding_fulltext_search (rowid, string_value) SELECT em.rowid, COALESCE(doc.string_value, '')
FROM embeddings em
LEFT JOIN embedding_metadata doc 
  ON em.id = doc.id 
  AND doc.key = 'chroma:document'
GROUP BY doc.id;

-- name: DropFTSConfig :exec
DROP TABLE IF EXISTS embedding_fulltext_search_config;

-- name: DropFTSContent :exec
DROP TABLE IF EXISTS embedding_fulltext_search_content;

-- name: DropFTSData :exec
DROP TABLE IF EXISTS embedding_fulltext_search_data;

-- name: DropFTSDocsize :exec
DROP TABLE IF EXISTS embedding_fulltext_search_docsize;


-- name: DropFTSIdx :exec
DROP TABLE IF EXISTS embedding_fulltext_search_idx;

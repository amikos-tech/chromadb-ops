-- name: GetSegments :many
SELECT * FROM segments WHERE scope = 'VECTOR';


-- name: AddDummyVectorSegment :exec
INSERT INTO segments (id, type, scope,collection) VALUES (?,'urn:chroma:segment/vector/hnsw-local-persisted','VECTOR',?)
RETURNING *;

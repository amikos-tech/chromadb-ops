BEGIN EXCLUSIVE TRANSACTION;
DROP TABLE IF EXISTS embedding_fulltext_search;
DROP TABLE IF EXISTS embedding_fulltext_search_config;
DROP TABLE IF EXISTS embedding_fulltext_search_content;
DROP TABLE IF EXISTS embedding_fulltext_search_data;
DROP TABLE IF EXISTS embedding_fulltext_search_docsize;
DROP TABLE IF EXISTS embedding_fulltext_search_idx;
CREATE VIRTUAL TABLE embedding_fulltext_search USING fts5(string_value, tokenize='__TOKENIZER__');
INSERT INTO embedding_fulltext_search (rowid, string_value) SELECT em.rowid, COALESCE(doc.string_value, '')
FROM embeddings em
LEFT JOIN embedding_metadata doc
  ON em.id = doc.id
  AND doc.key = 'chroma:document'
GROUP BY doc.id;
COMMIT;

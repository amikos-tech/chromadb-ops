import os.path
import shutil
import sqlite3
import tempfile
import uuid

import chromadb
import pytest

from chroma_ops.rebuild_fts import rebuild_fts


def test_rebuild_fts() -> None:
    records_to_add = 1
    with tempfile.TemporaryDirectory() as temp_dir:
        client = chromadb.PersistentClient(path=temp_dir)
        col = client.create_collection("test")
        ids_documents = [
            (f"{uuid.uuid4()}", f"document {i}", [0.1] * 1536)
            for i in range(records_to_add)
        ]
        ids, documents, embeddings = zip(*ids_documents)
        col.add(ids=list(ids), documents=list(documents), embeddings=list(embeddings))
        sql_file = os.path.join(temp_dir, "chroma.sqlite3")
        conn = sqlite3.connect(sql_file)
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS  embedding_fulltext_search;")
        conn.commit()
        cursor.close()
        with pytest.raises(Exception) as e:
            col.get(where_document={"$contains": "document 0"})

        assert "no such table: embedding_fulltext_search" in str(e)
        rebuild_fts(temp_dir)
        fixed_temp_dir = os.path.join(temp_dir, "fixed")
        shutil.copytree(temp_dir, fixed_temp_dir)
        client = chromadb.PersistentClient(path=fixed_temp_dir)
        col = client.get_collection("test")
        col.get(where_document={"$contains": "document 0"})

import os.path
import shutil
import sqlite3
import tempfile
import uuid

import chromadb
import pytest

from chroma_ops.rebuild_fts import rebuild_fts


def test_rebuild_fts() -> None:
    records_to_add = 100
    with tempfile.TemporaryDirectory() as temp_dir:
        client = chromadb.PersistentClient(path=temp_dir)
        col = client.create_collection("test")
        ids_documents = [
            (f"{uuid.uuid4()}", f"document {i}" if i % 2 == 0 else None, [0.1] * 384)
            for i in range(records_to_add)
        ]
        ids, documents, embeddings = zip(*ids_documents)
        col.add(ids=list(ids), documents=list(documents), embeddings=list(embeddings))
        res_before = col.get(where_document={"$contains": "document 1"})
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
        res_after = col.get(where_document={"$contains": "document 1"})
        assert res_after == res_before


def test_rebuild_fts_with_unicode61() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        client = chromadb.PersistentClient(path=temp_dir)
        col = client.create_collection("test")
        documents = [
            "The quick brown fox jumps over the lazy dog",
            "We've got all your llama's in a row",
            "Cats are lazy pets",
            "Dogs are loyal friends",
            "Birds are beautiful creatures",
            "Fish are fascinating underwater",
            "Bears are powerful animals",
            "Elephants are intelligent giants",
            "주요 신흥 4개국 증시 외국인투자자 순매수액",
            "Tigers are majestic predators",
        ]
        embeddings = [[0.1] * 384] * len(documents)
        ids = [f"{uuid.uuid4()}" for _ in range(len(documents))]
        col.add(ids=ids, documents=documents, embeddings=embeddings)
        res_before = col.get(where_document={"$contains": "국인투자"})

        sql_file = os.path.join(temp_dir, "chroma.sqlite3")
        conn = sqlite3.connect(sql_file)
        cursor = conn.cursor()
        res = cursor.execute(
            "select sql from sqlite_master where name = 'embedding_fulltext_search'"
        )
        assert "trigram" in res.fetchone()[0]
        shutil.copy2(sql_file, os.path.join(".", "chroma_before.sqlite3"))
        assert len(res_before["ids"]) == 1

        fixed_temp_dir = os.path.join(temp_dir, "fixed")
        shutil.copytree(temp_dir, fixed_temp_dir)
        rebuild_fts(fixed_temp_dir, tokenizer="unicode61")
        client = chromadb.PersistentClient(path=fixed_temp_dir)
        col = client.get_collection("test")
        res_after = col.get(where_document={"$contains": "순매"})
        assert len(res_after["ids"]) == 1
        sql_file = os.path.join(fixed_temp_dir, "chroma.sqlite3")
        conn = sqlite3.connect(sql_file)
        cursor = conn.cursor()
        res = cursor.execute(
            "select sql from sqlite_master where name = 'embedding_fulltext_search'"
        )
        assert "unicode61" in res.fetchone()[0]

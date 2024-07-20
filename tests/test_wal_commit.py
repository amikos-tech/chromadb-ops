import os.path
import sqlite3
import tempfile
import uuid

from hypothesis import given, settings
import hypothesis.strategies as st

import chromadb
from chromadb.segment import VectorReader
from chromadb.types import SegmentScope

from chroma_ops.wal_commit import commit_wal


@given(records_to_add=st.integers(min_value=1, max_value=1001))
@settings(deadline=60000)
def test_basic_commit(records_to_add: int) -> None:
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
        conn = sqlite3.connect(f"file:{sql_file}?mode=ro", uri=True)

        vector_segments = [
            client._server._manager.get_segment(s["collection"], VectorReader)
            for s in client._server._sysdb.get_segments()
            if s["scope"] == SegmentScope.VECTOR
        ]
        for segment in vector_segments:
            batch_size = segment._batch_size
            if records_to_add % batch_size == 0:
                assert (
                    len(segment._index.get_ids_list()) == records_to_add
                ), "Precheck failed"
            else:
                assert (
                    len(segment._index.get_ids_list()) != records_to_add
                ), "Precheck failed"
        cursor = conn.cursor()

        count = cursor.execute("SELECT count(*) FROM embeddings_queue")
        assert count.fetchone()[0] == records_to_add
        commit_wal(temp_dir)
        count = cursor.execute("SELECT count(*) FROM embeddings_queue")
        assert count.fetchone()[0] == records_to_add
        for segment in vector_segments:
            assert (
                len(segment._index.get_ids_list()) == records_to_add
            ), "postcheck failed"


@given(records_to_add=st.integers(min_value=1, max_value=1001))
@settings(deadline=60000)
def test_commit_skip_collection(records_to_add: int) -> None:
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
        conn = sqlite3.connect(f"file:{sql_file}?mode=ro", uri=True)

        vector_segments = [
            client._server._manager.get_segment(s["collection"], VectorReader)
            for s in client._server._sysdb.get_segments()
            if s["scope"] == SegmentScope.VECTOR
        ]
        for segment in vector_segments:
            batch_size = segment._batch_size
            if records_to_add % batch_size == 0:
                assert (
                    len(segment._index.get_ids_list()) == records_to_add
                ), "Precheck failed"
            else:
                assert (
                    len(segment._index.get_ids_list()) != records_to_add
                ), "Precheck failed"
        cursor = conn.cursor()

        count = cursor.execute("SELECT count(*) FROM embeddings_queue")
        assert count.fetchone()[0] == records_to_add
        commit_wal(temp_dir, skip_collection_names=["test"])
        count = cursor.execute("SELECT count(*) FROM embeddings_queue")
        assert count.fetchone()[0] == records_to_add
        for segment in vector_segments:
            if records_to_add % batch_size == 0:
                assert (
                    len(segment._index.get_ids_list()) == records_to_add
                ), "Post failed"
            else:
                assert (
                    len(segment._index.get_ids_list()) != records_to_add
                ), "Post failed"


def test_empty_collections(capsys) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        client = chromadb.PersistentClient(path=temp_dir)
        client.create_collection("test")
        commit_wal(temp_dir, skip_collection_names=["test"])
        captured = capsys.readouterr()
        assert "Ignoring skipped collection test" in captured.err

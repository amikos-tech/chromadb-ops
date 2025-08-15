import os.path
import sqlite3
import tempfile
import uuid

from hypothesis import given, settings
import hypothesis.strategies as st

import chromadb

from chroma_ops.utils import get_dir_size
from chroma_ops.wal_clean import clean_wal


# the min sample must be 1000
@given(records_to_add=st.sampled_from([1000, 2000, 3000, 10000]))
@settings(deadline=None)
def test_basic_clean(records_to_add: int) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        client = chromadb.PersistentClient(path=temp_dir)
        _records_to_add = min(records_to_add, client.get_max_batch_size())
        col = client.create_collection("test")
        ids_documents = [
            (f"{uuid.uuid4()}", f"document {i}", [0.1] * 1536)
            for i in range(_records_to_add)
        ]
        ids, documents, embeddings = zip(*ids_documents)
        col.add(ids=list(ids), documents=list(documents), embeddings=list(embeddings))
        size_before = get_dir_size(temp_dir)
        sql_file = os.path.join(temp_dir, "chroma.sqlite3")
        conn = sqlite3.connect(f"file:{sql_file}?mode=ro", uri=True)
        cursor = conn.cursor()
        count = cursor.execute("SELECT count(*) FROM embeddings_queue")
        if tuple(int(part) for part in chromadb.__version__.split(".")) > (0, 5, 5):
            assert count.fetchone()[0] == 1
        else:
            assert count.fetchone()[0] == _records_to_add
        clean_wal(temp_dir, yes=True)
        count = cursor.execute("SELECT count(*) FROM embeddings_queue")
        assert count.fetchone()[0] < _records_to_add
        size_after = get_dir_size(temp_dir)
        assert size_after <= size_before


def test_clean_skip_collections() -> None:
    records_to_add = 10
    with tempfile.TemporaryDirectory() as temp_dir:
        client = chromadb.PersistentClient(path=temp_dir)
        col = client.create_collection("test")
        ids_documents = [
            (f"{uuid.uuid4()}", f"document {i}", [0.1] * 1536)
            for i in range(records_to_add)
        ]
        ids, documents, embeddings = zip(*ids_documents)
        col.add(ids=list(ids), documents=list(documents), embeddings=list(embeddings))
        size_before = get_dir_size(temp_dir)
        sql_file = os.path.join(temp_dir, "chroma.sqlite3")
        conn = sqlite3.connect(f"file:{sql_file}?mode=ro", uri=True)
        cursor = conn.cursor()
        count = cursor.execute("SELECT count(*) FROM embeddings_queue")
        assert count.fetchone()[0] == records_to_add
        clean_wal(temp_dir, skip_collection_names=[col.name], yes=True)
        count = cursor.execute("SELECT count(*) FROM embeddings_queue")
        assert (
            count.fetchone()[0] == records_to_add
        )  # no changes as we skip the only collection
        size_after = get_dir_size(temp_dir)
        assert size_after == size_before  # no changes as we skip the only collection

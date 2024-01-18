import os.path
import sqlite3
import tempfile
import uuid

from hypothesis import given, settings
import hypothesis.strategies as st

import chromadb
from chromadb.segment import VectorReader
from chromadb.types import SegmentScope

from chroma_ops.utils import get_dir_size
from chroma_ops.wal_clean import clean_wal


@given(records_to_add=st.integers(min_value=1000, max_value=10001))
@settings(deadline=60000)
def test_basic_clean(records_to_add: int):
    with tempfile.TemporaryDirectory() as temp_dir:
        client = chromadb.PersistentClient(path=temp_dir)
        col = client.create_collection("test")
        ids_documents = [(f"{uuid.uuid4()}", f"document {i}", [0.1] * 1536) for i in range(records_to_add)]
        ids, documents, embeddings = zip(*ids_documents)
        col.add(ids=list(ids), documents=list(documents), embeddings=list(embeddings))
        size_before = get_dir_size(temp_dir)
        sql_file = os.path.join(temp_dir, "chroma.sqlite3")
        conn = sqlite3.connect(f"file:{sql_file}?mode=ro", uri=True)
        cursor = conn.cursor()
        count = cursor.execute("SELECT count(*) FROM embeddings_queue")
        assert count.fetchone()[0] == records_to_add
        clean_wal(temp_dir)
        count = cursor.execute("SELECT count(*) FROM embeddings_queue")
        assert count.fetchone()[0] < records_to_add
        size_after = get_dir_size(temp_dir)
        assert size_after < size_before

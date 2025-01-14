import os.path
import tempfile
import uuid

from chromadb.segment import VectorReader
from chromadb.types import SegmentScope
from hypothesis import given, settings
import hypothesis.strategies as st

import chromadb

from chroma_ops.wal_export import export_wal


def count_lines(file_path: str) -> int:
    with open(file_path, "r") as file:
        lines = file.readlines()
    return len(lines)


@given(records_to_add=st.sampled_from([1, 100, 500, 10000]))
@settings(deadline=None)
def test_basic_export(records_to_add: int) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        client = chromadb.PersistentClient(path=temp_dir)
        col = client.create_collection("test")
        ids_documents = [
            (f"{uuid.uuid4()}", f"document {i}", [0.1] * 1536)
            for i in range(records_to_add)
        ]
        ids, documents, embeddings = zip(*ids_documents)
        col.add(ids=list(ids), documents=list(documents), embeddings=list(embeddings))
        with tempfile.NamedTemporaryFile() as temp_file:
            vector_segments = [
                client._server._manager.get_segment(s["collection"], VectorReader)
                for s in client._server._sysdb.get_segments(collection=col.id)
                if s["scope"] == SegmentScope.VECTOR
            ]
            _sync_threshold = vector_segments[0]._sync_threshold
            export_wal(temp_dir, temp_file.name, yes=True)
            assert os.path.exists(temp_file.name)
            if tuple(int(part) for part in chromadb.__version__.split(".")) > (0, 5, 5):
                if records_to_add % _sync_threshold == 0:
                    assert count_lines(temp_file.name) == 1
                else:
                    assert count_lines(temp_file.name) <= records_to_add
            else:
                assert count_lines(temp_file.name) == records_to_add

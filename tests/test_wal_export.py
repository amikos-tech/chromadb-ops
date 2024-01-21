import os.path
import tempfile
import uuid

from hypothesis import given, settings
import hypothesis.strategies as st

import chromadb

from chroma_ops.wal_export import export_wal


def count_lines(file_path: str) -> int:
    with open(file_path, "r") as file:
        lines = file.readlines()
    return len(lines)


@given(records_to_add=st.integers(min_value=1, max_value=100))
@settings(deadline=60000)
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
            export_wal(temp_dir, temp_file.name)
            assert os.path.exists(temp_file.name)
            assert count_lines(temp_file.name) == records_to_add

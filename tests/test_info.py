import tempfile
import uuid

from hypothesis import given, settings
import hypothesis.strategies as st

import chromadb

from chroma_ops.info import info


@given(records_to_add=st.integers(min_value=1000, max_value=100000))
@settings(deadline=60000, max_examples=10)
def test_basic_info(records_to_add: int) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        client = chromadb.PersistentClient(path=temp_dir)
        col = client.create_collection("test")
        ids_documents = [
            (f"{uuid.uuid4()}", f"document {i}", [0.1] * 1536)
            for i in range(records_to_add)
        ]
        ids, documents, embeddings = zip(*ids_documents)
        col.add(ids=list(ids), documents=list(documents), embeddings=list(embeddings))
        export_data = info(temp_dir)
        assert len(export_data["collections"]) == 1


def test_empty_collections(capsys) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        client = chromadb.PersistentClient(path=temp_dir)
        client.get_or_create_collection("test")
        export_data = info(temp_dir)
        assert len(export_data["collections"]) == 1


def test_empty_db(capsys) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        chromadb.PersistentClient(path=temp_dir)
        export_data = info(temp_dir)
        assert len(export_data["collections"]) == 0


def test_skip_collection(capsys) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        client = chromadb.PersistentClient(path=temp_dir)
        client.get_or_create_collection("test")
        export_data = info(temp_dir, skip_collection_names=["test"])
        assert len(export_data["collections"]) == 0


def test_privacy(capsys) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        client = chromadb.PersistentClient(path=temp_dir)
        client.get_or_create_collection("test")
        export_data = info(temp_dir, privacy_mode=True)
        captured = capsys.readouterr()
        assert len(export_data["collections"]) == 1
        assert "test" not in captured.out
        print(captured.out)

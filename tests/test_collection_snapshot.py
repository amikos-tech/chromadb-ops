import os
from pathlib import Path
import tempfile
from typing import Any, Dict

import chromadb

from chroma_ops.collection_snapshot import collection_snapshot
from chroma_ops.utils import get_sqlite_snapshot_connection

from hypothesis import given, settings
import hypothesis.strategies as st
import numpy as np
import uuid


@st.composite
def dict_strategy(draw: st.DrawFn) -> Dict[str, Any]:
    keys = draw(st.lists(st.text(min_size=1, max_size=10), max_size=5, unique=True))
    values = draw(
        st.lists(
            st.one_of(
                st.integers(min_value=0, max_value=1000000),
                st.text(max_size=10),
                st.floats(min_value=0, max_value=1000000),
                st.booleans(),
            ),
            min_size=len(keys),
            max_size=len(keys),
        )
    )
    return dict(zip(keys, values))


@given(
    records_to_add=st.integers(min_value=100, max_value=5000),
    metadata=dict_strategy(),
)
@settings(deadline=None, max_examples=10)
def test_collection_snapshot(records_to_add: int, metadata: Dict[str, Any]) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        chroma_dir = os.path.join(temp_dir, "chroma")
        os.makedirs(chroma_dir, exist_ok=True)
        client = chromadb.PersistentClient(path=chroma_dir)
        col = client.get_or_create_collection(
            "test_collection", metadata=metadata if len(metadata) > 0 else None
        )
        ids = [str(uuid.uuid4()) for _ in range(records_to_add)]
        documents = [f"document {i}" for i in range(records_to_add)]
        embeddings = np.random.uniform(0, 1, (records_to_add, 384)).tolist()
        metadata_to_add = [
            {"metadata_key": f"metadata_value_{i}"} for i in range(records_to_add)
        ]  # we can do better here with a strategy but for now it is good enough
        col.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadata_to_add,
        )
        collection_snapshot(
            chroma_dir,
            "test_collection",
            Path(temp_dir, "snapshot", "snapshot.sqlite3"),
            yes=True,
        )
        assert os.path.exists(Path(temp_dir, "snapshot", "snapshot.sqlite3"))
        with get_sqlite_snapshot_connection(
            Path(temp_dir, "snapshot", "snapshot.sqlite3").absolute().as_posix()
        ) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT count(*) FROM collections")
            assert cursor.fetchone()[0] == 1
            cursor.execute("SELECT count(*) FROM collection_metadata")
            assert cursor.fetchone()[0] == len(metadata)
            cursor.execute("SELECT count(*) FROM hnsw_segment_data")
            assert (
                cursor.fetchone()[0] == 4 if records_to_add < 1000 else 5
            )  # 5 if pickle metadata is included e.g. if added records > threshold
            cursor.execute("SELECT count(*) FROM segments")
            assert cursor.fetchone()[0] == 2
            cursor.execute("SELECT count(*) FROM segment_metadata")
            assert cursor.fetchone()[0] == 0
            cursor.execute("SELECT count(*) FROM max_seq_id")
            assert (
                cursor.fetchone()[0] == 1 if records_to_add < 1000 else 2
            )  # 2 if pickle metadata is included e.g. if added records > threshold
            cursor.execute("SELECT count(*) FROM embeddings_queue")
            assert cursor.fetchone()[0] > 0
            cursor.execute("SELECT count(*) FROM embeddings")
            assert cursor.fetchone()[0] == records_to_add
            cursor.execute("SELECT count(*) FROM embedding_metadata")
            assert (
                cursor.fetchone()[0] == records_to_add * 2
            )  # 1 for the document and 1 for the metadata

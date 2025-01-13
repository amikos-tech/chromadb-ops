import os
import shutil
import tempfile
import uuid

import chromadb
import numpy as np

from chroma_ops.db_clean import clean
from hypothesis import given, settings
import hypothesis.strategies as st


@given(
    records_to_add=st.sampled_from([100, 1000]),
    number_of_collections=st.integers(min_value=1, max_value=10),
)
@settings(deadline=None)
def test_clean(records_to_add: int, number_of_collections: int) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        client = chromadb.PersistentClient(path=temp_dir)
        for i in range(number_of_collections):
            col = client.get_or_create_collection(f"test_{i}")
            data = np.random.uniform(-1, 1, (records_to_add, 5))
            col.add(ids=[str(i) for i in range(records_to_add)], embeddings=data)
        for dir in os.listdir(temp_dir):
            if os.path.isdir(os.path.join(temp_dir, dir)) and os.path.exists(
                os.path.join(temp_dir, dir, "header.bin")
            ):
                shutil.copytree(
                    os.path.join(temp_dir, dir),
                    os.path.join(temp_dir, f"{uuid.uuid4()}"),
                )
        clean(temp_dir)
        segment_dirs = []
        for dir in os.listdir(temp_dir):
            if os.path.isdir(os.path.join(temp_dir, dir)) and os.path.exists(
                os.path.join(temp_dir, dir, "header.bin")
            ):
                segment_dirs.append(dir)
        assert len(segment_dirs) == number_of_collections

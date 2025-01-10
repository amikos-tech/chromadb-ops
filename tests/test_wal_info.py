
import tempfile
from hypothesis import given, settings
import hypothesis.strategies as st
import chromadb
import uuid
import numpy as np
from chroma_ops.wal_info import info_wal

@given(collections_to_create=st.integers(min_value=1, max_value=10) )
@settings(deadline=None, max_examples=10)
def test_wal_info(collections_to_create: int) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        client = chromadb.PersistentClient(path=temp_dir)
        collecttion_records_to_add = {}
        for i in range(collections_to_create):
            collecttion_records_to_add[f"test_collection_{i}"] = np.random.randint(100, 999)
        for collection_name,records_to_add in collecttion_records_to_add.items():
            col = client.get_or_create_collection(collection_name)
            ids = [str(uuid.uuid4()) for _ in range(records_to_add)]
            documents = [f"document {i}" for i in range(records_to_add)]
            embeddings = np.random.uniform(0, 1, (records_to_add, 384)).tolist()
            col.add(ids=ids, documents=documents, embeddings=embeddings)
        stats= info_wal(temp_dir)
        assert len(stats) == collections_to_create
        for stat in stats:
            assert collecttion_records_to_add[stat[0]] == stat[2]

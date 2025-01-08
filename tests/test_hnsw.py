import os
import shutil
import sqlite3
import tempfile
import uuid

import chromadb
import numpy as np
from chroma_ops.hnsw import info_hnsw, rebuild_hnsw, _get_hnsw_details
from hypothesis import given, settings
import hypothesis.strategies as st

@given(verbose=st.booleans())
def test_hnsw_info(verbose:bool) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        client = chromadb.PersistentClient(path=temp_dir)
        col = client.create_collection("test", metadata={"hnsw:search_ef":101, "hnsw:construction_ef":101, "hnsw:M":17, "hnsw:batch_size":101, "hnsw:sync_threshold":1001}) 
        col.add(ids=["1", "2", "3"], documents=["document 1", "document 2", "document 3"], embeddings=[[0.1] * 384] * 3)
        info_dict= info_hnsw(temp_dir, "test", verbose=verbose)
        assert info_dict["fragmentation_level"] == 0.0
        assert info_dict["collection_id"] == str(col.id)
        assert info_dict["num_elements"] == 0 # with too few elements, metadata is not created
        assert info_dict["dimensions"] == 384
        assert info_dict["ef_construction"] == 101
        assert info_dict["ef_search"] == 101
        assert info_dict["m"] == 17
        assert info_dict["batch_size"] == 101
        assert info_dict["sync_threshold"] == 1001
        assert "segment_id" in info_dict
        assert info_dict["path"] == os.path.join(temp_dir, info_dict["segment_id"])
        assert info_dict["has_metadata"] == False # with too few elements, metadata is not created
        assert "index_size" in info_dict
        assert info_dict["fragmentation_level"] == 0.0
        assert info_dict["fragmentation_level_estimated"] == True
        shutil.copy2(os.path.join(temp_dir, "chroma.sqlite3") , os.path.join(".", "chroma_before.sqlite3"))


@given(records_to_add=st.integers(min_value=100,max_value=10000),records_to_delete=st.integers(min_value=10,max_value=1000))
@settings(deadline=None,max_examples=5)
def test_hnsw_rebuild(records_to_add,records_to_delete) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        records_to_delete = min(records_to_delete,records_to_add)
        sql_file = os.path.join(temp_dir, "chroma.sqlite3") 
        client = chromadb.PersistentClient(path=temp_dir)
        col = client.get_or_create_collection("test_collection")
        ids = [str(uuid.uuid4()) for _ in range(records_to_add)]
        documents = [f"document {i}" for i in range(records_to_add)]
        embeddings = np.random.uniform(0, 1, (records_to_add, 384)).tolist()
        random_ids_to_delete = np.random.choice(ids, size=records_to_delete, replace=False)
        col.add(ids=ids, documents=documents, embeddings=embeddings)
        col.delete(ids=random_ids_to_delete.tolist())
        conn = sqlite3.connect(sql_file)
        details = _get_hnsw_details(conn, temp_dir, "test_collection", verbose=True)
        conn.close()
        should_have_fragmentation = False
        if records_to_add >= details["sync_threshold"] or records_to_add+records_to_delete >= details["sync_threshold"]:
            if records_to_delete > details["sync_threshold"]:
                assert details["fragmentation_level"] > 0.0
            elif int((records_to_add+records_to_delete) / details["sync_threshold"]) > int(records_to_add/details["sync_threshold"]):
                assert details["fragmentation_level"] > 0.0
            else:
                assert details["fragmentation_level"] == 0.0
        else:
            assert details["fragmentation_level"] == 0.0
        rebuild_hnsw(temp_dir, "test_collection",yes=True)
        if should_have_fragmentation:
            conn = sqlite3.connect(sql_file)
            details = _get_hnsw_details(conn, temp_dir, "test_collection", verbose=True)
            assert details["fragmentation_level"] == 0.0
            conn.close()

        # ensure the index is functional after rebuild/compaction
        client._admin_client.clear_system_cache()
        client = chromadb.PersistentClient(path=temp_dir)
        col = client.get_collection("test_collection")
        col.query(query_embeddings=np.random.uniform(0, 1, (1, 384)).tolist())
        new_ids = [str(uuid.uuid4()) for _ in range(100)]
        new_documents = [f"document {i}" for i in range(100)]
        new_embeddings = np.random.uniform(0, 1, (100, 384)).tolist()
        col.add(ids=new_ids, documents=new_documents, embeddings=new_embeddings)
        new_random_ids_to_delete = np.random.choice(new_ids, size=10, replace=False)
        col.delete(ids=new_random_ids_to_delete.tolist())


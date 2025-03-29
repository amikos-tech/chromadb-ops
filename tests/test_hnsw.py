import os
import shutil
import sqlite3
import tempfile
from typing import Optional
import uuid

import chromadb
import numpy as np
import pytest
from chroma_ops.constants import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_CONSTRUCTION_EF,
    DEFAULT_DISTANCE_METRIC,
    DEFAULT_M,
    DEFAULT_NUM_THREADS,
    DEFAULT_RESIZE_FACTOR,
    DEFAULT_SEARCH_EF,
    DEFAULT_SYNC_THRESHOLD,
)
from chroma_ops.hnsw import (
    info_hnsw,
    modify_runtime_config,
    rebuild_hnsw,
    _get_hnsw_details,
)
from hypothesis import given, settings
import hypothesis.strategies as st

from chroma_ops.utils import DistanceMetric


@given(verbose=st.booleans())
@settings(deadline=None)
def test_hnsw_info(verbose: bool) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        client = chromadb.PersistentClient(path=temp_dir)
        col = client.create_collection(
            "test",
            metadata={
                "hnsw:search_ef": 101,
                "hnsw:construction_ef": 101,
                "hnsw:M": 17,
                "hnsw:batch_size": 101,
                "hnsw:sync_threshold": 1001,
            },
        )
        col.add(
            ids=["1", "2", "3"],
            documents=["document 1", "document 2", "document 3"],
            embeddings=[[0.1] * 384] * 3,
        )
        info_dict = info_hnsw(temp_dir, "test", verbose=verbose)
        assert info_dict["fragmentation_level"] == 0.0
        assert info_dict["collection_id"] == str(col.id)
        assert (
            info_dict["num_elements"] == 0
        )  # with too few elements, metadata is not created
        assert info_dict["dimensions"] == 384
        assert info_dict["construction_ef"] == 101
        assert info_dict["search_ef"] == 101
        assert info_dict["m"] == 17
        assert info_dict["batch_size"] == 101
        assert info_dict["sync_threshold"] == 1001
        assert "segment_id" in info_dict
        assert info_dict["path"] == os.path.join(temp_dir, info_dict["segment_id"])
        assert (
            info_dict["has_metadata"] is False
        )  # with too few elements, metadata is not created
        assert "index_size" in info_dict
        assert info_dict["fragmentation_level"] == 0.0
        assert info_dict["fragmentation_level_estimated"] is True
        shutil.copy2(
            os.path.join(temp_dir, "chroma.sqlite3"),
            os.path.join(".", "chroma_before.sqlite3"),
        )


@given(
    records_to_add=st.integers(min_value=100, max_value=10000),
    records_to_delete=st.integers(min_value=100, max_value=5000),
)
@settings(deadline=None, max_examples=10)
def test_hnsw_rebuild(records_to_add: int, records_to_delete: int) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        records_to_delete = min(records_to_delete, records_to_add)
        sql_file = os.path.join(temp_dir, "chroma.sqlite3")
        client = chromadb.PersistentClient(path=temp_dir)
        col = client.get_or_create_collection("test_collection")
        ids = [str(uuid.uuid4()) for _ in range(records_to_add)]
        documents = [f"document {i}" for i in range(records_to_add)]
        embeddings = np.random.uniform(0, 1, (records_to_add, 384)).tolist()
        random_ids_to_delete = np.random.choice(
            ids, size=records_to_delete, replace=False
        )
        col.add(ids=ids, documents=documents, embeddings=embeddings)
        col.delete(ids=random_ids_to_delete.tolist())
        with sqlite3.connect(sql_file) as conn:
            details = _get_hnsw_details(conn, temp_dir, "test_collection", verbose=True)
        total_elements_before_rebuild = details["total_elements_added"]
        should_have_fragmentation = False
        if (
            records_to_add >= details["sync_threshold"]
            or records_to_add + records_to_delete >= details["sync_threshold"]
        ):
            if records_to_delete > details["sync_threshold"]:
                assert details["fragmentation_level"] > 0.0
            elif int(
                (records_to_add + records_to_delete) / details["sync_threshold"]
            ) > int(records_to_add / details["sync_threshold"]):
                assert details["fragmentation_level"] > 0.0
            else:
                assert details["fragmentation_level"] == 0.0
        else:
            assert details["fragmentation_level"] == 0.0
        rebuild_hnsw(
            temp_dir,
            collection_name="test_collection",
            yes=True,
        )
        with sqlite3.connect(sql_file) as conn:
            details = _get_hnsw_details(conn, temp_dir, "test_collection", verbose=True)
            total_elements_after_rebuild = details["total_elements_added"]
            if should_have_fragmentation:
                assert (
                    total_elements_after_rebuild < total_elements_before_rebuild
                )  # if the index is fragmented and needs compaction this also impacts the total elements
                assert details["fragmentation_level"] == 0.0
            else:
                assert total_elements_after_rebuild <= total_elements_before_rebuild
        print("details", details["total_elements_added"])
        print("details", details["max_elements"])
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


@given(
    records_to_add=st.integers(min_value=100, max_value=10000),
    space=st.sampled_from(
        [
            None,
            DistanceMetric.COSINE.value,
            DistanceMetric.IP.value,
            DistanceMetric.L2.value,
        ]
    ),
    batch_size=st.one_of(st.none(), st.integers(min_value=10, max_value=1000)),
    sync_threshold=st.one_of(st.none(), st.integers(min_value=100, max_value=10000)),
    m=st.one_of(st.none(), st.integers(min_value=10, max_value=100)),
    construction_ef=st.one_of(st.none(), st.integers(min_value=10, max_value=1000)),
    search_ef=st.one_of(st.none(), st.integers(min_value=10, max_value=1000)),
    num_threads=st.one_of(st.none(), st.integers(min_value=1, max_value=10)),
    resize_factor=st.one_of(st.none(), st.floats(min_value=1.0, max_value=10.0)),
)
@settings(deadline=None, max_examples=10)
def test_hnsw_rebuild_with_params(
    records_to_add: int,
    space: Optional[DistanceMetric],
    batch_size: Optional[int],
    sync_threshold: Optional[int],
    m: Optional[int],
    construction_ef: Optional[int],
    search_ef: Optional[int],
    num_threads: Optional[int],
    resize_factor: Optional[float],
) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        client = chromadb.PersistentClient(path=temp_dir)
        col = client.get_or_create_collection("test_collection")
        ids = [str(uuid.uuid4()) for _ in range(records_to_add)]
        documents = [f"document {i}" for i in range(records_to_add)]
        embeddings = np.random.uniform(0, 1, (records_to_add, 384)).tolist()
        col.add(ids=ids, documents=documents, embeddings=embeddings)
        rebuild_hnsw(
            temp_dir,
            collection_name="test_collection",
            space=space,
            batch_size=batch_size,
            sync_threshold=sync_threshold,
            m=m,
            construction_ef=construction_ef,
            search_ef=search_ef,
            num_threads=num_threads,
            resize_factor=round(resize_factor, 2) if resize_factor else None,
            yes=True,
        )
        hnsw_details = info_hnsw(temp_dir, "test_collection")
        assert hnsw_details["space"] == space or DEFAULT_DISTANCE_METRIC
        assert hnsw_details["batch_size"] == batch_size or DEFAULT_BATCH_SIZE
        assert (
            hnsw_details["sync_threshold"] == sync_threshold or DEFAULT_SYNC_THRESHOLD
        )
        assert hnsw_details["m"] == m or DEFAULT_M
        assert (
            hnsw_details["construction_ef"] == construction_ef
            or DEFAULT_CONSTRUCTION_EF
        )
        assert hnsw_details["search_ef"] == search_ef or DEFAULT_SEARCH_EF
        assert hnsw_details["num_threads"] == num_threads or DEFAULT_NUM_THREADS
        assert (
            hnsw_details["resize_factor"] == round(resize_factor, 2)
            if resize_factor
            else DEFAULT_RESIZE_FACTOR
        )


@given(
    records_to_add=st.integers(min_value=100, max_value=10000),
    batch_size=st.one_of(st.none(), st.integers(min_value=10, max_value=1000)),
    sync_threshold=st.one_of(st.none(), st.integers(min_value=100, max_value=10000)),
    search_ef=st.one_of(st.none(), st.integers(min_value=10, max_value=1000)),
    num_threads=st.one_of(st.none(), st.integers(min_value=1, max_value=10)),
    resize_factor=st.one_of(st.none(), st.floats(min_value=1.0, max_value=10.0)),
)
@settings(deadline=None, max_examples=10)
def test_hnsw_config(
    records_to_add: int,
    search_ef: Optional[int],
    num_threads: Optional[int],
    resize_factor: Optional[float],
    batch_size: Optional[int],
    sync_threshold: Optional[int],
) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        client = chromadb.PersistentClient(path=temp_dir)
        col = client.get_or_create_collection("test_collection")
        ids = [str(uuid.uuid4()) for _ in range(records_to_add)]
        documents = [f"document {i}" for i in range(records_to_add)]
        embeddings = np.random.uniform(0, 1, (records_to_add, 384)).tolist()
        col.add(ids=ids, documents=documents, embeddings=embeddings)
        modify_runtime_config(
            temp_dir,
            "test_collection",
            "default_database",
            search_ef=search_ef,
            num_threads=num_threads,
            resize_factor=round(resize_factor, 2) if resize_factor else None,
            batch_size=batch_size,
            sync_threshold=sync_threshold,
            yes=True,
        )
        hnsw_details = info_hnsw(temp_dir, "test_collection")
        assert hnsw_details["batch_size"] == batch_size or DEFAULT_BATCH_SIZE
        assert (
            hnsw_details["sync_threshold"] == sync_threshold or DEFAULT_SYNC_THRESHOLD
        )
        assert hnsw_details["search_ef"] == search_ef or DEFAULT_SEARCH_EF
        assert hnsw_details["num_threads"] == num_threads or DEFAULT_NUM_THREADS
        assert (
            hnsw_details["resize_factor"] == round(resize_factor, 2)
            if resize_factor
            else DEFAULT_RESIZE_FACTOR
        )


def test_hnsw_config_with_invalid_collection_name() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        client = chromadb.PersistentClient(path=temp_dir)
        client.get_or_create_collection("test_collection")

        with pytest.raises(ValueError):
            rebuild_hnsw(
                temp_dir,
                collection_name="invalid_collection_name",
                yes=True,
            )
        with pytest.raises(ValueError):
            modify_runtime_config(
                temp_dir,
                "invalid_collection_name",
                "default_database",
                yes=True,
            )

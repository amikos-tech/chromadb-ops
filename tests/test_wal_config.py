import json
import os
import tempfile
from typing import Optional
import uuid
import chromadb
import numpy as np
from hypothesis import given, settings
import hypothesis.strategies as st


from chroma_ops.utils import SqliteMode, get_sqlite_connection
from chroma_ops.wal_config import PurgeFlag, config_wal


@given(
    records_to_add=st.integers(min_value=100, max_value=10000),
    purge=st.one_of(st.none(), st.just(PurgeFlag.OFF), st.just(PurgeFlag.AUTO)),
)
@settings(deadline=None, max_examples=10)
def test_wal_config(records_to_add: int, purge: Optional[PurgeFlag]) -> None:
    sync_threshold = 1000
    with tempfile.TemporaryDirectory() as temp_dir:
        client = chromadb.PersistentClient(path=os.path.join(temp_dir, "original"))
        records_to_add = min(records_to_add, client.get_max_batch_size())
        col = client.create_collection("test_collection")
        ids = [f"{uuid.uuid4()}" for _ in range(records_to_add)]
        embeddings = np.random.uniform(0, 1, (records_to_add, 384))
        col.add(ids=ids, embeddings=embeddings)
        with get_sqlite_connection(
            os.path.join(temp_dir, "original"), SqliteMode.READ_WRITE
        ) as conn:
            cursor = conn.cursor()
            rows = cursor.execute("SELECT count(*) FROM embeddings_queue;").fetchone()
            assert rows[0] >= 1 and rows[0] <= sync_threshold
            config = json.loads(
                cursor.execute(
                    "SELECT config_json_str FROM embeddings_queue_config;"
                ).fetchone()[0]
            )
            assert config["automatically_purge"] is True
            cursor.close()
        client._admin_client.clear_system_cache()

        config_wal(os.path.join(temp_dir, "original"), purge=purge, yes=True)

        client = chromadb.PersistentClient(path=os.path.join(temp_dir, "original"))
        col = client.get_collection("test_collection")
        new_ids = [f"{uuid.uuid4()}" for _ in range(records_to_add)]
        embeddings = np.random.uniform(0, 1, (records_to_add, 384))
        col.add(ids=new_ids, embeddings=embeddings)

        with get_sqlite_connection(
            os.path.join(temp_dir, "original"), SqliteMode.READ_WRITE
        ) as conn:
            cursor = conn.cursor()
            config = json.loads(
                cursor.execute(
                    "SELECT config_json_str FROM embeddings_queue_config;"
                ).fetchone()[0]
            )
            assert (
                config["automatically_purge"] is False
                if purge is not None and purge == PurgeFlag.OFF
                else True
            )
            config = json.loads(
                cursor.execute(
                    "SELECT config_json_str FROM embeddings_queue_config;"
                ).fetchone()[0]
            )
            rows = cursor.execute("SELECT count(*) FROM embeddings_queue;").fetchone()
            if purge is not None and purge == PurgeFlag.OFF:
                assert rows[0] >= records_to_add + 1
            else:
                assert rows[0] >= 1 and rows[0] <= sync_threshold
            cursor.close()

        client._admin_client.clear_system_cache()

        config_wal(os.path.join(temp_dir, "original"), purge=PurgeFlag.AUTO, yes=True)

        client = chromadb.PersistentClient(path=os.path.join(temp_dir, "original"))
        col = client.get_collection("test_collection")
        new_ids = [f"{uuid.uuid4()}" for _ in range(records_to_add)]
        embeddings = np.random.uniform(0, 1, (records_to_add, 384))
        col.add(ids=new_ids, embeddings=embeddings)

        with get_sqlite_connection(
            os.path.join(temp_dir, "original"), SqliteMode.READ_WRITE
        ) as conn:
            cursor = conn.cursor()
            config = json.loads(
                cursor.execute(
                    "SELECT config_json_str FROM embeddings_queue_config;"
                ).fetchone()[0]
            )
            assert config["automatically_purge"] is True
            rows = cursor.execute("SELECT count(*) FROM embeddings_queue;").fetchone()
            assert rows[0] >= 1 and rows[0] <= sync_threshold
            cursor.close()
        client._admin_client.clear_system_cache()

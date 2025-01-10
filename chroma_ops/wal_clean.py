#!/usr/bin/env python3
import os
import sys
from typing import Optional, Sequence
import typer
from chromadb import __version__ as chroma_version
from chroma_ops.utils import (
    SqliteMode,
    get_sqlite_connection,
    validate_chroma_persist_dir,
    get_hnsw_index_ids,
    get_dir_size,
    PersistentData,
    decode_seq_id,
)
from chroma_ops.constants import DEFAULT_TENANT_ID, DEFAULT_TOPIC_NAMESPACE


def clean_wal(
    persist_dir: str,
    skip_collection_names: Optional[Sequence[str]] = None,
    tenant: Optional[str] = DEFAULT_TENANT_ID,
    topic_namespace: Optional[str] = DEFAULT_TOPIC_NAMESPACE,
) -> None:
    validate_chroma_persist_dir(persist_dir)
    typer.echo(f"Size before: {get_dir_size(persist_dir)}", file=sys.stderr)
    with get_sqlite_connection(persist_dir, SqliteMode.READ_WRITE) as conn:
        cursor = conn.cursor()
        if int(chroma_version.split(".")[1]) <= 4:
            collection_name_index = 4
            query = "SELECT s.id as 'segment',s.topic as 'topic', c.id as 'collection' , c.dimension as 'dimension', c.name FROM segments s LEFT JOIN collections c ON s.collection = c.id WHERE s.scope = 'VECTOR';"
        else:
            collection_name_index = 3
            query = "SELECT s.id as 'segment', c.id as 'collection' , c.dimension as 'dimension', c.name FROM segments s LEFT JOIN collections c ON s.collection = c.id WHERE s.scope = 'VECTOR';"

        cursor.execute(query)

        results = cursor.fetchall()
        wal_cleanup_queries = []
        for row in results:
            if (
                skip_collection_names
                and row[collection_name_index] in skip_collection_names
            ):
                continue
            if int(chroma_version.split(".")[1]) <= 4:
                segment_id = row[0]
                topic = row[1]
                collection_id = row[2]
            else:
                segment_id = row[0]
                collection_id = row[1]
                topic = f"persistent://{tenant}/{topic_namespace}/{collection_id}"
            metadata_pickle = os.path.join(
                persist_dir, segment_id, "index_metadata.pickle"
            )
            if os.path.exists(metadata_pickle):
                metadata = PersistentData.load_from_file(metadata_pickle)
                if hasattr(metadata, "max_seq_id"):
                    max_seq_id = metadata.max_seq_id
                else:
                    max_seq_id_query_hnsw_057 = (
                        "SELECT seq_id FROM max_seq_id WHERE segment_id = ?"
                    )
                    cursor.execute(max_seq_id_query_hnsw_057, [row[0]])
                    results = cursor.fetchall()
                    max_seq_id = decode_seq_id(results[0][0]) if len(results) > 0 else 0
                wal_cleanup_queries.append(
                    f"DELETE FROM embeddings_queue WHERE seq_id < {max_seq_id} AND topic='{topic}';"
                )
            else:
                hnsw_space = cursor.execute(
                    "select str_value from collection_metadata where collection_id=? and key='hnsw:space'",
                    (collection_id,),
                ).fetchone()
                if not hnsw_space:
                    continue
                hnsw_space = "l2" if hnsw_space is None else hnsw_space[0]
                list_of_ids = get_hnsw_index_ids(
                    f"{os.path.join(persist_dir, segment_id)}", hnsw_space, row[3]
                )
                batch_size = 100
                for batch in range(0, len(list_of_ids), batch_size):
                    wal_cleanup_queries.append(
                        f"DELETE FROM embeddings_queue WHERE seq_id IN ({','.join([str(i) for i in list_of_ids[batch:batch + batch_size]])});"
                    )
        if len(wal_cleanup_queries) > 0:
            typer.echo("Cleaning up WAL", file=sys.stderr)
            wal_cleanup_queries.insert(
                0, "BEGIN EXCLUSIVE;"
            )  # locking the DB exclusively to prevent other processes from accessing it
            wal_cleanup_queries.append("COMMIT;")
            wal_cleanup_queries.append("VACUUM;")
            cursor.executescript("\n".join(wal_cleanup_queries))
        # Close the cursor and connection
        cursor.close()
    typer.echo(f"Size after: {get_dir_size(persist_dir)}", file=sys.stderr)


def command(
    persist_dir: str = typer.Argument(..., help="The persist directory"),
    skip_collection_names: str = typer.Option(
        None,
        "--skip-collection-names",
        "-s",
        help="Comma separated list of collection names to skip",
    ),
) -> None:
    clean_wal(persist_dir, skip_collection_names=skip_collection_names)

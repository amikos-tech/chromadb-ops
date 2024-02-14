#!/usr/bin/env python3
import argparse
import os
import sqlite3
import sys
from typing import Optional, Sequence

import typer
from chromadb.segment.impl.vector.local_persistent_hnsw import PersistentData

from chroma_ops.utils import (
    validate_chroma_persist_dir,
    get_hnsw_index_ids,
    get_dir_size,
)


def clean_wal(
    persist_dir: str, skip_collection_names: Optional[Sequence[str]] = None
) -> None:
    validate_chroma_persist_dir(persist_dir)
    typer.echo(f"Size before: {get_dir_size(persist_dir)}", file=sys.stderr)
    sql_file = os.path.join(persist_dir, "chroma.sqlite3")
    conn = sqlite3.connect(sql_file)
    # conn = sqlite3.connect(f"file:{sql_file}?mode=ro", uri=True)

    cursor = conn.cursor()

    query = "SELECT s.id as 'segment',s.topic as 'topic', c.id as 'collection' , c.dimension as 'dimension', c.name FROM segments s LEFT JOIN collections c ON s.collection = c.id WHERE s.scope = 'VECTOR';"

    cursor.execute(query)

    results = cursor.fetchall()
    wal_cleanup_queries = []
    for row in results:
        if skip_collection_names and row[4] in skip_collection_names:
            continue
        metadata_pickle = os.path.join(persist_dir, row[0], "index_metadata.pickle")
        if os.path.exists(metadata_pickle):
            metadata = PersistentData.load_from_file(metadata_pickle)
            wal_cleanup_queries.append(
                f"DELETE FROM embeddings_queue WHERE seq_id < {metadata.max_seq_id} AND topic='{row[1]}';"
            )
        else:
            hnsw_space = cursor.execute(
                "select str_value from collection_metadata where collection_id=? and key='hnsw:space'",
                (row[2],),
            ).fetchone()
            if not hnsw_space:
                continue
            hnsw_space = "l2" if hnsw_space is None else hnsw_space[0]
            list_of_ids = get_hnsw_index_ids(
                f"{os.path.join(persist_dir, row[0])}", hnsw_space, row[3]
            )
            batch_size = 100
            for batch in range(0, len(list_of_ids), batch_size):
                wal_cleanup_queries.append(
                    f"DELETE FROM embeddings_queue WHERE seq_id IN ({','.join([str(i) for i in list_of_ids[batch:batch + batch_size]])});"
                )
    if len(wal_cleanup_queries) > 0:
        typer.echo("Cleaning up WAL", file=sys.stderr)
        wal_cleanup_queries.append("VACUUM;")
        cursor.executescript("\n".join(wal_cleanup_queries))
    # Close the cursor and connection
    cursor.close()
    conn.close()
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("persist_dir", type=str)
    parser.add_argument("--skip-collection-names", type=str, default=None)
    arg = parser.parse_args()
    clean_wal(arg.persist_dir, skip_collection_names=arg.skip_collection_names)

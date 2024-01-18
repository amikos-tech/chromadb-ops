#!/usr/bin/env python3
import argparse
import os
import sqlite3
import hnswlib
import typer
from chromadb.segment.impl.vector.local_persistent_hnsw import PersistentData

from chroma_ops.utils import validate_chroma_persist_dir, get_hnsw_index_ids, get_dir_size


def clean_wal(persist_dir: str):
    validate_chroma_persist_dir(persist_dir)
    print("Size before: ", get_dir_size(persist_dir))
    # TODO add path join here
    sql_file = os.path.join(persist_dir, "chroma.sqlite3")
    conn = sqlite3.connect(sql_file)
    # conn = sqlite3.connect(f"file:{sql_file}?mode=ro", uri=True)

    cursor = conn.cursor()

    query = "SELECT s.id as 'segment',s.topic as 'topic', c.id as 'collection' , c.dimension as 'dimension' FROM segments s LEFT JOIN collections c ON s.collection = c.id WHERE s.scope = 'VECTOR';"

    cursor.execute(query)

    results = cursor.fetchall()
    wal_cleanup_queries = []
    for row in results:
        metadata_pickle = os.path.join(persist_dir, row[0], 'index_metadata.pickle')
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
        print("Cleaning up WAL")
        wal_cleanup_queries.append("VACUUM;")
        cursor.executescript("\n".join(wal_cleanup_queries))
    # Close the cursor and connection
    cursor.close()
    conn.close()
    print("Size after: ", get_dir_size(persist_dir))


def command(
        persist_dir: str = typer.Argument(..., help="The persist directory"),
):
    clean_wal(persist_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("persist_dir", type=str)
    arg = parser.parse_args()
    clean_wal(arg.persist_dir)

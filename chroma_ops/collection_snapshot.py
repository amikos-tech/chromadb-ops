import hashlib
import os
from pathlib import Path
import sqlite3
import sys
from typing import List, Tuple
import zlib
import typer
from chromadb import __version__ as chroma_version
from chroma_ops.constants import DEFAULT_TENANT_ID, DEFAULT_TOPIC_NAMESPACE
from chroma_ops.utils import (
    SqliteMode,
    get_sqlite_connection,
    get_sqlite_snapshot_connection,
    list_collections,
    read_script,
    validate_chroma_persist_dir,
)
from rich.console import Console
from rich.table import Table

def _copy_collection_to_snapshot_db(persist_dir: str, collection: str, output_file: Path) -> None:
     with get_sqlite_connection(persist_dir, SqliteMode.READ_WRITE) as conn:
        collection_id = conn.execute(
            "SELECT id FROM collections WHERE name = ?",
            (collection,),
        ).fetchone()
        if not collection_id:
            raise ValueError(f"Collection {collection} not found")
        collection_id = collection_id[0]
        vector_segment_id = conn.execute(
            "SELECT id FROM segments WHERE scope = 'VECTOR' AND collection = ?",
            (collection_id,),
        ).fetchone()
        if not vector_segment_id:
            raise ValueError(f"Vector segment for collection {collection} not found")
        vector_segment_id = vector_segment_id[0]
        metadata_segment_id = conn.execute(
            "SELECT id FROM segments WHERE scope = 'METADATA' AND collection = ?",
            (collection_id,),
        ).fetchone()
        if not metadata_segment_id:
            raise ValueError(f"Metadata segment for collection {collection} not found")
        metadata_segment_id = metadata_segment_id[0]
        topic = f"persistent://{DEFAULT_TENANT_ID}/{DEFAULT_TOPIC_NAMESPACE}/{collection_id}"

        conn.execute("BEGIN EXCLUSIVE")
        try:
            conn.execute("ATTACH DATABASE ? AS snapshot", (output_file.absolute().as_posix(),))
            # copy the collection to the snapshot db
            conn.execute("INSERT INTO snapshot.embeddings_queue SELECT * FROM main.embeddings_queue WHERE topic = ?", (topic,))
            conn.execute("INSERT INTO snapshot.max_seq_id SELECT * FROM main.max_seq_id WHERE segment_id IN (?, ?)", (vector_segment_id, metadata_segment_id))
            conn.execute("INSERT INTO snapshot.embeddings SELECT * FROM main.embeddings WHERE segment_id = ? ", (metadata_segment_id,))
            conn.execute("INSERT INTO snapshot.embedding_metadata SELECT * FROM main.embedding_metadata WHERE id IN (SELECT id FROM main.embeddings WHERE segment_id = ?)", (metadata_segment_id,))
            conn.execute("INSERT INTO snapshot.segments SELECT * FROM main.segments WHERE collection = ?", (collection_id,))
            conn.execute("INSERT INTO snapshot.segment_metadata SELECT * FROM main.segment_metadata WHERE segment_id IN (SELECT id FROM main.segments WHERE collection = ?)", (collection_id,))
            conn.execute("""
                INSERT INTO snapshot.collections (id, name, dimension, database_id, database_name, tenant_id, config_json_str)
                SELECT 
                    src.id,
                    src.name,
                    src.dimension,
                    src.database_id,
                    db.name AS database_name,
                    t.id AS tenant_id,
                    src.config_json_str
                FROM 
                    main.collections AS src
                JOIN 
                    main.databases AS db ON src.database_id = db.id
                JOIN 
                    tenants AS t ON db.tenant_id = t.id
                WHERE 
                    src.id = ?;
                """, (collection_id,))
            conn.execute("INSERT INTO snapshot.collection_metadata SELECT * FROM main.collection_metadata WHERE collection_id = ?", (collection_id,))
            segment_dir = os.path.join(persist_dir, vector_segment_id)
            for filename in os.listdir(segment_dir):
                filepath = os.path.join(segment_dir, filename)
                if os.path.isfile(filepath):
                    with open(filepath, "rb") as file:
                        binary_data = file.read()
                    compressed_data = zlib.compress(binary_data)
                    sha256 = hashlib.sha256(binary_data).hexdigest()
                    # Insert the compressed data into the database
                    conn.execute(
                        "INSERT INTO snapshot.hnsw_segment_data (segment_id, filename, data, sha256) VALUES (?, ?, ?, ?)",
                        (vector_segment_id, filename, compressed_data, sha256)
                    )
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e

def collection_snapshot(persist_dir: str, collection: str, output_file: Path) -> None:
    if tuple(int(part) for part in chroma_version.split(".")) < (0, 6, 0):
        console.print("Collection snapshot is not supported for this version of ChromaDB", file=sys.stderr)
        sys.exit(1)
    validate_chroma_persist_dir(persist_dir)
    console = Console()
    with get_sqlite_snapshot_connection(output_file.absolute().as_posix()) as conn:
        script = read_script("scripts/snapshot.sql")
        conn.executescript(script)
        conn.commit()
    _copy_collection_to_snapshot_db(persist_dir, collection, output_file)

# lock the db to prevent accidental writes
# create the new snapshot schema
# copy the collection to the snapshot db
# copy the collection metadata to the snapshot db
# unlock the db

def command(
    persist_dir: str = typer.Argument(..., help="The persist directory"),
    collection: str = typer.Option(..., "--collection", "-c", help="The collection to snapshot"),
    output_file: Path = typer.Option(..., "--output", "-o", help="The output file"),
) -> None:
    collection_snapshot(persist_dir, collection, output_file)


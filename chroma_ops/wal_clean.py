#!/usr/bin/env python3
import os
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
from rich.console import Console


def clean_wal(
    persist_dir: str,
    skip_collection_names: Optional[Sequence[str]] = None,
    tenant: Optional[str] = DEFAULT_TENANT_ID,
    topic_namespace: Optional[str] = DEFAULT_TOPIC_NAMESPACE,
    yes: Optional[bool] = False,
) -> None:
    validate_chroma_persist_dir(persist_dir)
    console = Console()
    console.print(f"[green]Size before: {get_dir_size(persist_dir)}[/green]")
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
        if len(results) == 0:
            console.print("[green]No WAL entries found. Nothing to clean up.[/green]")
            return
        if not yes:
            if not typer.confirm(
                f"\nAre you sure you want to clean up the WAL in {persist_dir}? This action will delete all WAL entries that are not committed to the HNSW index.",
                default=False,
                show_default=True,
            ):
                console.print("[yellow]WAL cleanup cancelled by user[/yellow]")
                return
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
                # TODO this way of getting the hnsw space might be wrong going forward with 0.6.x
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
            console.print("[green]Cleaning up WAL[/green]")
            wal_cleanup_queries.insert(
                0, "BEGIN EXCLUSIVE;"
            )  # locking the DB exclusively to prevent other processes from accessing it
            wal_cleanup_queries.append("COMMIT;")
            wal_cleanup_queries.append("VACUUM;")
            cursor.executescript("\n".join(wal_cleanup_queries))
        # Close the cursor and connection
        cursor.close()
    console.print(
        f"[green]WAL cleaned up. Size after: {get_dir_size(persist_dir)}[/green]"
    )


def command(
    persist_dir: str = typer.Argument(..., help="The persist directory"),
    skip_collection_names: str = typer.Option(
        None,
        "--skip-collection-names",
        "-s",
        help="Comma separated list of collection names to skip",
    ),
    yes: Optional[bool] = typer.Option(
        False, "--yes", "-y", help="Skip confirmation prompt"
    ),
) -> None:
    clean_wal(persist_dir, skip_collection_names=skip_collection_names, yes=yes)

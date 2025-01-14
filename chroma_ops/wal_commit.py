#!/usr/bin/env python3
import os
from typing import Sequence, Optional

import chromadb
import typer
from rich.console import Console
from chromadb.segment.impl.vector.local_persistent_hnsw import PersistentData
from chromadb.segment import VectorReader
from chromadb.types import Operation
from chromadb import __version__ as chroma_version
from chroma_ops.constants import DEFAULT_TENANT_ID, DEFAULT_TOPIC_NAMESPACE
from chroma_ops.utils import (
    SqliteMode,
    get_sqlite_connection,
    validate_chroma_persist_dir,
)
from rich.table import Table


def commit_wal(
    persist_dir: str,
    skip_collection_names: Optional[Sequence[str]] = None,
    yes: Optional[bool] = False,
    tenant: Optional[str] = DEFAULT_TENANT_ID,
    topic_namespace: Optional[str] = DEFAULT_TOPIC_NAMESPACE,
) -> None:
    """Note this uses internal ChromaDB APIs which may change at any moment."""
    validate_chroma_persist_dir(persist_dir)
    skip_collection_names = skip_collection_names or []
    console = Console()
    collections_to_commit = []
    vector_segments = []
    skipped_collections_table = Table(title="Skipped Collections")
    skipped_collections_table.add_column("Collection", style="cyan")
    table = Table(title="WAL Commit Summary")
    table.add_column("Collection", style="cyan")
    table.add_column("WAL Entries", style="magenta")
    with get_sqlite_connection(persist_dir, SqliteMode.READ_ONLY) as conn:
        collections = conn.execute(
            "SELECT c.name,c.id, s.id FROM collections c left join segments s on c.id=s.collection where s.scope='VECTOR'"
        ).fetchall()
        wal_topic_groups = conn.execute(
            "SELECT topic, count(*) FROM embeddings_queue group by topic"
        ).fetchall()
        if len(collections) == 0:
            console.print("[yellow]No collections found in the database.[/yellow]")
            return
        for collection in collections:
            if collection[0] not in skip_collection_names:
                topic = f"persistent://{tenant}/{topic_namespace}/{collection[1]}"
                table.add_row(
                    collection[0],
                    str([s[1] for s in wal_topic_groups if s[0] == topic][0]),
                )
                collections_to_commit.append(collection)
                vector_segments.append(
                    {"collection_id": collection[1], "id": collection[2]}
                )
            else:
                skipped_collections_table.add_row(collection[0])
    console.print(table)
    console.print(skipped_collections_table)
    if not yes:
        if not typer.confirm(
            f"\nAre you sure you want to commit the WAL in {persist_dir}? As part of the WAL commit action your database will be migrated to currently installed version {chroma_version}.",
            default=False,
            show_default=True,
        ):
            console.print("[yellow]WAL commit cancelled by user[/yellow]")
            return
    client = chromadb.PersistentClient(path=persist_dir)

    for s in vector_segments:
        col = client._server._get_collection(
            s["collection_id"]
        )  # load the collection and apply WAL
        client._server._manager.hint_use_collection(
            s["collection_id"], Operation.ADD
        )  # Add hint to load the index into memory
        segment = client._server._manager.get_segment(
            s["collection_id"], VectorReader
        )  # Get the segment instance
        segment._apply_batch(segment._curr_batch)  # Apply the current WAL batch

        segment._persist()  # persist the index
        PersistentData.load_from_file(
            os.path.join(persist_dir, str(s["id"]), "index_metadata.pickle")
        )  # load the metadata after persisting
        console.print(
            f"Processing index for collection {col['name']} ({s['id']}) - "
            f"total vectors in index {len(segment._index.get_ids_list())}",
        )
        segment.close_persistent_index()
    console.print("[green]WAL commit completed.[/green]")


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
    commit_wal(persist_dir, skip_collection_names=skip_collection_names, yes=yes)

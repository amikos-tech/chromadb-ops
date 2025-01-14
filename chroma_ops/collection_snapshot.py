import hashlib
import os
from pathlib import Path
import sys
from typing import Optional
import zlib
import typer
from chromadb import __version__ as chroma_version
from chroma_ops.constants import DEFAULT_TENANT_ID, DEFAULT_TOPIC_NAMESPACE
from chroma_ops.utils import (
    SqliteMode,
    get_sqlite_connection,
    get_sqlite_snapshot_connection,
    read_script,
    validate_chroma_persist_dir,
)
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table


def _copy_collection_to_snapshot_db(
    persist_dir: str, collection: str, output_file: Path, yes: Optional[bool] = False
) -> None:
    console = Console()
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
        segment_dir = os.path.join(persist_dir, vector_segment_id)
        topic = f"persistent://{DEFAULT_TENANT_ID}/{DEFAULT_TOPIC_NAMESPACE}/{collection_id}"
        table = Table(title="Copying collection to snapshot database...")
        table.add_column("Table", style="cyan")
        table.add_column("Count", style="magenta")
        console.print(
            f"Copying collection [red]{collection}[/red] to snapshot database..."
        )
        embeddings_queue_count = conn.execute(
            "SELECT COUNT(*) FROM main.embeddings_queue WHERE topic = ?",
            (topic,),
        ).fetchone()
        table.add_row("Embeddings Queue", f"{embeddings_queue_count[0]:,}")
        max_seq_id_count = conn.execute(
            "SELECT COUNT(*) FROM main.max_seq_id WHERE segment_id IN (?, ?)",
            (vector_segment_id, metadata_segment_id),
        ).fetchone()
        table.add_row("Max Seq ID", f"{max_seq_id_count[0]:,}")
        embeddings_count = conn.execute(
            "SELECT COUNT(*) FROM main.embeddings WHERE segment_id = ?",
            (metadata_segment_id,),
        ).fetchone()
        table.add_row("Embeddings", f"{embeddings_count[0]:,}")
        embedding_metadata_count = conn.execute(
            "SELECT COUNT(*) FROM main.embedding_metadata WHERE id IN (SELECT id FROM main.embeddings WHERE segment_id = ?)",
            (metadata_segment_id,),
        ).fetchone()
        table.add_row("Embedding Metadata", f"{embedding_metadata_count[0]:,}")
        segments_count = conn.execute(
            "SELECT COUNT(*) FROM main.segments WHERE collection = ?",
            (collection_id,),
        ).fetchone()
        table.add_row("Segments", f"{segments_count[0]:,}")
        segment_metadata_count = conn.execute(
            "SELECT COUNT(*) FROM main.segment_metadata WHERE segment_id IN (SELECT id FROM main.segments WHERE collection = ?)",
            (collection_id,),
        ).fetchone()
        table.add_row("Segment Metadata", f"{segment_metadata_count[0]:,}")
        collections_count = conn.execute(
            "SELECT COUNT(*) FROM main.collections WHERE id = ?",
            (collection_id,),
        ).fetchone()
        table.add_row("Collections", f"{collections_count[0]:,}")
        collection_metadata_count = conn.execute(
            "SELECT COUNT(*) FROM main.collection_metadata WHERE collection_id = ?",
            (collection_id,),
        ).fetchone()
        table.add_row("Collection Metadata", f"{collection_metadata_count[0]:,}")
        table.add_row("HNSW Segment Data Files", f"{len(os.listdir(segment_dir)):,}")
        console.print(table)
        if not yes:
            if not typer.confirm(
                "\nAre you sure you want to copy this collection to the snapshot database?",
                default=False,
                show_default=True,
            ):
                console.print("[yellow]Copy cancelled by user[/yellow]")
                return
        conn.execute("BEGIN EXCLUSIVE")
        try:
            with Progress(
                SpinnerColumn(
                    finished_text="[bold green]:heavy_check_mark:[/bold green]"
                ),
                TextColumn("[progress.description]{task.description}"),
                *[
                    BarColumn(),
                    TextColumn("{task.percentage:>3.0f}%"),
                ],  # Add these columns
                transient=True,
            ) as progress:
                conn.execute(
                    "ATTACH DATABASE ? AS snapshot",
                    (output_file.absolute().as_posix(),),
                )
                # copy the collection to the snapshot db
                task = progress.add_task("Copying embedings_queue...", total=0)
                conn.execute(
                    "INSERT INTO snapshot.embeddings_queue SELECT * FROM main.embeddings_queue WHERE topic = ?",
                    (topic,),
                )
                progress.update(task, advance=1)
                task = progress.add_task("Copying max_seq_id...", total=0)
                conn.execute(
                    "INSERT INTO snapshot.max_seq_id SELECT * FROM main.max_seq_id WHERE segment_id IN (?, ?)",
                    (vector_segment_id, metadata_segment_id),
                )
                progress.update(task, advance=1)
                task = progress.add_task("Copying embeddings...", total=0)
                conn.execute(
                    "INSERT INTO snapshot.embeddings SELECT * FROM main.embeddings WHERE segment_id = ? ",
                    (metadata_segment_id,),
                )
                progress.update(task, advance=1)
                task = progress.add_task("Copying embedding_metadata...", total=0)
                conn.execute(
                    "INSERT INTO snapshot.embedding_metadata SELECT * FROM main.embedding_metadata WHERE id IN (SELECT id FROM main.embeddings WHERE segment_id = ?)",
                    (metadata_segment_id,),
                )
                progress.update(task, advance=1)
                task = progress.add_task("Copying segments...", total=0)
                conn.execute(
                    "INSERT INTO snapshot.segments SELECT * FROM main.segments WHERE collection = ?",
                    (collection_id,),
                )
                progress.update(task, advance=1)
                task = progress.add_task("Copying segment_metadata...", total=0)
                conn.execute(
                    "INSERT INTO snapshot.segment_metadata SELECT * FROM main.segment_metadata WHERE segment_id IN (SELECT id FROM main.segments WHERE collection = ?)",
                    (collection_id,),
                )
                progress.update(task, advance=1)
                task = progress.add_task("Copying collections...", total=0)
                conn.execute(
                    """
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
                    """,
                    (collection_id,),
                )
                progress.update(task, advance=1)
                task = progress.add_task("Copying collection_metadata...", total=0)
                conn.execute(
                    "INSERT INTO snapshot.collection_metadata SELECT * FROM main.collection_metadata WHERE collection_id = ?",
                    (collection_id,),
                )
                progress.update(task, advance=1)

                task = progress.add_task(
                    "Copying hnsw_segment_data...", total=len(os.listdir(segment_dir))
                )
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
                            (vector_segment_id, filename, compressed_data, sha256),
                        )
                        progress.update(task, advance=1)
            conn.commit()
            console.print(
                f"[green]Collection [red]{collection}[/red] copied to snapshot database in [red]{output_file.absolute().as_posix()}[/red][/green]"
            )
        except Exception as e:
            conn.rollback()
            raise e


def collection_snapshot(
    persist_dir: str,
    collection: str,
    output_file: Path,
    yes: Optional[bool] = False,
) -> None:
    console = Console()
    if tuple(int(part) for part in chroma_version.split(".")) < (0, 6, 0):
        console.print(
            "Collection snapshot is not supported for this version of ChromaDB",
            file=sys.stderr,
        )
        sys.exit(1)
    validate_chroma_persist_dir(persist_dir)
    if output_file.exists():
        if not yes:
            if not typer.confirm(
                f"\nAre you sure you want to overwrite {output_file.absolute().as_posix()} file?",
                default=False,
                show_default=True,
            ):
                console.print("[yellow]Snapshot cancelled by user[/yellow]")
                return
        os.remove(output_file.absolute().as_posix())
    os.makedirs(output_file.parent, exist_ok=True)
    console = Console()
    with get_sqlite_snapshot_connection(output_file.absolute().as_posix()) as conn:
        console.print("Bootstrapping snapshot database...")
        script = read_script("scripts/snapshot.sql")
        conn.executescript(script)
        conn.commit()
        console.print(
            f"[green]Snapshot database bootstrapped in [red]{output_file.absolute().as_posix()}[/red][/green]"
        )
    _copy_collection_to_snapshot_db(persist_dir, collection, output_file, yes=yes)


def command(
    persist_dir: str = typer.Argument(..., help="The persist directory"),
    collection: str = typer.Option(
        ..., "--collection", "-c", help="The collection to snapshot"
    ),
    output_file: Path = typer.Option(..., "--output", "-o", help="The output file"),
    yes: Optional[bool] = typer.Option(
        False, "--yes", "-y", help="Skip confirmation prompt"
    ),
) -> None:
    collection_snapshot(persist_dir, collection, output_file, yes=yes)

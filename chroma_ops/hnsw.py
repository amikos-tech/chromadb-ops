import datetime
import json
import os
import shutil
import sqlite3
import tempfile
import traceback
from typing import Dict, Optional, TypedDict
import hnswlib
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table
from chroma_ops.utils import (
    SqliteMode,
    get_sqlite_connection,
    validate_chroma_persist_dir,
    get_dir_size,
    PersistentData,
    sizeof_fmt,
)

hnsw_commands = typer.Typer()


class HnswDetails(TypedDict):
    collection_name: str
    database: str
    space: str
    dimensions: int
    ef_construction: int
    ef_search: int
    m: int
    num_threads: int
    resize_factor: int
    batch_size: int
    sync_threshold: int
    segment_id: str
    path: str
    has_metadata: bool
    num_elements: int
    id_to_label: Dict[str, int]
    collection_id: str
    index_size: str
    fragmentation_level: float
    fragmentation_level_estimated: bool


def _get_hnsw_details(
    conn: sqlite3.Connection,
    persist_dir: str,
    collection_name: str,
    database: Optional[str] = "default_database",
    verbose: Optional[bool] = False,
) -> HnswDetails:
    collection_details = conn.execute(
        "SELECT id,dimension FROM collections WHERE name = ?", (collection_name,)
    ).fetchone()
    # config = json.loads(collection_details[1])
    config = {}

    segment_id = conn.execute(
        "SELECT id FROM segments WHERE scope = 'VECTOR' AND collection = ?",
        (collection_details[0],),
    ).fetchone()
    segment_metadata = conn.execute(
        """ SELECT json_object(
    'segment_id', segment_id,
    'metadata', json_object(
        'hnsw:search_ef',MAX(CASE WHEN key = 'hnsw:search_ef' THEN int_value END),
        'hnsw:construction_ef', MAX(CASE WHEN key = 'hnsw:construction_ef' THEN int_value END),
        'hnsw:M', MAX(CASE WHEN key = 'hnsw:M' THEN int_value END),
        'hnsw:batch_size', MAX(CASE WHEN key = 'hnsw:batch_size' THEN int_value END),
        'hnsw:sync_threshold', MAX(CASE WHEN key = 'hnsw:sync_threshold' THEN int_value END),
        'hnsw:space', MAX(CASE WHEN key = 'hnsw:space' THEN str_value END),
        'hnsw:num_threads', MAX(CASE WHEN key = 'hnsw:num_threads' THEN int_value END),
        'hnsw:resize_factor', MAX(CASE WHEN key = 'hnsw:resize_factor' THEN float_value END)
        )
    ) AS result_json
    FROM segment_metadata WHERE segment_id = ?""",
        (segment_id[0],),
    ).fetchone()

    config = json.loads(segment_metadata[0])["metadata"]
    space = (
        config["hnsw:space"]
        if "hnsw:space" in config and config["hnsw:space"]
        else "l2"
    )
    ef_construction = (
        config["hnsw:construction_ef"]
        if "hnsw:construction_ef" in config and config["hnsw:construction_ef"]
        else 100
    )
    ef_search = (
        config["hnsw:search_ef"]
        if "hnsw:search_ef" in config and config["hnsw:search_ef"]
        else 100
    )
    m = config["hnsw:M"] if "hnsw:M" in config and config["hnsw:M"] else 16
    num_threads = (
        config["hnsw:num_threads"]
        if "hnsw:num_threads" in config and config["hnsw:num_threads"]
        else 1
    )
    resize_factor = (
        config["hnsw:resize_factor"]
        if "hnsw:resize_factor" in config and config["hnsw:resize_factor"]
        else 1.2
    )
    batch_size = (
        config["hnsw:batch_size"]
        if "hnsw:batch_size" in config and config["hnsw:batch_size"]
        else 100
    )
    sync_threshold = (
        config["hnsw:sync_threshold"]
        if "hnsw:sync_threshold" in config and config["hnsw:sync_threshold"]
        else 1000
    )
    dimensions = collection_details[1]
    id_to_label = {}
    fragmentation_level = 0.0
    fragmentation_level_estimated = True

    if os.path.exists(
        os.path.join(persist_dir, segment_id[0], "index_metadata.pickle")
    ):
        has_metadata = True
        persistent_data = PersistentData.load_from_file(
            os.path.join(persist_dir, segment_id[0], "index_metadata.pickle")
        )
        id_to_label = persistent_data.id_to_label
        if len(id_to_label) > 0:
            fragmentation_level = (
                (persistent_data.total_elements_added - len(id_to_label))
                / persistent_data.total_elements_added
                * 100
            )
        else:
            fragmentation_level = 0.0
            fragmentation_level_estimated = False
        if verbose:
            index = hnswlib.Index(space=space, dim=dimensions)
            index.load_index(
                os.path.join(persist_dir, segment_id[0]),
                is_persistent_index=True,
                max_elements=len(id_to_label),
            )
            index.set_num_threads(num_threads)
            index.set_ef(ef_search)
            total_elements = index.element_count
            if total_elements > 0:
                fragmentation_level = (
                    (total_elements - len(id_to_label)) / total_elements * 100
                )
                fragmentation_level_estimated = False
            else:
                fragmentation_level = 0.0
                fragmentation_level_estimated = False
            index.close_file_handles()
    else:
        has_metadata = False

    return HnswDetails(
        collection_name=collection_name,
        database=database if database else "default_database",
        space=space,
        dimensions=dimensions,
        ef_construction=ef_construction,
        ef_search=ef_search,
        m=m,
        num_threads=num_threads,
        resize_factor=resize_factor,
        batch_size=batch_size,
        sync_threshold=sync_threshold,
        segment_id=segment_id[0],
        path=os.path.join(persist_dir, segment_id[0]),
        has_metadata=has_metadata,
        num_elements=len(id_to_label),
        id_to_label=id_to_label,
        collection_id=collection_details[0],
        index_size=sizeof_fmt(
            get_dir_size(os.path.join(persist_dir, segment_id[0])),
        ),
        fragmentation_level=fragmentation_level,
        fragmentation_level_estimated=fragmentation_level_estimated,
    )


def print_hnsw_details(hnsw_details: HnswDetails) -> None:
    console = Console()
    table = Table(
        title=f"HNSW details for collection [red]{hnsw_details['collection_name']}[/red] in [red]{hnsw_details['database']}[/red] database"
    )

    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    # Add rows for each detail
    table.add_row("Space", str(hnsw_details["space"]))
    table.add_row("Dimensions", str(hnsw_details["dimensions"]))
    table.add_row("EF Construction", str(hnsw_details["ef_construction"]))
    table.add_row("EF Search", str(hnsw_details["ef_search"]))
    table.add_row("M", str(hnsw_details["m"]))
    table.add_row("Number of threads", str(hnsw_details["num_threads"]))
    table.add_row("Resize factor", str(hnsw_details["resize_factor"]))
    table.add_row("Batch size", str(hnsw_details["batch_size"]))
    table.add_row("Sync threshold", str(hnsw_details["sync_threshold"]))
    table.add_row("Segment ID", hnsw_details["segment_id"])
    table.add_row("Path", hnsw_details["path"])
    table.add_row("Has metadata", str(hnsw_details["has_metadata"]))
    table.add_row("Number of elements", str(hnsw_details["num_elements"]))
    table.add_row("Collection ID", str(hnsw_details["collection_id"]))
    table.add_row("Index size", hnsw_details["index_size"])
    table.add_row(
        "Fragmentation level",
        f"{hnsw_details['fragmentation_level']:.2f}% {'(estimated)' if hnsw_details['fragmentation_level_estimated'] else ''}",
    )
    console.print(table)


def rebuild_hnsw(
    persist_dir: str,
    collection_name: str,
    database: Optional[str] = "default_database",
    backup: Optional[bool] = True,
    yes: Optional[bool] = False,
) -> None:
    """Rebuilds the HNSW index in-place"""
    validate_chroma_persist_dir(persist_dir)
    console = Console()
    with get_sqlite_connection(persist_dir, SqliteMode.READ_WRITE) as conn:
        # lock the database to ensure no new data is added while we are rebuilding the index
        conn.execute("BEGIN EXCLUSIVE")
        try:
            hnsw_details = _get_hnsw_details(
                conn, persist_dir, collection_name, database
            )
            if not hnsw_details["has_metadata"]:
                console.print(
                    f"[red]Index metadata not found for segment {hnsw_details['segment_id']}. No need to rebuild.[/red]"
                )
                return
            space = hnsw_details["space"]
            ef_construction = hnsw_details["ef_construction"]
            ef_search = hnsw_details["ef_search"]
            m = hnsw_details["m"]
            num_threads = hnsw_details["num_threads"]
            batch_size = hnsw_details["batch_size"]
            segment_id = hnsw_details["segment_id"]
            dimensions = hnsw_details["dimensions"]
            id_to_label = hnsw_details["id_to_label"]
            with tempfile.TemporaryDirectory() as temp_dir:
                # TODO get dir size to ensure we have enough space to copy the index files
                temp_persist_dir = os.path.join(temp_dir, segment_id)
                shutil.copytree(os.path.join(persist_dir, segment_id), temp_persist_dir)
                target_index = hnswlib.Index(space=space, dim=dimensions)
                target_index.init_index(
                    max_elements=len(id_to_label),
                    ef_construction=ef_construction,
                    M=m,
                    is_persistent_index=True,
                    persistence_location=temp_persist_dir,
                )
                target_index.set_num_threads(num_threads)
                target_index.set_ef(ef_search)
                source_index = hnswlib.Index(space=space, dim=dimensions)
                source_index.load_index(
                    os.path.join(persist_dir, segment_id),
                    is_persistent_index=True,
                    max_elements=len(id_to_label),
                )
                source_index.set_num_threads(num_threads)
                values = list(id_to_label.values())
                print_hnsw_details(hnsw_details)
                if not yes:
                    if not typer.confirm(
                        "\nAre you sure you want to rebuild this index?",
                        default=False,
                        show_default=True,
                    ):
                        console.print("[yellow]Rebuild cancelled by user[/yellow]")
                        return
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
                    task = progress.add_task(
                        "Adding items to target index...", total=len(values)
                    )
                    for i in range(0, len(values), batch_size):
                        items = source_index.get_items(ids=values[i : i + batch_size])
                        target_index.add_items(items, values[i : i + batch_size])
                        progress.update(task, advance=len(items))
                target_index.persist_dirty()
                target_index.close_file_handles()
                source_index.close_file_handles()
                if backup:
                    backup_target = os.path.join(
                        persist_dir,
                        f"{segment_id}_backup_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}",
                    )
                    shutil.move(os.path.join(persist_dir, segment_id), backup_target)
                    console.print(
                        f"[bold green]Backup of old index created at {backup_target}[/bold green]"
                    )
                else:
                    shutil.rmtree(os.path.join(persist_dir, segment_id))
                shutil.copytree(temp_persist_dir, os.path.join(persist_dir, segment_id))
            conn.commit()
            print_hnsw_details(
                _get_hnsw_details(
                    conn, persist_dir, collection_name, database, verbose=True
                )
            )
        except Exception:
            conn.rollback()
            console.print("[red]Failed to rebuild HNSW index[/red]")
            traceback.print_exc()
            raise


def info_hnsw(
    persist_dir: str,
    collection_name: str,
    database: Optional[str] = "default_database",
    verbose: Optional[bool] = False,
) -> HnswDetails:
    validate_chroma_persist_dir(persist_dir)
    console = Console()
    with get_sqlite_connection(persist_dir, SqliteMode.READ_ONLY) as conn:
        try:
            hnsw_details = _get_hnsw_details(
                conn, persist_dir, collection_name, database, verbose=verbose
            )
            print_hnsw_details(hnsw_details)
            return hnsw_details
        except Exception:
            console.print("[red]Failed to get HNSW details[/red]")
            traceback.print_exc()
            raise


def rebuild_hnsw_command(
    persist_dir: str = typer.Argument(..., help="The persist directory"),
    collection_name: str = typer.Option(
        ..., "--collection", "-c", help="The collection name"
    ),
    database: str = typer.Option(
        "default_database",
        "--database",
        "-d",
        help="The database name",
    ),
    backup: bool = typer.Option(
        True,
        "--backup",
        "-b",
        help="Backup the old index before rebuilding",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompt",
    ),
) -> None:
    rebuild_hnsw(
        persist_dir,
        collection_name,
        database,
        backup,
        yes,
    )


def info_hnsw_command(
    persist_dir: str = typer.Argument(..., help="The persist directory"),
    collection_name: str = typer.Option(
        ..., "--collection", "-c", help="The collection name"
    ),
    database: str = typer.Option(
        "default_database",
        "--database",
        "-d",
        help="The database name",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Verbose output",
    ),
) -> None:
    info_hnsw(persist_dir, collection_name, database, verbose)


hnsw_commands.command(
    name="rebuild",
    help="Rebuild the HNSW index",
    no_args_is_help=True,
)(rebuild_hnsw_command)

hnsw_commands.command(
    name="info",
    help="Info about the HNSW index",
    no_args_is_help=True,
)(info_hnsw_command)

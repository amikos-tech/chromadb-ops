import datetime
import json
import os
import shutil
import sqlite3
import tempfile
import traceback
from typing import Any, Callable, Dict, List, Optional, Tuple, TypedDict
import hnswlib
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table
from chroma_ops.utils import (
    DistanceMetric,
    SqliteMode,
    check_disk_space,
    get_sqlite_connection,
    validate_chroma_persist_dir,
    get_dir_size,
    PersistentData,
    sizeof_fmt,
)
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

hnsw_commands = typer.Typer(no_args_is_help=True)


class HnswDetails(TypedDict):
    collection_name: str
    database: str
    space: str
    dimensions: int
    construction_ef: int
    search_ef: int
    m: int
    num_threads: int
    resize_factor: float
    batch_size: int
    sync_threshold: int
    segment_id: str
    path: str
    has_metadata: bool
    num_elements: int
    id_to_label: Dict[str, int]
    collection_id: str
    index_size: int
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
        else DEFAULT_DISTANCE_METRIC
    )
    construction_ef = (
        config["hnsw:construction_ef"]
        if "hnsw:construction_ef" in config and config["hnsw:construction_ef"]
        else DEFAULT_CONSTRUCTION_EF
    )
    search_ef = (
        config["hnsw:search_ef"]
        if "hnsw:search_ef" in config and config["hnsw:search_ef"]
        else DEFAULT_SEARCH_EF
    )
    m = config["hnsw:M"] if "hnsw:M" in config and config["hnsw:M"] else DEFAULT_M
    num_threads = (
        config["hnsw:num_threads"]
        if "hnsw:num_threads" in config and config["hnsw:num_threads"]
        else DEFAULT_NUM_THREADS
    )
    resize_factor = (
        config["hnsw:resize_factor"]
        if "hnsw:resize_factor" in config and config["hnsw:resize_factor"]
        else DEFAULT_RESIZE_FACTOR
    )
    batch_size = (
        config["hnsw:batch_size"]
        if "hnsw:batch_size" in config and config["hnsw:batch_size"]
        else DEFAULT_BATCH_SIZE
    )
    sync_threshold = (
        config["hnsw:sync_threshold"]
        if "hnsw:sync_threshold" in config and config["hnsw:sync_threshold"]
        else DEFAULT_SYNC_THRESHOLD
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
            index.set_ef(search_ef)
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
        construction_ef=construction_ef,
        search_ef=search_ef,
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
        index_size=get_dir_size(os.path.join(persist_dir, segment_id[0])),
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
    table.add_row("EF Construction", str(hnsw_details["construction_ef"]))
    table.add_row("EF Search", str(hnsw_details["search_ef"]))
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
    table.add_row("Index size", sizeof_fmt(hnsw_details["index_size"]))
    table.add_row(
        "Fragmentation level",
        f"{hnsw_details['fragmentation_level']:.2f}% {'(estimated)' if hnsw_details['fragmentation_level_estimated'] else ''}",
    )
    console.print(table)


def _prepare_hnsw_segment_config_changes(
    segment_id: str,
    hnsw_details: HnswDetails,
    *,
    space: Optional[str] = None,
    construction_ef: Optional[int] = None,
    search_ef: Optional[int] = None,
    m: Optional[int] = None,
    num_threads: Optional[int] = None,
    resize_factor: Optional[float] = None,
    batch_size: Optional[int] = None,
    sync_threshold: Optional[int] = None,
) -> Tuple[
    List[Callable[[sqlite3.Connection], None]],
    Dict[str, Dict[str, Any]],
    HnswDetails,
]:
    """Prepare the HNSW segment config changes in `segment_metadata`"""
    changes_callbacks = []
    changes_diff: Dict[str, Dict[str, Any]] = {}
    final_changes: HnswDetails = hnsw_details.copy()
    if space and space != hnsw_details["space"]:
        changes_callbacks.append(
            lambda conn: conn.execute(
                "INSERT INTO segment_metadata (segment_id, key, str_value) VALUES (?, 'hnsw:space', ?) ON CONFLICT (segment_id, key) DO UPDATE SET str_value = ?",
                (segment_id, space, space),
            )
        )
        changes_diff["hnsw:space"] = {
            "old": hnsw_details["space"],
            "new": space,
        }
        final_changes["space"] = space
    if construction_ef and construction_ef != hnsw_details["construction_ef"]:
        changes_callbacks.append(
            lambda conn: conn.execute(
                "INSERT INTO segment_metadata (segment_id, key, int_value) VALUES (?, 'hnsw:construction_ef', ?) ON CONFLICT (segment_id, key) DO UPDATE SET int_value = ?",
                (segment_id, construction_ef, construction_ef),
            )
        )
        changes_diff["hnsw:construction_ef"] = {
            "old": hnsw_details["construction_ef"],
            "new": construction_ef,
        }
        final_changes["construction_ef"] = construction_ef
    if search_ef and search_ef != hnsw_details["search_ef"]:
        changes_callbacks.append(
            lambda conn: conn.execute(
                "INSERT INTO segment_metadata (segment_id, key, int_value) VALUES (?, 'hnsw:search_ef', ?) ON CONFLICT (segment_id, key) DO UPDATE SET int_value = ?",
                (segment_id, search_ef, search_ef),
            )
        )
        changes_diff["hnsw:search_ef"] = {
            "old": hnsw_details["search_ef"],
            "new": search_ef,
        }
        final_changes["search_ef"] = search_ef
    if m and m != hnsw_details["m"]:
        changes_callbacks.append(
            lambda conn: conn.execute(
                "INSERT INTO segment_metadata (segment_id, key, int_value) VALUES (?, 'hnsw:M', ?) ON CONFLICT (segment_id, key) DO UPDATE SET int_value = ?",
                (segment_id, m, m),
            )
        )
        changes_diff["hnsw:M"] = {
            "old": hnsw_details["m"],
            "new": m,
        }
        final_changes["m"] = m
    if num_threads and num_threads != hnsw_details["num_threads"]:
        changes_callbacks.append(
            lambda conn: conn.execute(
                "INSERT INTO segment_metadata (segment_id, key, int_value) VALUES (?, 'hnsw:num_threads', ?) ON CONFLICT (segment_id, key) DO UPDATE SET int_value = ?",
                (segment_id, num_threads, num_threads),
            )
        )
        changes_diff["hnsw:num_threads"] = {
            "old": hnsw_details["num_threads"],
            "new": num_threads,
        }
        final_changes["num_threads"] = num_threads
    if resize_factor and resize_factor != hnsw_details["resize_factor"]:
        changes_callbacks.append(
            lambda conn: conn.execute(
                "INSERT INTO segment_metadata (segment_id, key, float_value) VALUES (?, 'hnsw:resize_factor', ?) ON CONFLICT (segment_id, key) DO UPDATE SET float_value = ?",
                (segment_id, resize_factor, resize_factor),
            )
        )
        changes_diff["hnsw:resize_factor"] = {
            "old": hnsw_details["resize_factor"],
            "new": resize_factor,
        }
        final_changes["resize_factor"] = resize_factor
    if batch_size and batch_size != hnsw_details["batch_size"]:
        changes_callbacks.append(
            lambda conn: conn.execute(
                "INSERT INTO segment_metadata (segment_id, key, int_value) VALUES (?, 'hnsw:batch_size', ?) ON CONFLICT (segment_id, key) DO UPDATE SET int_value = ?",
                (segment_id, batch_size, batch_size),
            )
        )
        changes_diff["hnsw:batch_size"] = {
            "old": hnsw_details["batch_size"],
            "new": batch_size,
        }
        final_changes["batch_size"] = batch_size
    if sync_threshold and sync_threshold != hnsw_details["sync_threshold"]:
        changes_callbacks.append(
            lambda conn: conn.execute(
                "INSERT INTO segment_metadata (segment_id, key, int_value) VALUES (?, 'hnsw:sync_threshold', ?) ON CONFLICT (segment_id, key) DO UPDATE SET int_value = ?",
                (segment_id, sync_threshold, sync_threshold),
            )
        )
        changes_diff["hnsw:sync_threshold"] = {
            "old": hnsw_details["sync_threshold"],
            "new": sync_threshold,
        }
        final_changes["sync_threshold"] = sync_threshold
    return changes_callbacks, changes_diff, final_changes


def _print_hnsw_segment_config_changes(changes_diff: Dict[str, Dict[str, Any]]) -> None:
    console = Console()
    table = Table(title="HNSW segment config changes")
    table.add_column("Config Key", style="cyan")
    table.add_column("Old", style="green")
    table.add_column("New", style="red")
    for key, value in changes_diff.items():
        table.add_row(key, str(value["old"]), str(value["new"]))
    console.print(table)


def rebuild_hnsw(
    persist_dir: str,
    *,
    collection_name: str,
    database: Optional[str] = "default_database",
    backup: Optional[bool] = True,
    yes: Optional[bool] = False,
    space: Optional[str] = None,
    construction_ef: Optional[int] = None,
    search_ef: Optional[int] = None,
    m: Optional[int] = None,
    num_threads: Optional[int] = None,
    resize_factor: Optional[float] = None,
    batch_size: Optional[int] = None,
    sync_threshold: Optional[int] = None,
) -> None:
    """Rebuilds the HNSW index"""
    validate_chroma_persist_dir(persist_dir)
    console = Console()
    with get_sqlite_connection(persist_dir, SqliteMode.READ_WRITE) as conn:
        # lock the database to ensure no new data is added while we are rebuilding the index
        conn.execute("BEGIN EXCLUSIVE")
        try:
            hnsw_details = _get_hnsw_details(
                conn, persist_dir, collection_name, database
            )
            (
                changes_callbacks,
                changes_diff,
                final_changes,
            ) = _prepare_hnsw_segment_config_changes(
                hnsw_details["segment_id"],
                hnsw_details,
                space=space,
                construction_ef=construction_ef,
                search_ef=search_ef,
                m=m,
                num_threads=num_threads,
                resize_factor=resize_factor,
                batch_size=batch_size,
                sync_threshold=sync_threshold,
            )
            if not hnsw_details["has_metadata"] and len(changes_diff) == 0:
                console.print(
                    f"[red]Index metadata not found for segment {hnsw_details['segment_id']} and no config changes to make. No need to rebuild.[/red]"
                )
                return
            _space = final_changes["space"]
            construction_ef = final_changes["construction_ef"]
            search_ef = final_changes["search_ef"]
            _m = final_changes["m"]
            _num_threads = final_changes["num_threads"]
            _batch_size = final_changes["batch_size"]
            segment_id = final_changes["segment_id"]
            dimensions = final_changes["dimensions"]
            id_to_label = final_changes["id_to_label"]
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_persist_dir = os.path.join(temp_dir, segment_id)
                if not check_disk_space(
                    os.path.join(persist_dir, segment_id), temp_dir
                ):
                    console.print(
                        f"[red]Not enough space on in temp dir {temp_persist_dir} to copy index from {os.path.join(persist_dir, segment_id)}[/red]"
                    )
                    return
                shutil.copytree(os.path.join(persist_dir, segment_id), temp_persist_dir)
                target_index = hnswlib.Index(space=_space, dim=dimensions)
                target_index.init_index(
                    max_elements=len(id_to_label),
                    ef_construction=construction_ef,
                    M=_m,
                    is_persistent_index=True,
                    persistence_location=temp_persist_dir,
                )
                target_index.set_num_threads(_num_threads)
                target_index.set_ef(search_ef)
                source_index = hnswlib.Index(space=_space, dim=dimensions)
                source_index.load_index(
                    os.path.join(persist_dir, segment_id),
                    is_persistent_index=True,
                    max_elements=len(id_to_label),
                )
                source_index.set_num_threads(_num_threads)
                values = list(id_to_label.values())
                print_hnsw_details(final_changes)
                if len(changes_diff) > 0:
                    _print_hnsw_segment_config_changes(changes_diff)
                if not yes:
                    if not typer.confirm(
                        "\nAre you sure you want to rebuild this index?",
                        default=False,
                        show_default=True,
                    ):
                        console.print("[yellow]Rebuild cancelled by user[/yellow]")
                        return
                if len(changes_diff) > 0:
                    for callback in changes_callbacks:
                        callback(conn)
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
                    for i in range(0, len(values), _batch_size):
                        items = source_index.get_items(ids=values[i : i + _batch_size])
                        target_index.add_items(items, values[i : i + _batch_size])
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


def modify_runtime_config(
    persist_dir: str,
    collection_name: str,
    database: str,
    search_ef: Optional[int] = None,
    num_threads: Optional[int] = None,
    resize_factor: Optional[float] = None,
    batch_size: Optional[int] = None,
    sync_threshold: Optional[int] = None,
    yes: Optional[bool] = False,
) -> None:
    validate_chroma_persist_dir(persist_dir)
    console = Console()
    with get_sqlite_connection(persist_dir, SqliteMode.READ_WRITE) as conn:
        conn.execute("BEGIN EXCLUSIVE")
        try:
            hnsw_details = _get_hnsw_details(
                conn, persist_dir, collection_name, database
            )
            (
                changes_callbacks,
                changes_diff,
                _,
            ) = _prepare_hnsw_segment_config_changes(
                hnsw_details["segment_id"],
                hnsw_details,
                search_ef=search_ef,
                num_threads=num_threads,
                resize_factor=resize_factor,
                batch_size=batch_size,
                sync_threshold=sync_threshold,
            )
            if len(changes_diff) > 0:
                _print_hnsw_segment_config_changes(changes_diff)
            else:
                console.print(
                    "[bold green]No changes to apply (it is possible requested changes are identical to current config)[/bold green]"
                )
                return
            if not yes:
                if not typer.confirm(
                    "\nAre you sure you want to apply these changes?",
                    default=False,
                    show_default=True,
                ):
                    console.print("[yellow]Changes cancelled by user[/yellow]")
                    return
            for callback in changes_callbacks:
                callback(conn)
            conn.commit()
            console.print(
                "[bold green]HNSW index configuration modified successfully[/bold green]"
            )
        except Exception:
            conn.rollback()
            console.print("[red]Failed to modify HNSW index configuration[/red]")
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
    space: Optional[DistanceMetric] = typer.Option(
        None,
        "--space",
        help="The space to use for the index",
        case_sensitive=False,
    ),
    construction_ef: Optional[int] = typer.Option(
        None,
        "--construction-ef",
        help="The construction ef to use for the index",
        min=1,
    ),
    search_ef: Optional[int] = typer.Option(
        None,
        "--search-ef",
        help="The search ef to use for the index",
        min=1,
    ),
    m: Optional[int] = typer.Option(
        None,
        "--m",
        help="The m to use for the index",
        min=1,
    ),
    num_threads: Optional[int] = typer.Option(
        None,
        "--num-threads",
        help="The number of threads to use for the index",
        min=1,
    ),
    resize_factor: Optional[float] = typer.Option(
        None,
        "--resize-factor",
        help="The resize factor to use for the index",
        min=1.0,
    ),
    batch_size: Optional[int] = typer.Option(
        None,
        "--batch-size",
        help="The batch size to use for the index",
        min=2,
    ),
    sync_threshold: Optional[int] = typer.Option(
        None,
        "--sync-threshold",
        help="The sync threshold to use for the index",
        min=2,
    ),
) -> None:
    rebuild_hnsw(
        persist_dir,
        collection_name=collection_name,
        database=database,
        backup=backup,
        yes=yes,
        space=space.lower() if space else None,
        construction_ef=construction_ef,
        search_ef=search_ef,
        m=m,
        num_threads=num_threads,
        resize_factor=resize_factor,
        batch_size=batch_size,
        sync_threshold=sync_threshold,
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


def hnsw_modify_runtime_config_command(
    persist_dir: str = typer.Argument(..., help="The persist directory"),
    *,
    collection_name: str = typer.Option(
        ..., "--collection", "-c", help="The collection name"
    ),
    database: str = typer.Option(
        "default_database",
        "--database",
        "-d",
        help="The database name",
    ),
    search_ef: Optional[int] = typer.Option(
        None,
        "--search-ef",
        help="The search ef to use for the index",
        min=1,
    ),
    num_threads: Optional[int] = typer.Option(
        None,
        "--num-threads",
        help="The number of threads to use for the index",
        min=1,
    ),
    resize_factor: Optional[float] = typer.Option(
        None,
        "--resize-factor",
        help="The resize factor to use for the index",
        min=1.0,
    ),
    batch_size: Optional[int] = typer.Option(
        None,
        "--batch-size",
        help="The batch size to use for the index",
        min=2,
    ),
    sync_threshold: Optional[int] = typer.Option(
        None,
        "--sync-threshold",
        help="The sync threshold to use for the index",
        min=2,
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompt",
    ),
) -> None:
    modify_runtime_config(
        persist_dir,
        collection_name,
        database,
        search_ef=search_ef,
        num_threads=num_threads,
        resize_factor=resize_factor,
        batch_size=batch_size,
        sync_threshold=sync_threshold,
        yes=yes,
    )


hnsw_commands.command(
    name="rebuild",
    help="Rebuild the HNSW index and update HNSW index configuration",
    no_args_is_help=True,
)(rebuild_hnsw_command)

hnsw_commands.command(
    name="info",
    help="Info about the HNSW index",
    no_args_is_help=True,
)(info_hnsw_command)

hnsw_commands.command(
    name="config",
    help="Modify the HNSW index configuration. This is a soft change that updates index configuration without rebuilding the index. The config changes are related to ",
    no_args_is_help=True,
)(hnsw_modify_runtime_config_command)

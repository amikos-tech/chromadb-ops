import argparse
import datetime
import json
import os
import shutil
import sqlite3
import tempfile
import traceback
from typing import Any, Dict, Optional
import numpy as np
import hnswlib
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.rule import Rule
from rich.table import Table
from chroma_ops.utils import (
    validate_chroma_persist_dir,
    get_dir_size,
    PersistentData,
    sizeof_fmt,
)
hnsw_commands = typer.Typer()



def _get_hnsw_details(conn: sqlite3.Connection, persist_dir: str, collection_name: str, database: Optional[str] = "default_database") -> None:
    collection_details = conn.execute("SELECT id,config_json_str,dimension FROM collections WHERE name = ?", (collection_name,)).fetchone()
    config = json.loads(collection_details[1])
    space = config["hnsw_configuration"]["space"]
    ef_construction = config["hnsw_configuration"]["ef_construction"]
    ef_search = config["hnsw_configuration"]["ef_search"]
    m = config["hnsw_configuration"]["M"]
    num_threads = config["hnsw_configuration"]["num_threads"]
    resize_factor = config["hnsw_configuration"]["resize_factor"]
    batch_size = config["hnsw_configuration"]["batch_size"]
    sync_threshold = config["hnsw_configuration"]["sync_threshold"]
    segment_id = conn.execute("SELECT id FROM segments WHERE scope = 'VECTOR' AND collection = ?", (collection_details[0],)).fetchone()
    id_to_label = {}
    if os.path.exists(os.path.join(persist_dir, segment_id[0],"index_metadata.pickle")):
        has_metadata = True
        persistent_data = PersistentData.load_from_file(os.path.join(persist_dir, segment_id[0], "index_metadata.pickle"))
        id_to_label = persistent_data.id_to_label
    else:
        has_metadata = False

    return {
        "collection_name": collection_name,
        "database": database,
        "space": space,
        "dimensions": collection_details[2],
        "ef_construction": ef_construction,
        "ef_search": ef_search,
        "m": m,
        "num_threads": num_threads,
        "resize_factor": resize_factor,
        "batch_size": batch_size,
        "sync_threshold": sync_threshold,
        "segment_id": segment_id[0],
        "path": os.path.join(persist_dir, segment_id[0]),
        "has_metadata": has_metadata,
        "num_elements": len(id_to_label),
        "id_to_label": id_to_label,
        "collection_id": collection_details[0],
        "index_size": sizeof_fmt(get_dir_size(os.path.join(persist_dir, segment_id[0])),)
    }

def print_hnsw_details(hnsw_details: Dict[str, Any]) -> None:
    console = Console()
    table = Table(title=f"HNSW details for collection [red]{hnsw_details['collection_name']}[/red] in [red]{hnsw_details['database']}[/red] database")
    
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    
    # Add rows for each detail
    table.add_row("Space", str(hnsw_details['space']))
    table.add_row("Dimensions", str(hnsw_details['dimensions']))
    table.add_row("EF Construction", str(hnsw_details['ef_construction']))
    table.add_row("EF Search", str(hnsw_details['ef_search']))
    table.add_row("M", str(hnsw_details['m']))
    table.add_row("Number of threads", str(hnsw_details['num_threads']))
    table.add_row("Resize factor", str(hnsw_details['resize_factor']))
    table.add_row("Batch size", str(hnsw_details['batch_size']))
    table.add_row("Sync threshold", str(hnsw_details['sync_threshold']))
    table.add_row("Segment ID", hnsw_details['segment_id'])
    table.add_row("Path", hnsw_details['path'])
    table.add_row("Has metadata", str(hnsw_details['has_metadata']))
    table.add_row("Number of elements", str(hnsw_details['num_elements']))
    table.add_row("Collection ID", str(hnsw_details['collection_id']))
    table.add_row("Index size", hnsw_details['index_size'])
    
    console.print(table)

def rebuild_hnsw(persist_dir: str, collection_name: str, database: Optional[str] = "default_database", backup: Optional[bool] = True, yes: Optional[bool] = False) -> None:
    """Rebuilds the HNSW index in-place"""
    validate_chroma_persist_dir(persist_dir)
    console = Console()
    sql_file = os.path.join(persist_dir, "chroma.sqlite3")
    conn = sqlite3.connect(f"file:{sql_file}?mode=rw", uri=True)
    # lock the database to ensure no new data is added while we are rebuilding the index
    conn.execute("BEGIN EXCLUSIVE")
    try:
        hnsw_details = _get_hnsw_details(conn, persist_dir, collection_name, database)
        if not hnsw_details["has_metadata"]:
            console.print(f"[red]Index metadata not found for segment {hnsw_details['segment_id']}. No need to rebuild.[/red]")
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
            source_index.load_index(os.path.join(persist_dir, segment_id), is_persistent_index=True, max_elements=len(id_to_label))
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
                SpinnerColumn(finished_text="[bold green]:heavy_check_mark:[/bold green]"),
                TextColumn("[progress.description]{task.description}"),
                *[BarColumn(), TextColumn("{task.percentage:>3.0f}%")],  # Add these columns
                transient=True,
            ) as progress:
                task = progress.add_task("Adding items to target index...", total=len(values))
                for i in range(0, len(values), batch_size):
                    items = source_index.get_items(ids=values[i:i+batch_size])
                    target_index.add_items(items, values[i:i+batch_size])
                    progress.update(task, advance=len(items))
            target_index.persist_dirty()
            target_index.close_file_handles()
            source_index.close_file_handles()
            if backup:
                backup_target = os.path.join(persist_dir, f"{segment_id}_backup_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}")
                shutil.move(os.path.join(persist_dir, segment_id), backup_target)
                console.print(f"[bold green]Backup of old index created at {backup_target}[/bold green]")
            else:
                shutil.rmtree(os.path.join(persist_dir, segment_id))
            shutil.copytree(temp_persist_dir, os.path.join(persist_dir, segment_id))
        conn.commit()
        print_hnsw_details(_get_hnsw_details(conn, persist_dir, collection_name, database))
    except Exception:
        conn.rollback()
        console.print("[red]Failed to rebuild HNSW index[/red]")
        traceback.print_exc()
        raise

def info_hnsw(persist_dir: str, collection_name: str, database: Optional[str] = "default_database") -> None:
    validate_chroma_persist_dir(persist_dir)
    sql_file = os.path.join(persist_dir, "chroma.sqlite3")
    conn = sqlite3.connect(f"file:{sql_file}?mode=rw", uri=True)
    print_hnsw_details(_get_hnsw_details(conn, persist_dir, collection_name, database))

def rebuild_hnsw_command(
    persist_dir: str = typer.Argument(..., help="The persist directory"),
    collection_name: str = typer.Option(..., "--collection", "-c", help="The collection name"),
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
    collection_name: str = typer.Option(..., "--collection", "-c", help="The collection name"),
    database: str = typer.Option(
        "default_database",
        "--database",
        "-d",
        help="The database name",
    ),
) -> None:
    info_hnsw(persist_dir, collection_name, database)

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

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='hnsw', help='Available commands')
    
    # Setup command groups
    rebuild = subparsers.add_parser('rebuild', help='Rebuild the HNSW index')
    rebuild.add_argument("persist_dir", type=str)
    rebuild.add_argument("collection_name", type=str)
    rebuild.add_argument("-d", "--database", type=str, default="default_database")
    rebuild.set_defaults(func=rebuild_hnsw_command)
    args = parser.parse_args()
    if hasattr(args, 'func'):
        args.func(args)
    

import os
import shutil
from typing import Optional

from rich.console import Console
from rich.table import Table
import typer
from chroma_ops.utils import (
    SqliteMode,
    get_sqlite_connection,
    validate_chroma_persist_dir,
)


def clean(persist_dir: str, yes: Optional[bool] = False) -> None:
    validate_chroma_persist_dir(persist_dir)
    with get_sqlite_connection(persist_dir, SqliteMode.READ_ONLY) as conn:
        console = Console()
        cursor = conn.cursor()
        console.print("Cleaning up orphanated segment dirs...")
        query = "SELECT id FROM segments WHERE scope = 'VECTOR';"
        cursor.execute(query)
        results = cursor.fetchall()
        active_segments = []
        for result in results:
            active_segments.append(result[0])
        cursor.close()
        conn.commit()
        # list dirs in persist_dir
        dirs_to_delete = []
        console.print()
        table = Table(title="Orphanated HNSW segment dirs")
        table.add_column("Segment ID", style="cyan")
        table.add_column("Path", style="green")
        for dir in os.listdir(persist_dir):
            if (
                os.path.isdir(os.path.join(persist_dir, dir))
                and dir not in active_segments
                and os.path.exists(os.path.join(persist_dir, dir, "header.bin"))
            ):
                dirs_to_delete.append(dir)
                table.add_row(dir, os.path.join(persist_dir, dir))
        if len(dirs_to_delete) == 0:
            console.print("[green]No orphanated segment dirs found[/green]")
            return
        console.print(table)
        if not yes:
            if not typer.confirm(
                "\nAre you sure you want to delete these segment dirs?",
                default=False,
                show_default=True,
            ):
                console.print("[yellow]Deletion cancelled by user[/yellow]")
                return
        for dir in dirs_to_delete:
            console.print(f"Deleting orphanated segment dir: {dir}")
            shutil.rmtree(os.path.join(persist_dir, dir))
        console.print("[green]Done[/green]")


def command(
    persist_dir: str = typer.Argument(..., help="The persist directory"),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompt",
    ),
) -> None:
    clean(persist_dir, yes)

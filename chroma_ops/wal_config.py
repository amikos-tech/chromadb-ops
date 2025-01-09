from enum import Enum
import json
import sqlite3
from typing import Optional
import typer

from chroma_ops.utils import (
    SqliteMode,
    get_sqlite_connection,
    validate_chroma_persist_dir,
)
from rich.console import Console
from rich.table import Table


class PurgeFlag(str, Enum):
    OFF = "off"
    AUTO = "auto"


def config_wal(
    persist_dir: str, *, purge: Optional[PurgeFlag] = None, yes: Optional[bool] = False
) -> None:
    validate_chroma_persist_dir(persist_dir)
    console = Console()
    with get_sqlite_connection(persist_dir, SqliteMode.READ_WRITE) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """SELECT name
            FROM sqlite_master
            WHERE type='table' AND name='embeddings_queue_config';"""
            )
            cursor.fetchone()
        except sqlite3.OperationalError:
            console.print(
                "[red]WAL config table not found. Likely unsupported version of Chroma.[/red]"
            )
            return
        try:
            current_config = cursor.execute(
                """SELECT config_json_str FROM embeddings_queue_config"""
            ).fetchone()
            current_config = json.loads(current_config[0])
            del current_config["_type"]
            table = Table(title="Current WAL config")
            table.add_column("Config key", style="cyan")
            table.add_column("Config Change", style="green")

            if purge is not None:
                if (
                    purge == PurgeFlag.OFF
                    and current_config["automatically_purge"] is False
                ):
                    console.print(
                        "[bold green]WAL config is already set to the desired state (auto purge disabled).[/bold green]"
                    )
                    return
                elif (
                    purge == PurgeFlag.AUTO
                    and current_config["automatically_purge"] is True
                ):
                    console.print(
                        "[bold green]WAL config is already set to the desired state (auto purge enabled).[/bold green]"
                    )
                    return
                table.add_row(
                    "Automatically purge (automatically_purge)",
                    f"{str(current_config['automatically_purge'])} (old) -> [red]{'True' if purge == PurgeFlag.AUTO else 'False'} (new)[/red]",
                )
            else:
                table.add_row(
                    "Automatically purge (automatically_purge)",
                    f"{str(current_config['automatically_purge'])}",
                )
            console.print(table)

            if not yes:
                if not typer.confirm(
                    "\nAre you sure you want to update the WAL config?",
                    default=False,
                    show_default=True,
                ):
                    console.print("[yellow]Rebuild cancelled by user[/yellow]")
                    return
            cursor.execute("BEGIN EXCLUSIVE")
            if purge is not None:
                if purge == PurgeFlag.OFF:
                    cursor.execute(
                        """UPDATE embeddings_queue_config
                    SET config_json_str = JSON_SET(config_json_str, '$.automatically_purge', json('false'))"""
                    )
                elif purge == PurgeFlag.AUTO:
                    cursor.execute(
                        """UPDATE embeddings_queue_config
                    SET config_json_str = JSON_SET(config_json_str, '$.automatically_purge', json('true'))"""
                    )
            conn.commit()
            console.print("[bold green]WAL config updated successfully![/bold green]")
        except sqlite3.OperationalError as e:
            console.print(f"[red]Failed to update WAL config: {e}[/red]")
            conn.rollback()


def command(
    persist_dir: str = typer.Argument(..., help="The persist directory"),
    purge: PurgeFlag = typer.Option(
        PurgeFlag.AUTO,
        "--purge",
        help="Configure the purge behaviour for the WAL. Available options are: off - inifinite WAL, auto - purge WAL after adding a batch.",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompt",
    ),
) -> None:
    config_wal(persist_dir, purge=purge, yes=yes)

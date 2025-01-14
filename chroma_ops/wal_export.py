import base64
import json
import sys
from contextlib import contextmanager
from typing import Optional, Generator, IO, Union, Any, TextIO

import typer

from chroma_ops.constants import DEFAULT_TENANT_ID, DEFAULT_TOPIC_NAMESPACE
from chroma_ops.utils import (
    SqliteMode,
    get_sqlite_connection,
    validate_chroma_persist_dir,
)

from rich.console import Console
from rich.table import Table


@contextmanager
def smart_open(
    filename: Optional[str] = None,
) -> Generator[Union[IO[Any], TextIO], None, None]:
    fh: Union[IO[Any], TextIO] = sys.stdout
    if filename:
        fh = open(filename, "w")

    try:
        yield fh
    finally:
        if filename:
            fh.close()


def export_wal(
    persist_dir: str,
    output_file: str,
    *,
    tenant: Optional[str] = DEFAULT_TENANT_ID,
    topic_namespace: Optional[str] = DEFAULT_TOPIC_NAMESPACE,
    yes: Optional[bool] = False,
) -> None:
    validate_chroma_persist_dir(persist_dir)
    console = Console(stderr=True)
    table = Table(title="Exporting WAL")
    table.add_column("Collection", style="cyan")
    table.add_column("WAL Entries", style="magenta")
    with get_sqlite_connection(persist_dir, SqliteMode.READ_ONLY) as conn:
        collections = conn.execute(
            "SELECT c.name,c.id, s.id FROM collections c left join segments s on c.id=s.collection where s.scope='VECTOR'"
        ).fetchall()
        wal_topic_groups = conn.execute(
            "SELECT topic, count(*) FROM embeddings_queue group by topic"
        ).fetchall()
        for collection in collections:
            topic = f"persistent://{tenant}/{topic_namespace}/{collection[1]}"
            table.add_row(
                collection[0],
                str([s[1] for s in wal_topic_groups if s[0] == topic][0]),
            )
        console.print(table)
        if not yes:
            console.print("Are you sure you want to export the WAL? (y/N)")
            if not typer.confirm(
                "\nAre you sure you want to export the WAL?",
                default=False,
                show_default=True,
            ):
                console.print("[yellow]WAL export cancelled by user[/yellow]")
                return
        cursor = conn.cursor()
        query = "SELECT * FROM embeddings_queue ORDER BY seq_id ASC;"
        cursor.execute(query)
        exported_rows = 0
        with smart_open(output_file) as json_file:
            column_names = [description[0] for description in cursor.description]
            for row in cursor:
                row_data = {}
                for i, column_name in enumerate(column_names):
                    if column_name == "vector":
                        row_data[column_name] = base64.b64encode(row[i]).decode()
                    else:
                        row_data[column_name] = row[i]
                json_file.write(json.dumps(row_data) + "\n")
                exported_rows += 1

    console.print(f"[green]Exported {exported_rows} rows[/green]")


def command(
    persist_dir: str = typer.Argument(..., help="The persist directory"),
    out: str = typer.Option(None, "--out", "-o", help="The output jsonl file"),
    yes: Optional[bool] = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    export_wal(persist_dir, out, yes=yes)

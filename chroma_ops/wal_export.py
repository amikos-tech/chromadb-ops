import base64
import json
import sys
from contextlib import contextmanager
from typing import Optional, Generator, IO, Union, Any, TextIO

import typer

from chroma_ops.utils import (
    SqliteMode,
    get_sqlite_connection,
    validate_chroma_persist_dir,
)


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


def export_wal(persist_dir: str, output_file: str) -> None:
    validate_chroma_persist_dir(persist_dir)
    with get_sqlite_connection(persist_dir, SqliteMode.READ_ONLY) as conn:
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

    typer.echo(f"Exported {exported_rows} rows", file=sys.stderr)


def command(
    persist_dir: str = typer.Argument(..., help="The persist directory"),
    out: str = typer.Option(None, "--out", "-o", help="The output jsonl file"),
) -> None:
    export_wal(persist_dir, out)

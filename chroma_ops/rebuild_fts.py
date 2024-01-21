import argparse
import os
import sqlite3
import sys

import chromadb
import typer

from chroma_ops.utils import validate_chroma_persist_dir, read_script


def rebuild_fts(persist_dir: str) -> None:
    validate_chroma_persist_dir(persist_dir)
    sql_file = os.path.join(persist_dir, "chroma.sqlite3")
    conn = sqlite3.connect(sql_file)
    cursor = conn.cursor()
    script = read_script("scripts/drop_fts.sql")
    cursor.executescript(script)
    cursor.close()
    conn.close()
    typer.echo("Dropped FTS. Will try to start your Chroma now.", file=sys.stderr)
    typer.echo(
        "NOTE: Depending on the size of your documents in Chroma it may take a while for Chroma to start up again.",
        file=sys.stderr,
        color=typer.colors.YELLOW,
    )
    try:
        chromadb.PersistentClient(path=persist_dir)
        typer.echo("Chroma started successfully.", file=sys.stderr)
    except Exception as e:
        typer.echo(
            f"Chroma failed to start. Error: {repr(e)}",
            file=sys.stderr,
            color=typer.colors.RED,
            err=True,
        )


def command(
    persist_dir: str = typer.Argument(..., help="The persist directory"),
) -> None:
    rebuild_fts(persist_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("persist_dir", type=str)
    arg = parser.parse_args()
    rebuild_fts(arg.persist_dir)

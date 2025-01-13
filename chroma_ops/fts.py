import sys

import chromadb
import typer

from chroma_ops.constants import DEFAULT_TOKENIZER
from chroma_ops.utils import (
    SqliteMode,
    get_sqlite_connection,
    validate_chroma_persist_dir,
    read_script,
)


fts_commands = typer.Typer(no_args_is_help=True)


def validate_tokenizer(tokenizer: str) -> None:
    valid_tokenizers = ["trigram", "unicode61", "ascii", "porter"]
    if (
        not tokenizer.startswith("trigram")
        and not tokenizer.startswith("unicode61")
        and not tokenizer.startswith("ascii")
        and not tokenizer.startswith("porter")
    ):
        raise ValueError(
            f"Invalid tokenizer. Must be one of: {', '.join(valid_tokenizers)}. See https://www.sqlite.org/fts5.html#tokenizers"
        )


def rebuild_fts(persist_dir: str, tokenizer: str = DEFAULT_TOKENIZER) -> None:
    validate_chroma_persist_dir(persist_dir)
    validate_tokenizer(tokenizer)
    with get_sqlite_connection(persist_dir, SqliteMode.READ_WRITE) as conn:
        cursor = conn.cursor()
        script = read_script("scripts/drop_fts.sql")
        script = script.replace("__TOKENIZER__", tokenizer)
        cursor.executescript(script)
        cursor.close()
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


def rebuild_command(
    persist_dir: str = typer.Argument(..., help="The persist directory"),
    tokenizer: str = typer.Option(
        DEFAULT_TOKENIZER,
        "--tokenizer",
        "-t",
        help="The tokenizer to use for the FTS index. Supported values: 'trigram', 'unicode61', 'ascii', 'porter'. See https://www.sqlite.org/fts5.html#tokenizers",
    ),
) -> None:
    rebuild_fts(persist_dir, tokenizer)


fts_commands.command(
    name="rebuild", help="Rebuilds Full Text Search index.", no_args_is_help=True
)(rebuild_command)

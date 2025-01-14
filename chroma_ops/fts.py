from typing import Optional

import chromadb
import typer

from chroma_ops.constants import DEFAULT_TOKENIZER
from chroma_ops.utils import (
    SqliteMode,
    get_sqlite_connection,
    validate_chroma_persist_dir,
    read_script,
)

from rich.console import Console


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


def rebuild_fts(
    persist_dir: str,
    tokenizer: str = DEFAULT_TOKENIZER,
    yes: Optional[bool] = False,
) -> None:
    validate_chroma_persist_dir(persist_dir)
    validate_tokenizer(tokenizer)
    console = Console()
    if not yes:
        if not typer.confirm(
            f"\nAre you sure you want to rebuild the FTS index in {persist_dir}? This action will drop the existing FTS index and create a new one.",
            default=False,
            show_default=True,
        ):
            console.print("[yellow]Rebuild FTS cancelled by user[/yellow]")
            return
    with get_sqlite_connection(persist_dir, SqliteMode.READ_WRITE) as conn:
        cursor = conn.cursor()
        script = read_script("scripts/drop_fts.sql")
        script = script.replace("__TOKENIZER__", tokenizer)
        cursor.executescript(script)
        cursor.close()
        console.print("Rebuilt FTS. Will try to start your Chroma now.")
        console.print(
            "NOTE: Depending on the size of your documents in Chroma it may take a while for Chroma to start up again.",
        )
        try:
            chromadb.PersistentClient(path=persist_dir)
            console.print("[green]Chroma started successfully. FTS rebuilt.[/green]")
        except Exception as e:
            console.print(f"[red]Chroma failed to start. Error: {repr(e)}[/red]")
            raise e


def rebuild_command(
    persist_dir: str = typer.Argument(..., help="The persist directory"),
    tokenizer: str = typer.Option(
        DEFAULT_TOKENIZER,
        "--tokenizer",
        "-t",
        help="The tokenizer to use for the FTS index. Supported values: 'trigram', 'unicode61', 'ascii', 'porter'. See https://www.sqlite.org/fts5.html#tokenizers",
    ),
    yes: Optional[bool] = typer.Option(
        False, "--yes", "-y", help="Skip confirmation prompt"
    ),
) -> None:
    rebuild_fts(persist_dir, tokenizer, yes=yes)


fts_commands.command(
    name="rebuild", help="Rebuilds Full Text Search index.", no_args_is_help=True
)(rebuild_command)

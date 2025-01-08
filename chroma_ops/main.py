import typer

from chroma_ops.fts import fts_commands
from chroma_ops.wal_commit import command as commit_wal_command
from chroma_ops.wal_clean import command as clean_wal_command
from chroma_ops.wal_export import command as export_wal_command
from chroma_ops.info import command as info_command
from chroma_ops.clean import command as clean_command
from chroma_ops.hnsw import hnsw_commands

app = typer.Typer(no_args_is_help=True, help="ChromaDB Ops Commands.")

app.command(
    name="commit-wal", help="Commit WAL to HNSW lib binary index", no_args_is_help=True
)(commit_wal_command)

app.command(
    name="clean-wal",
    help="Cleans up WAL and VACUUM the SQLite DB.",
    no_args_is_help=True,
)(clean_wal_command)
app.command(
    name="export-wal", help="Exports the WAL to a jsonl file.", no_args_is_help=True
)(export_wal_command)

app.command(
    name="info",
    help="Provide persistent Chroma DB information. "
    "Useful to understand how your Chroma works or get support from the team.",
    no_args_is_help=True,
)(info_command)

app.command(
    name="clean",
    help="Clean up orphaned vector segment directories.",
    no_args_is_help=True,
)(clean_command)

app.add_typer(hnsw_commands, name="hnsw", help="HNSW index maintenance commands")
app.add_typer(fts_commands, name="fts", help="Full Text Search index maintenance commands")

if __name__ == "__main__":
    app()

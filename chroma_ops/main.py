import typer

from chroma_ops.rebuild_fts import rebuild_fts
from chroma_ops.wal_commit import command as commit_wal_command
from chroma_ops.wal_clean import command as clean_wal_command
from chroma_ops.wal_export import command as export_wal_command

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
    name="rebuild-fts", help="Rebuilds Full Text Search index.", no_args_is_help=True
)(rebuild_fts)
if __name__ == "__main__":
    app()

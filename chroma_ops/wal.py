import typer
from chroma_ops.wal_export import command as export_command
from chroma_ops.wal_commit import command as commit_command
from chroma_ops.wal_clean import command as clean_command

wal_commands = typer.Typer(no_args_is_help=True)

wal_commands.command(
    name="export", no_args_is_help=True, help="Exports the WAL to a jsonl file."
)(export_command)
wal_commands.command(
    name="commit", no_args_is_help=True, help="Commit WAL to HNSW lib binary index."
)(commit_command)
wal_commands.command(
    name="clean", no_args_is_help=True, help="Cleans up WAL and VACUUM the SQLite DB."
)(clean_command)

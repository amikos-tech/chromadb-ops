import typer
from chroma_ops.collection_snapshot import command as snapshot_command

collection_commands = typer.Typer(no_args_is_help=True)

collection_commands.command(
    name="snapshot", no_args_is_help=True, help="Snapshot a collection to a file."
)(snapshot_command)

import typer

from chroma_ops.db_info import command as db_info_command
from chroma_ops.db_clean import command as db_clean_command

db_commands = typer.Typer(no_args_is_help=True)

db_commands.command(
    name="info",
    help="Provide persistent Chroma DB information. "
    "Useful to understand how your Chroma works or get support from the team.",
    no_args_is_help=True,
)(db_info_command)

db_commands.command(
    name="clean",
    help="Clean up orphanated HNSW segment subdirectories.",
    no_args_is_help=True,
)(db_clean_command)

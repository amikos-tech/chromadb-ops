import typer

from chroma_ops.db_info import command as db_info_command

db_commands = typer.Typer(no_args_is_help=True)

db_commands.command(
    name="info",
    help="Provide persistent Chroma DB information. "
    "Useful to understand how your Chroma works or get support from the team.",
    no_args_is_help=True,
)(db_info_command)

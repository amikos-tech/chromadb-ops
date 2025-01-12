import typer

from chroma_ops.fts import fts_commands
from chroma_ops.wal import wal_commands
from chroma_ops.info import command as info_command
from chroma_ops.clean import command as clean_command
from chroma_ops.hnsw import hnsw_commands
from chroma_ops.collection import collection_commands

app = typer.Typer(no_args_is_help=True, help="ChromaDB Ops Commands.")


app.add_typer(wal_commands, name="wal", help="WAL maintenance commands")

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
app.add_typer(
    fts_commands, name="fts", help="Full Text Search index maintenance commands"
)

app.add_typer(
    collection_commands, name="collection", help="Collection maintenance commands"
)

if __name__ == "__main__":
    app()

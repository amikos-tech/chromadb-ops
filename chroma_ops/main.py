import typer

from chroma_ops.fts import fts_commands
from chroma_ops.wal import wal_commands
from chroma_ops.db import db_commands
from chroma_ops.hnsw import hnsw_commands
from chroma_ops.collection import collection_commands

app = typer.Typer(no_args_is_help=True, help="ChromaDB Ops Commands.")


app.add_typer(wal_commands, name="wal", help="WAL maintenance commands")


app.add_typer(db_commands, name="db", help="DB maintenance commands")

app.add_typer(hnsw_commands, name="hnsw", help="HNSW index maintenance commands")
app.add_typer(
    fts_commands, name="fts", help="Full Text Search index maintenance commands"
)

app.add_typer(
    collection_commands, name="collection", help="Collection maintenance commands"
)

if __name__ == "__main__":
    app()

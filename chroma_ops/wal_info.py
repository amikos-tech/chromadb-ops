from typing import List, Tuple
import typer
import chromadb
from chroma_ops.constants import DEFAULT_TENANT_ID, DEFAULT_TOPIC_NAMESPACE
from chroma_ops.utils import (
    SqliteMode,
    get_sqlite_connection,
    list_collections,
    validate_chroma_persist_dir,
)
from rich.console import Console
from rich.table import Table


def info_wal(persist_dir: str) -> List[Tuple[str, str, int]]:
    validate_chroma_persist_dir(persist_dir)
    console = Console()
    with get_sqlite_connection(persist_dir, SqliteMode.READ_ONLY) as conn:
        client = chromadb.PersistentClient(path=persist_dir)
        cursor = conn.cursor()
        all_collections = list_collections(client)
        collection_topics = {}
        stats = []
        for col in all_collections:
            collection_topics[
                f"persistent://{DEFAULT_TENANT_ID}/{DEFAULT_TOPIC_NAMESPACE}/{col.id}"
            ] = col.name
        query = "SELECT topic, COUNT(*) FROM embeddings_queue GROUP BY topic ORDER BY seq_id ASC;"
        res = cursor.execute(query).fetchall()
        table = Table(title="WAL Info")
        table.add_column("Collection")
        table.add_column("Topic")
        table.add_column("Count")
        for row in res:
            table.add_row(collection_topics[str(row[0])], str(row[0]), str(row[1]))
            stats.append((collection_topics[str(row[0])], str(row[0]), row[1]))
        console.print(table)
        return stats


def command(
    persist_dir: str = typer.Argument(..., help="The persist directory"),
) -> None:
    info_wal(persist_dir)

import os
import shutil
import sys

import typer
from chroma_ops.utils import (
    SqliteMode,
    get_sqlite_connection,
    validate_chroma_persist_dir,
)


def clean(persist_dir: str) -> None:
    validate_chroma_persist_dir(persist_dir)
    with get_sqlite_connection(persist_dir, SqliteMode.READ_ONLY) as conn:
        cursor = conn.cursor()
        print("Cleaning up orphanated segment dirs...", file=sys.stderr)
        query = "SELECT id FROM segments WHERE scope = 'VECTOR';"
        cursor.execute(query)
        results = cursor.fetchall()
        active_segments = []
        for result in results:
            active_segments.append(result[0])
        cursor.close()
        conn.commit()
        # list dirs in persist_dir
        for dir in os.listdir(persist_dir):
            if (
                os.path.isdir(os.path.join(persist_dir, dir))
                and dir not in active_segments
                and os.path.exists(os.path.join(persist_dir, dir, "header.bin"))
            ):
                print(f"Deleting orphanated segment dir: {dir}", file=sys.stderr)
                shutil.rmtree(os.path.join(persist_dir, dir))


def command(
    persist_dir: str = typer.Argument(..., help="The persist directory"),
) -> None:
    clean(persist_dir)

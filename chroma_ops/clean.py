import argparse
import os
import shutil
import sqlite3
import sys
import uuid

import typer
from chroma_ops.utils import validate_chroma_persist_dir


def clean(persist_dir: str):
    validate_chroma_persist_dir(persist_dir)
    sql_file = os.path.join(persist_dir, "chroma.sqlite3")
    conn = sqlite3.connect(f"file:{sql_file}?mode=ro", uri=True)
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
    conn.close()
    # list dirs in persist_dir
    for dir in os.listdir(persist_dir):
        if os.path.isdir(os.path.join(persist_dir, dir)) and dir not in active_segments and os.path.exists(os.path.join(persist_dir, dir, "header.bin")):
            print(f"Deleting orphanated segment dir: {dir}", file=sys.stderr)
            shutil.rmtree(os.path.join(persist_dir, dir))


def command(
    persist_dir: str = typer.Argument(..., help="The persist directory"),
) -> None:
    clean(persist_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("persist_dir", type=str, help="The persist directory")
    arg = parser.parse_args()
    clean(arg.persist_dir)

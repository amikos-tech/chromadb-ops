#!/usr/bin/env python3
import argparse
import os

import chromadb
import typer

from chromadb.segment.impl.vector.local_persistent_hnsw import PersistentData
from chromadb.segment import VectorReader
from chromadb.types import SegmentScope, Operation

from chroma_ops.utils import validate_chroma_persist_dir


def commit_wal(persist_dir: str):
    """Note this uses internal ChromaDB APIs which may change at any moment."""

    validate_chroma_persist_dir(persist_dir)
    client = chromadb.PersistentClient(path=persist_dir)
    vector_segments = [
        s
        for s in client._server._sysdb.get_segments()
        if s["scope"] == SegmentScope.VECTOR
    ]
    for s in vector_segments:
        col = client._server._get_collection(
            s["collection"]
        )  # load the collection and apply WAL
        client._server._manager.hint_use_collection(
            s["collection"], Operation.ADD
        )  # Add hint to load the index into memory
        segment = client._server._manager.get_segment(
            s["collection"], VectorReader
        )  # Get the segment instance
        segment._apply_batch(segment._curr_batch)  # Apply the current WAL batch

        segment._persist()  # persist the index
        metadata = PersistentData.load_from_file(
            os.path.join(persist_dir, str(s["id"]), "index_metadata.pickle")
        )  # load the metadata after persisting
        print(
            f"Processing index for collection {col['name']} ({s['id']}) - "
            f"total vectors in index {len(segment._index.get_ids_list())}"
        )
        segment.close_persistent_index()


def command(
        persist_dir: str = typer.Argument(..., help="The persist directory"),
):
    commit_wal(persist_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("persist_dir", type=str)
    arg = parser.parse_args()
    commit_wal(arg.persist_dir)

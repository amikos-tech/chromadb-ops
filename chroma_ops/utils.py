from contextlib import contextmanager
from enum import Enum
import os
import pickle
import shutil
import sqlite3
from typing import List, cast, Optional, Dict, Union, Generator, Any

from chromadb import Collection
import chromadb
from chromadb import __version__ as chroma_version
import hnswlib


def validate_chroma_persist_dir(persist_dir: str) -> None:
    if not os.path.exists(persist_dir):
        raise ValueError(f"Persist dir ({persist_dir}) does not exist")
    if not os.path.exists(f"{persist_dir}/chroma.sqlite3"):
        raise ValueError(
            f"{persist_dir} does not appear to be valid ChromaDB persist directory"
        )


class SqliteMode(str, Enum):
    READ_ONLY = "ro"
    READ_WRITE = "rw"


def get_sqlite_snapshot_connection(snapshot_file: str) -> sqlite3.Connection:
    with open(snapshot_file, "a"):
        os.utime(snapshot_file, None)
    conn = sqlite3.connect(f"file:{snapshot_file}?mode=rw", uri=True)
    return conn


@contextmanager
def get_sqlite_connection(
    persist_dir: str, mode: SqliteMode = SqliteMode.READ_ONLY
) -> Generator[sqlite3.Connection, Any, None]:
    """Get a connection to the SQLite database. Assumes the database is in the persist directory."""
    sql_file = os.path.join(persist_dir, "chroma.sqlite3")
    if not os.path.exists(sql_file):
        raise ValueError(f"SQLite database file ({sql_file}) does not exist")
    else:
        with open(sql_file, "a"):
            os.utime(sql_file, None)

    conn = sqlite3.connect(f"file:{sql_file}?mode={mode.value}", uri=True)
    try:
        yield conn
    finally:
        conn.close()


def get_hnsw_index_ids(filename: str, space: str = "l2", dim: int = 384) -> List[int]:
    index = hnswlib.Index(space=space, dim=dim)
    index.load_index(
        filename,
        is_persistent_index=True,
        max_elements=100000,
    )
    ids = index.get_ids_list().copy()
    index.close_file_handles()
    return cast(List[int], ids)


def read_script(script: str) -> str:
    return open(
        os.path.join(os.path.dirname(os.path.realpath(__file__)), script), "r"
    ).read()


def get_dir_size(path: str) -> int:
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if os.path.exists(fp):
                total_size += os.path.getsize(fp)
    return total_size


def get_file_size(path: str) -> int:
    # ensure it is a file
    if not os.path.isfile(path):
        raise ValueError(f"{path} is not a file")
    return os.path.getsize(path)


SeqId = int


# TODO this works for versions of Chroma using pickle persistent data.
class PersistentData:
    """Stores the data and metadata needed for a PersistentLocalHnswSegment"""

    dimensionality: Optional[int]
    total_elements_added: int
    max_seq_id: SeqId

    id_to_label: Dict[str, int]
    label_to_id: Dict[int, str]
    id_to_seq_id: Dict[str, SeqId]

    def __init__(
        self,
        dimensionality: Optional[int],
        total_elements_added: int,
        max_seq_id: int,
        id_to_label: Dict[str, int],
        label_to_id: Dict[int, str],
        id_to_seq_id: Dict[str, SeqId],
    ):
        self.dimensionality = dimensionality
        self.total_elements_added = total_elements_added
        self.max_seq_id = max_seq_id
        self.id_to_label = id_to_label
        self.label_to_id = label_to_id
        self.id_to_seq_id = id_to_seq_id

    @staticmethod
    def load_from_file(filename: str) -> "PersistentData":
        """Load persistent data from a file"""
        with open(filename, "rb") as f:
            ret = cast(PersistentData, pickle.load(f))
            return ret


def decode_seq_id(seq_id_bytes: Union[bytes, int]) -> SeqId:
    """Decode a byte array into a SeqID"""
    if isinstance(seq_id_bytes, int):
        return seq_id_bytes

    if len(seq_id_bytes) == 8:
        return int.from_bytes(seq_id_bytes, "big")
    elif len(seq_id_bytes) == 24:
        return int.from_bytes(seq_id_bytes, "big")
    else:
        raise ValueError(f"Unknown SeqID type with length {len(seq_id_bytes)}")


# https://stackoverflow.com/a/1094933
def sizeof_fmt(num: int, suffix: str = "B") -> str:
    n: float = float(num)
    for unit in ("", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"):
        if abs(n) < 1024.0:
            return f"{n:3.1f}{unit}{suffix}"
        n /= 1024.0
    return f"{n:.1f}Yi{suffix}"


def list_collections(client: chromadb.PersistentClient) -> List[Collection]:
    if tuple(int(part) for part in chroma_version.split(".")) < (0, 6, 0):
        return client.list_collections()  # type: ignore
    else:
        collections = []
        for collection_name in client.list_collections():
            collections.append(client.get_collection(collection_name))
        return collections


class DistanceMetric(str, Enum):
    COSINE = "cosine"
    L2 = "l2"
    IP = "ip"


def get_disk_free_space(directory: str) -> int:
    """Returns free space in bytes for the device containing the directory"""
    return shutil.disk_usage(directory).free


def check_disk_space(source_dir: str, target_dir: str) -> bool:
    """
    Checks if target directory's device has enough space for source files
    Returns (has_space, message)
    """
    source_size = get_dir_size(source_dir)
    free_space = get_disk_free_space(target_dir)
    required_space = source_size * 1.1  # Require 10% extra space to be safe

    if free_space < required_space:
        return False
    return True

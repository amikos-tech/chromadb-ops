import os
import pickle
from typing import List, cast, Optional, Dict, Union

import hnswlib


def validate_chroma_persist_dir(persist_dir: str) -> None:
    if not os.path.exists(persist_dir):
        raise ValueError(f"Persist dir ({persist_dir}) does not exist")
    if not os.path.exists(f"{persist_dir}/chroma.sqlite3"):
        raise ValueError(
            f"{persist_dir} does not appear to be valid ChromaDB persist directory"
        )


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

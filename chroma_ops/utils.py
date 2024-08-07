import os
import pickle
from typing import List, cast, Optional, Dict

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

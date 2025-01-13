import os
from typing import Optional, Sequence, Any, Dict

import chromadb
import hnswlib
import typer
from chromadb.segment.impl.vector.hnsw_params import HnswParams
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.rule import Rule
from rich.table import Table

from chroma_ops.utils import (
    SqliteMode,
    list_collections,
    get_sqlite_connection,
    validate_chroma_persist_dir,
    get_dir_size,
    decode_seq_id,
    PersistentData,
    sizeof_fmt,
    get_file_size,
)


def info(
    persist_dir: str,
    skip_collection_names: Optional[Sequence[str]] = None,
    privacy_mode: Optional[bool] = False,
) -> Dict[str, Any]:
    console = Console()
    validate_chroma_persist_dir(persist_dir)
    export_data = {}
    chroma_version = chromadb.__version__
    export_data["chroma_version"] = chroma_version
    persist_dir_size = sizeof_fmt(get_dir_size(persist_dir))
    export_data["persist_dir_size"] = persist_dir_size
    client = chromadb.PersistentClient(path=persist_dir)
    collection_count = client.count_collections()
    export_data["collection_count"] = collection_count
    collection_data = {}

    sql_file = os.path.join(persist_dir, "chroma.sqlite3")
    sysdb_size = sizeof_fmt(get_file_size(sql_file))
    export_data["sysdb_size"] = sysdb_size
    with get_sqlite_connection(persist_dir, SqliteMode.READ_WRITE) as conn:
        active_hnsw_segment_dirs = set()
        console.print()
        with Progress(
            SpinnerColumn(finished_text="[bold green]:heavy_check_mark:[/bold green]"),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            task = progress.add_task(
                "Gathering collection data...", total=collection_count
            )
            for c in list_collections(client):
                if (
                    skip_collection_names is not None
                    and c.name in skip_collection_names
                ):
                    progress.update(task, advance=1)
                    continue
                collection = {
                    "id": str(c.id),
                    "name": c.name,
                    "metadata": c.metadata,
                    "tenant": c.tenant,
                    "database": c.database,
                    "records": c.count(),
                }
                cname = c.name
                cursor = conn.cursor()
                query = "SELECT s.*,c.* FROM segments s LEFT JOIN collections c ON s.collection = c.id WHERE c.id = ?;"
                cursor.execute(query, [collection["id"]])
                results = cursor.fetchall()
                collection["segments"] = []
                if len(results) > 0:
                    collection["dimension"] = (
                        c._model.dimension if hasattr(c, "_model") else results[0][8]
                    )
                for row in results:
                    segment = {
                        "id": row[0],
                        "type": row[1],
                        "scope": row[2],
                        "path": sql_file
                        if row[2] == "METADATA"
                        else os.path.join(persist_dir, row[0]),
                        "segment_metadata_path": None
                        if row[2] == "METADATA"
                        else os.path.join(persist_dir, row[0], "index_metadata.pickle"),
                    }
                    active_hnsw_segment_dirs.add(segment["path"])
                    max_seq_id_query = (
                        "SELECT seq_id FROM max_seq_id WHERE segment_id = ?"
                    )
                    cursor.execute(max_seq_id_query, [row[0]])  # N+1 query fun
                    results = cursor.fetchall()
                    segment["sysdb_max_seq_id"] = (
                        decode_seq_id(results[0][0]) if len(results) > 0 else 0
                    )
                    if segment["scope"] == "VECTOR":
                        segment["hnsw_dir_size"] = sizeof_fmt(
                            get_dir_size(segment["path"])
                        )
                        segment["hnsw_metadata_max_seq_id"] = 0
                        segment["hnsw_metadata_total_elements"] = 0
                        segment["wal_gap"] = 0
                        segment["hnsw_raw_total_elements"] = 0
                        segment["hnsw_orphan_elements"] = set()
                        segment["fragmentation_level"] = 0.0
                        segment["hnsw_raw_capacity"] = 0
                        if os.path.exists(segment["segment_metadata_path"]):
                            hnsw_metadata = PersistentData.load_from_file(
                                segment["segment_metadata_path"]
                            )
                            # support chroma 0.5.7+
                            if hasattr(hnsw_metadata, "max_seq_id"):
                                segment[
                                    "hnsw_metadata_max_seq_id"
                                ] = hnsw_metadata.max_seq_id
                            else:
                                max_seq_id_query_hnsw_057 = (
                                    "SELECT seq_id FROM max_seq_id WHERE segment_id = ?"
                                )
                                cursor.execute(max_seq_id_query_hnsw_057, [row[0]])
                                results = cursor.fetchall()
                                segment["hnsw_metadata_max_seq_id"] = (
                                    decode_seq_id(results[0][0])
                                    if len(results) > 0
                                    else 0
                                )
                            segment["hnsw_metadata_total_elements"] = len(
                                hnsw_metadata.id_to_label
                            )
                            segment["wal_gap"] = collection["records"] - len(
                                hnsw_metadata.id_to_label
                            )
                            hnsw_params = HnswParams(collection["metadata"])
                            index = hnswlib.Index(
                                space=hnsw_params.space, dim=collection["dimension"]
                            )
                            index.load_index(
                                os.path.join(segment["path"]),
                                is_persistent_index=True,
                                max_elements=segment["hnsw_metadata_max_seq_id"],
                            )
                            hnsw_ids = index.get_ids_list()
                            segment["hnsw_raw_total_elements"] = len(hnsw_ids)
                            segment["hnsw_raw_capacity"] = index.element_count
                            # fragmentation ration tells us the ratio of active elements vs total elements -
                            # the greater this number the more fragmented the index is impacting memory and performance
                            segment["fragmentation_level"] = (
                                (
                                    index.element_count
                                    - segment["hnsw_raw_total_elements"]
                                )
                                / index.element_count
                            ) * 100
                            hnsw_metadata_labels = set(hnsw_metadata.label_to_id.keys())
                            segment["hnsw_orphan_elements"] = (
                                set(hnsw_ids) - hnsw_metadata_labels
                            )
                            index.close_file_handles()
                    else:
                        # TODO implement stats on the metadata segment
                        # metadata segment
                        # metadata_info_query = "select count(*) from embedding_metadata  where segment_id = ? AND key <> 'chroma:document' group by id;"
                        ...
                    collection["segments"].append(segment)
                # Get WAL entries per collection
                query = "SELECT count(*) FROM embeddings_queue WHERE topic = ?;"
                cursor.execute(
                    query, [f"persistent://default/default/{collection['id']}"]
                )
                results = cursor.fetchall()
                collection["wal_entries"] = results[0][0]
                collection_data[cname] = collection
                progress.update(task, advance=1)

    # list dirs under persist_dir
    orphan_hnsw_dirs = []
    for entry in os.scandir(persist_dir):
        if (
            entry.is_dir()
            and os.path.join(persist_dir, entry.name) not in active_hnsw_segment_dirs
        ):
            orphan_hnsw_index = {
                "size": sizeof_fmt(get_dir_size(entry.path)),
                "path": entry.path if not privacy_mode else "redacted",
                "id": entry.name,
            }
            orphan_hnsw_dirs.append(orphan_hnsw_index)

    gtable = Table(title="General Info", expand=True)
    gtable.add_column("Property", justify="right", style="cyan", no_wrap=True)
    gtable.add_column("Value", style="magenta")
    gtable.add_row("Chroma Version", str(chroma_version))
    gtable.add_row("Number of Collection", str(collection_count))
    gtable.add_row(
        "Persist Directory", str(persist_dir) if not privacy_mode else "redacted"
    )
    gtable.add_row("Persist Directory Size", str(persist_dir_size))
    gtable.add_row(
        "SystemDB size: ",
        f"{sysdb_size} ({sql_file if not privacy_mode else 'redacted'})",
    )
    gtable.add_row("Orphan HNSW Directories", str(orphan_hnsw_dirs))
    console.print(gtable)
    console.print(Rule("Collections", style="red"))
    # Creating a table for the main information
    for cname, data in collection_data.items():
        tname = cname if not privacy_mode else data["id"]
        table = Table(title=f"'{tname}' Collection Data", expand=True)

        table.add_column("Table Data", justify="right", style="cyan", no_wrap=True)
        table.add_column("Value", style="magenta")

        table.add_row("ID", data["id"])
        table.add_row("Name", data["name"] if not privacy_mode else "redacted")
        table.add_row(
            "Metadata",
            str(data["metadata"])
            if not privacy_mode
            else str(
                {k: v for k, v in data["metadata"].items() if k.startswith("hnsw:")}
                if data["metadata"]
                else None
            ),
        )
        table.add_row("Dimension", str(data["dimension"]))
        table.add_row("Tenant", data["tenant"])
        table.add_row("Database", data["database"])
        table.add_row("Records", f"{data['records']:,}")
        table.add_row("WAL Entries", f"{data['wal_entries']:,}")

        metadata_segment = [
            segment for segment in data["segments"] if segment["scope"] == "METADATA"
        ][0]

        metadata_segment_table = Table(title=f"Metadata Segment ({tname})", expand=True)

        metadata_segment_table.add_column(
            "Property", justify="right", style="cyan", no_wrap=True
        )
        metadata_segment_table.add_column("Value", style="magenta")

        metadata_segment_table.add_row("Segment ID", metadata_segment["id"])
        metadata_segment_table.add_row("Type", metadata_segment["type"])
        metadata_segment_table.add_row("Scope", metadata_segment["scope"])
        metadata_segment_table.add_row(
            "SysDB Max Seq ID", f"{metadata_segment['sysdb_max_seq_id']:,}"
        )

        hnsw_segment = [
            segment for segment in data["segments"] if segment["scope"] == "VECTOR"
        ][0]

        hnsw_segment_table = Table(title=f"HNSW Segment ({tname})", expand=True)

        hnsw_segment_table.add_column(
            "Property", justify="right", style="cyan", no_wrap=True
        )
        hnsw_segment_table.add_column("Value", style="magenta")

        hnsw_segment_table.add_row("Segment ID", hnsw_segment["id"])
        hnsw_segment_table.add_row("Type", hnsw_segment["type"])
        hnsw_segment_table.add_row("Scope", hnsw_segment["scope"])
        hnsw_segment_table.add_row(
            "Path",
            hnsw_segment["path"] if not privacy_mode else f"*/{hnsw_segment['id']}",
        )
        hnsw_segment_table.add_row(
            "SysDB Max Seq ID", f"{hnsw_segment['sysdb_max_seq_id']:,}"
        )
        hnsw_segment_table.add_row("HNSW Dir Size", hnsw_segment["hnsw_dir_size"])
        hnsw_segment_table.add_row(
            "HNSW Metadata Max Seq ID", f"{hnsw_segment['hnsw_metadata_max_seq_id']:,}"
        )
        hnsw_segment_table.add_row(
            "HNSW Metadata Total Labels",
            f"{hnsw_segment['hnsw_metadata_total_elements']:,}",
        )
        hnsw_segment_table.add_row("WAL Gap", f"{hnsw_segment['wal_gap']:,}")
        hnsw_segment_table.add_row(
            "HNSW Raw Total Active Labels",
            f"{hnsw_segment['hnsw_raw_total_elements']:,}",
        )
        hnsw_segment_table.add_row(
            "HNSW Raw Allocated Labels", f"{hnsw_segment['hnsw_raw_capacity']:,}"
        )
        hnsw_segment_table.add_row(
            "HNSW Orphan Labels", str(hnsw_segment["hnsw_orphan_elements"])
        )
        hnsw_segment_table.add_row(
            "Fragmentation Level", str(hnsw_segment["fragmentation_level"])
        )
        console.print(Rule(f"{tname}", style="yellow"))
        console.print(table)
        console.print(Rule("Segments"))
        console.print(metadata_segment_table)
        console.print(hnsw_segment_table)
    export_data["collections"] = collection_data
    return export_data


def command(
    persist_dir: str = typer.Argument(..., help="The persist directory"),
    skip_collection_names: str = typer.Option(
        None,
        "--skip-collection-names",
        "-s",
        help="Comma separated list of collection names to skip",
    ),
    privacy_mode: bool = typer.Option(
        False,
        "--privacy-mode",
        "-p",
        help="Redact sensitive data such as paths and names",
    ),
) -> None:
    info(
        persist_dir,
        skip_collection_names=skip_collection_names,
        privacy_mode=privacy_mode,
    )

# ChromaDB Operations Tools

Tiny collection of utilities to help you managed ChromaDB indices.

WARNING: These tools rely on internal ChromaDB APIs and may break in the future.

## ☠️☠️☠️ BEFORE YOU BEGIN ☠️☠️☠️

Before you use these tools make sure your ChromaDB persistent dir, on which you intend to run these tools, is backed up.

## Installation

```bash
pip install chromadb-ops
```

## Usage

### Info

Gather general information about your persistent Chroma instance. This command is useful to understand what's going on
internally in Chroma and to get recommendations or support from the team by providing the output.

```bash
chops info /path/to/persist_dir
```

Supported options are:

- `--skip-collection-names` (`-s`) - to skip specific collections
- `--privacy-mode` (`-p`) - privacy mode hides paths and collection names so that the output can be shared without
  exposing sensitive information

When sharing larger outputs consider storing the output in a file:

```bash
chops info /path/to/persist_dir -p > chroma_info.txt
```

Sample output:

```console
                                 General Info
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                    Property ┃ Value                                          ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│              Chroma Version │ 0.5.5                                          │
│        Number of Collection │ 1                                              │
│           Persist Directory │ /tmp/tmp9l3ceuvp                               │
│      Persist Directory Size │ 142.2MiB                                       │
│              SystemDB size: │ 81.6MiB (/tmp/tmp9l3ceuvp/chroma.sqlite3)      │
│     Orphan HNSW Directories │ []                                             │
└─────────────────────────────┴────────────────────────────────────────────────┘
───────────────────────────────── Collections ──────────────────────────────────
───────────────────────────────────── test ─────────────────────────────────────
                             'test' Collection Data
┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃         Table Data ┃ Value                                                   ┃
┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│                 ID │ 9e80e4fd-fd4b-47b8-810c-e8ffa57c1912                    │
│               Name │ test                                                    │
│           Metadata │ None                                                    │
│          Dimension │ 1536                                                    │
│             Tenant │ default_tenant                                          │
│           Database │ default_database                                        │
│            Records │ 10,000                                                  │
│        WAL Entries │ 10,000                                                  │
└────────────────────┴─────────────────────────────────────────────────────────┘
─────────────────────────────────── Segments ───────────────────────────────────
                            Metadata Segment (test)
┏━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                Property ┃ Value                                              ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│              Segment ID │ 832fa2cd-6c40-4eee-ad7d-35f260acaaaa               │
│                    Type │ urn:chroma:segment/metadata/sqlite                 │
│                   Scope │ METADATA                                           │
│        SysDB Max Seq ID │ 10,000                                             │
└─────────────────────────┴────────────────────────────────────────────────────┘
                              HNSW Segment (test)
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                     Property ┃ Value                                         ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│                   Segment ID │ 13609103-d317-4556-a744-008c96229b72          │
│                         Type │ urn:chroma:segment/vector/hnsw-local-persist… │
│                        Scope │ VECTOR                                        │
│                         Path │ /tmp/tmp9l3ceuvp/13609103-d317-4556-a744-008… │
│             SysDB Max Seq ID │ 0                                             │
│                HNSW Dir Size │ 60.6MiB                                       │
│     HNSW Metadata Max Seq ID │ 10,000                                        │
│   HNSW Metadata Total Labels │ 10,000                                        │
│                      WAL Gap │ 0                                             │
│ HNSW Raw Total Active Labels │ 10,000                                        │
│    HNSW Raw Allocated Labels │ 10,000                                        │
│           HNSW Orphan Labels │ set()                                         │
│          Fragmentation Level │ 0.0                                           │
└──────────────────────────────┴───────────────────────────────────────────────┘
```

⚠️ Interesting things to look for:

- Fragmentation Level - the higher the value the more unnecessary memory and performance hits your HNSW index suffers.
  It needs to be rebuilt.
- Orphan HNSW Directories - these are directories that are not associated with any collection. They can be safely
  deleted.
- WAL Entries - high values usually means that you need prune your WAL. Use either this tool or
  the [official Chroma CLI](https://cookbook.chromadb.dev/core/advanced/wal-pruning/#chroma-cli).
- HNSW Orphan Labels - this must always be empty set, if you see anything else report it
  in [Discord](https://discord.gg/MMeYNTmh3x).

### WAL Commit

This command ensures your WAL is committed to binary vector index (HNSW).

```bash
chops commit-wal /path/to/persist_dir
```

> Note: You can skip certain collections by running `chops commit-wal /path/to/persist_dir --skip <collection_name>`

### WAL Cleanup

This command cleans up the committed portion of the WAL and VACUUMs the database.

```bash
chops clean-wal /path/to/persist_dir
```

### WAL Export

This commands exports the WAL to a `jsonl` file. The command can be useful in taking backups of the WAL.

```bash
chops export-wal /path/to/persist_dir --out /path/to/export.jsonl
```

> Note: If --out or -o is not specified the command will print the output to stdout.

### Full-Text Search Index Rebuild

This command rebuilds the full-text search index.

> Note: **_Why is this needed_**? Users have reported broken FTS indices that result in a error of this
> kind: `no such table: embedding_fulltext_search`

```bash
chops rebuild-fts /path/to/persist_dir
```

### Using Docker

> Note: You have to mount your persist directory into the container for the commands to work.


Building the image:

```bash
docker build -t chops .
```

#### WAL Commit

```bash
docker run -it --rm -v ./persist_dir:/chroma-data ghcr.io/amikos-tech/chromadb-ops/chops:latest commit-wal /chroma-data
```

#### WAL Cleanup

```bash
docker run -it --rm -v ./persist_dir:/chroma-data ghcr.io/amikos-tech/chromadb-ops/chops:latest clean-wal /chroma-data
```

#### WAL Export

```bash
docker run -it --rm -v ./persist_dir:/chroma-data -v ./backup:/backup ghcr.io/amikos-tech/chromadb-ops/chops:latest export-wal /chroma-data --out /backup/export.jsonl
```

#### Full-Text Search Index Rebuild

```bash
docker run -it --rm -v ./persist_dir:/chroma-data ghcr.io/amikos-tech/chromadb-ops/chops:latest rebuild-fts /chroma-data
```

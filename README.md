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

#### How to Read the output

**General Info**

This section presents general Chroma persistent dir info.

- Chroma Version - the currently installed Chroma version.
- Number of Collection - the number of collections in the persistent dir.
- Persist Directory - the path to the persistent dir (if privacy mode is off).
- Persist Directory Size - the size of the persistent dir.
- SystemDB size - the size of the system database (if privacy mode is off the full path to the sqlite3 file is shown).
- Orphan HNSW Directories - a list of orphan HNSW directories. These directories are present in the persistent dir but
  are not associated with any collection.

**Collections**

- ID - the collection ID.
- Name - the collection name.
- Metadata - the metadata associated with the collection.
- Dimension - the dimension of the embeddings in the collection. (this can be None in case no vectors are present and
  the collection is newly created).
- Tenant - the tenant of the collection.
- Database - the database of the collection.
- Records - the number of records in the collection.
- WAL Entries - the number of WAL entries in the collection (as of 0.5.5 for new instances Chroma will clean WAL for
  each collection periodically).

**Metadata Segment**

- Segment ID - the segment ID.
- Type - the segment type.
- Scope - the segment scope.
- SysDB Max Seq ID - the maximum sequence ID in the system database.

**HNSW Segment**

- Segment ID - the segment ID.
- Type - the segment type.
- Scope - the segment scope.
- Path - the path to the HNSW directory.
- SysDB Max Seq ID - the maximum sequence ID in the system database.
- HNSW Dir Size - the size of the HNSW directory.
- HNSW Metadata Max Seq ID - the maximum sequence ID in the HNSW metadata.
- HNSW Metadata Total Labels - the total number of labels in the HNSW metadata.
- WAL Gap - the difference between the maximum sequence ID in the system database and the maximum sequence ID in the
  HNSW
  metadata. The gap usually represents the number of WAL entries that are not committed to the HNSW index.
- HNSW Raw Total Active Labels - the total number of active labels in the HNSW index.
- HNSW Raw Allocated Labels - the total number of allocated labels in the HNSW index.
- HNSW Orphan Labels - a set of orphan labels in the HNSW index. These are labels in the HNSW index that are not visible
  to Chroma as they are not part of the metadata. This set should always be empty, if not please report it!!!
- Fragmentation Level - the fragmentation level of the HNSW index.

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

### Clean

This command cleans up orphaned vector segment directories.

```bash
chops clean /path/to/persist_dir
```

> Note: The command is particularly useful for windows users where deleting collections may leave behind orphaned vector
> segment directories due to Windows file locking.

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

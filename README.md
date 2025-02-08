# Chroma Maintenance CLI

> Silent logs whisper,  
> indexes drift like lost leaves—  
> vacuum sweeps the past.  
>  
> Tables stand renewed,  
> queries dance with swift purpose,  
> data breathes again.

Chroma Ops is designed to help you maintain a healthy Chroma database. It can also be used for inspecting the state of your database.

The following use cases are supported:

- 📦 Database Maintenance
  - [`db info`](#info) - gathers general information about your Chroma persistent database
  - [`db clean`](#clean) - cleans up the database from unused files (for now only orphanated HNSW segment directories)
- 📝 Write-Ahead Log (WAL) Maintenance
  - [`wal info`](#info-1) - gathers information about the Write-Ahead Log (WAL)
  - [`wal commit`](#commit) - commits the WAL to all collections with outstanding changes
  - [`wal clean`](#clean-1) - cleans up the WAL from committed transactions. Recent Chroma version automatically prune the WAL so this is not needed unless you have older version of Chroma or disabled automatic WAL pruning.
  - [`wal export`](#export) - exports the WAL to a `jsonl` file. This can be used for debugging and for auditing.
  - [`wal config`](#configuration) - allows you to configure the WAL for your Chroma database.
- 🔍 Full Text Search (FTS) Maintenance
  - [`fts rebuild`](#rebuild) - rebuilds the FTS index for all collections or change the tokenizer.
- 🧬 Vector Index (HNSW) Maintenance
  - [`hnsw info`](#info-2) - gathers information about the HNSW index for a given collection
  - [`hnsw rebuild`](#rebuild-1) - rebuilds the HNSW index for a given collection and allows the modification of otherwise immutable (construction-only) parameters. Useful command to keep your HNSW index healthy and prevent fragmentation.
  - [`hnsw config`](#configuration-1) - allows you to configure the HNSW index for your Chroma database.
- 📸 Collection Maintenance
  - [`collection snapshot`](#snapshot) - creates a snapshot of a collection. The snapshots are self-contained and are meant to be used for backup and restore.

> [!TIP]
> Some of Chroma Ops tool functionality relies on internal Chroma APIs and breaking changes with new version of Chroma are possible.

> [!WARNING]
> Before you use these tools make sure your Chroma persistent dir, on which you intend to run these tools, is backed up.

## Installation

### Python

```bash
pip install --upgrade chromadb-ops
```

### Go

```bash
go install github.com/amikos-tech/chromadb-ops/cmd/chops
```

## Usage

### Collection

#### Snapshot

This command creates a snapshot of a collection. It will lock the chroma database while the snapshot is being created to ensure consistency.
The data is stored in sqlite3 file including all binary indices.

**Python:**

```bash
chops collection snapshot /path/to/persist_dir --collection <collection_name> -o /path/to/snapshot.sqlite3
```

Options:

- `--collection` (`-c`) - the collection name
- `--output` (`-o`) - the path to the output snapshot file
- `--yes` (`-y`) - skip confirmation prompt (default: `False`, prompt will be shown)

**Go:**

> [!NOTE]
> Coming soon

#### Restore

> [!NOTE]
> The restore command will come in v0.1.1

### Database Maintenance

#### Info

Gather general information about your persistent Chroma instance. This command is useful to understand what's going on
internally in Chroma and to get recommendations or support from the team by providing the output.

**Python:**

```bash
chops db info /path/to/persist_dir
```

Options:

- `--skip-collection-names` (`-s`) - to skip specific collections
- `--privacy-mode` (`-p`) - privacy mode hides paths and collection names so that the output can be shared without
  exposing sensitive information

When sharing larger outputs consider storing the output in a file:

```bash
chops db info /path/to/persist_dir -p > chroma_info.txt
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

#### Clean

This command cleans up orphanated HNSW segment subdirectories.

> [!TIP]
> The command is particularly useful for Microsoft Windows users where deleting collections may leave behind orphaned vector
> segment directories due to Windows file locking.

**Python:**

```bash
chops db clean /path/to/persist_dir
```

Options:

- `--yes` (`-y`) - skip confirmation prompt (default: `False`, prompt will be shown)

**Go:**


```bash
chops db clean /path/to/persist_dir
```

Options:

- `--dry-run` (`-d`) - to see what would be deleted without actually deleting anything.


### WAL Maintenance

#### Info

This command shows the number of records in the WAL for each collection.

**Python:**

```bash
chops wal info /path/to/persist_dir
```

**Go:**

> [!NOTE]
> Coming soon

#### Commit

This command ensures your WAL is committed to binary vector index (HNSW).

**Python:**

```bash
chops wal commit /path/to/persist_dir
```

Options:

- `--skip` (`-s`) - skip certain collections by running `chops wal commit /path/to/persist_dir --skip <collection_name>`
- `--yes` (`-y`) - skip confirmation prompt (default: `False`, prompt will be shown)

**Go:**

> [!NOTE]
> Coming soon

#### Clean

This command cleans up the committed portion of the WAL and VACUUMs the database.

**Python:**

```bash
chops wal clean /path/to/persist_dir
```

Options:

- `--yes` (`-y`) - skip confirmation prompt (default: `False`, prompt will be shown)

**Go:**

> [!NOTE]
> Coming soon

#### Export

This commands exports the WAL to a `jsonl` file. The command can be useful in taking backups of the WAL.

**Python:**

```bash
chops wal export /path/to/persist_dir --out /path/to/export.jsonl
```

Options:

- `--yes` (`-y`) - skip confirmation prompt (default: `False`, prompt will be shown)
- `--out` (`-o`) - the path to the output file

> [!NOTE]
> If --out or -o is not specified the command will print the output to stdout.

**Go:**

> [!NOTE]
> Coming soon

#### Configuration

This command helps you configure Chroma WAL behavior. Currently only the purge behavior can be configured.

**Python:**

```bash
chops wal config /path/to/persist_dir --purge auto
```

Options:

- `--purge` option can be set to `auto` (automatically purge the WAL when the number of records in the collection exceeds the number of
  records in the WAL) or `off` (disable automatic purge of the WAL). Automatic WAL purge is enabled by default. The automatic purge keeps your slite3 file smaller and faster, but it makes it hard or impossible to restore Chroma.
- `--yes` option can be set to `true` (skip confirmation prompt) or `false` (show confirmation prompt). The default is `false`.

**Go:**

> [!NOTE]
> Coming soon

### Full-Text Search (FTS) Maintenance

#### Rebuild

This command rebuilds the full-text search index.

> Note: **_Why is this needed_**? Users have reported broken FTS indices that result in a error of this
> kind: `no such table: embedding_fulltext_search`

**Python:**

```bash
chops fts rebuild /path/to/persist_dir
```

Options:

- `--yes` (`-y`) - skip confirmation prompt (default: `False`, prompt will be shown)
- `--tokenizer` (`-t`) - the tokenizer to use for the index.
Change the tokenizer to `unicode61` by passing `--tokenizer unicode61` (or `-t unicode61`) option.

```bash
chops fts rebuild --tokenizer unicode61 /path/to/persist_dir
```

> [!TIP]
> See [SQLite FTS5 Tokenizers](https://www.sqlite.org/fts5.html#tokenizers) for more information and available tokenizers and their options.

**Go:**

```bash
chops fts rebuild /path/to/persist_dir
```

Change the tokenizer to `unicode61` by passing `--tokenizer unicode61` (or `-t unicode61`) option.

```bash
chops fts rebuild --tokenizer unicode61 /path/to/persist_dir
```

> See [SQLite FTS5 Tokenizers](https://www.sqlite.org/fts5.html#tokenizers) for more information and available tokenizers and their options.


### HNSW Maintenance

#### Info

**Python:**

```bash
chops hnsw info /path/to/persist_dir --collection <collection_name>
```

Options:

- `--collection` (`-c`) - the collection name
- `--verbose` (`-v`) - If specified, the HNSW index will be loaded for more accurate fragmentation level reporting.

**Go:**

> [!NOTE]
> Coming soon

#### Rebuild

Allows you to rebuild the HNSW index. The command also allows you to modify the HNSW index configuration, including parameters which are cannot be changed after index initialization.

Use cases:

- Defragment the index
- Change the distance metric
- Change configuration parameters like `M` or `construction_ef` parameters normally not changeable after index initialization
- Tune the HNSW index for better performance

**Python:**

```bash
chops hnsw rebuild /path/to/persist_dir --collection <collection_name>
```

Options:

- `--backup` (`-b`) - backup the old index. At the end of the rebuild process the location of the backed up index will be printed out. (default: `True`)
- `--database` (`-d`) - the database name (default: `default_database`)
- `--yes` (`-y`) - skip confirmation prompt (default: `False`, prompt will be shown)
- `--space` (`-s`) - the distance metric to use for the index.
- `--construction-ef` (`-c`) - the construction ef to use for the index.
- `--search-ef` (`-e`) - the search ef to use for the index.
- `--m` (`-m`) - the m to use for the index.
- `--num-threads` (`-t`) - the number of threads to use for the index.
- `--resize-factor` (`-r`) - the resize factor to use for the index.
- `--batch-size` (`-b`) - the batch size to use for the index.
- `--sync-threshold` (`-s`) - the sync threshold to use for the index.

> [!NOTE]
> All the HNSW index options default to `None` which means no changes will be made if the parameter is not specified. Additionally, any options provided that are identical to the current index configuration will be skipped.

**Go:**

> [!NOTE]
> Coming soon

#### Configuration

Allows you to modify the HNSW index configuration at runtime. This command only modifies configuration parameters that can be changed at runtime.

Use cases:

- Tune the HNSW index for better performance

**Python:**

```bash
chops hnsw config /path/to/persist_dir --collection <collection_name>
```

Options:

- `--search-ef` (`-e`) - the search ef to use for the index.
- `--num-threads` (`-t`) - the number of threads to use for the index.
- `--resize-factor` (`-r`) - the resize factor to use for the index.
- `--batch-size` (`-b`) - the batch size to use for the index.
- `--sync-threshold` (`-s`) - the sync threshold to use for the index.

> [!NOTE]
> All the HNSW index options default to `None` which means no changes will be made if the parameter is not specified. Additionally, any options provided that are identical to the current index configuration will be skipped.

**Go:**

> [!NOTE]
> Coming soon

### Using Docker

> Note: You have to mount your persist directory into the container for the commands to work.

Building the image:

```bash
docker build -t chops .
```

#### Running Commands

```bash
docker run -it --rm -v ./persist_dir:/chroma-data ghcr.io/amikos-tech/chromadb-ops/chops:latest <command>
```

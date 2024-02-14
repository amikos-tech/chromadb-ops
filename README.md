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

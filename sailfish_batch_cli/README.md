# `sailfish_batch_cli`

A small CLI to **inspect Sailfish batches** stored in RocksDB worker stores. It can:

* **List** all batch digests found in one or more RocksDB paths.
* **Print** a single batch (its transactions) by digest.
* Accept digests in **hex** or **base64**.
* Output in **pretty JSON** (`--json`) or a compact debug format.

> The tool opens RocksDB in **read‑only** mode and reads from the `default` column family.

---

## Build

```bash
# From the workspace root
cargo build --release -p sailfish_batch_cli

# Binary will be at
./target/release/sailfish_batch_cli
```

---

## Usage

### List all batch digests in one or more DB paths

```bash
sailfish_batch_cli --list <db_path> [db_path ...]
```

**Examples**

```bash
# List all digests from a single worker store
sailfish_batch_cli --list /var/lib/sailfish/store-0

# Merge-list across multiple worker stores, de-duplicated
sailfish_batch_cli --list /var/lib/sailfish/store-0 /var/lib/sailfish/store-1
```

The output is one **hex digest per line**.

---

### Show a batch by digest (hex or base64)

```bash
sailfish_batch_cli [--json] <batch_digest> <db_path> [db_path ...]
```

* `<batch_digest>`: hex (`[0-9a-f]+`) **or** base64.
* `<db_path>`: one or more RocksDB directories (the tool searches them in order and prints the first match).

**Examples**

```bash
# Hex digest
sailfish_batch_cli 5b2a...e31f /var/lib/sailfish/store-0

# Base64 digest, pretty JSON output
sailfish_batch_cli --json gmw6t7wzjx7SyzuwSydLZLCGsiQDxWfrLf03eR21I94= \
  /var/lib/sailfish/store-0 /var/lib/sailfish/store-1
```

**Default (non‑JSON) output** is a compact line with the digest and a debug list of txs in hex.
**JSON output** looks like:

```json
{
  "digest": "5b2a...e31f",
  "txns": [
    "f86d1b84...",
    "f86d1c84..."
  ]
}
```

> Note: The tool only prints entries that deserialize as `WorkerMessage::Batch`.

---

## Parameters & flags

* `--list` : list batch digests from the given DB path(s). No digest argument when using this flag.
* `--json` : pretty‑print JSON when showing a single batch.

Positional arguments depend on the mode:

* **List mode**: `--list <db_path> [db_path ...]`
* **Show mode**: `[--json] <batch_digest> <db_path> [db_path ...]`

If arguments are missing or malformed, the tool prints usage help and exits with a non‑zero code.

---

## Typical workflows

### Find a digest then dump it as JSON

```bash
# 1) Get a digest from worker 0
DIGEST=$(sailfish_batch_cli --list /var/lib/sailfish/store-0 | head -n1)

# 2) Print the batch from either worker 0 or 1
sailfish_batch_cli --json "$DIGEST" /var/lib/sailfish/store-0 /var/lib/sailfish/store-1
```

### Verify a specific digest in multiple stores

```bash
sailfish_batch_cli 5b2a...e31f /var/lib/sailfish/store-0 /var/lib/sailfish/store-1 || \
  echo "Digest not found in provided databases"
```

---

## Troubleshooting

* **"Failed to open DB"**: Ensure the path points to a RocksDB directory (not a file) and that the process has read permissions. The tool expects a `default` column family to exist.
* **"Batch not found in provided databases"**: The digest may not exist, may belong to a different worker, or is not a `WorkerMessage::Batch` entry.
* **Input digest format**: The CLI accepts hex or base64. If you paste from logs that show base64, pass it unchanged; if logs show `0x...` hex, remove the `0x` prefix.
* **Large outputs**: Pipe to a pager or file: `... | less -R` or `... > batch.json`.

---

## Notes & limitations

* The utility is **read‑only** and does not lock or modify the DBs.
* It **de‑duplicates** digests when listing across multiple paths.
* Listing prints only entries that decode as `WorkerMessage::Batch`; other key types are ignored.
* If your deployment uses different column families, update the source to pass the correct CF names.

---

## Development

The main entry points are:

* `list_batches(db_paths: &[String])`
* `print_batch_from_dbs(db_paths: &[String], key_input: &str, json: bool)`
* `print_batch_from_db(db: &DB, cf: &rocksdb::ColumnFamily, key_bytes: &[u8], json: bool) -> bool`

Key decoding supports **hex** and **base64** via `decode_key_input`.

Contributions welcome—open a PR with small, focused changes and example logs/DB paths for reproduction.

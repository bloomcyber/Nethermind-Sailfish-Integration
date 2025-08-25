#!/usr/bin/env python3
"""
Extract ordered batches from Sailfish ordered_cert.json into a JSON **object** (dictionary)
keyed by a monotonically increasing **batch_index** (as a string). The value for each key is the
batch record (without an embedded batch_index field).

Input file may contain multiple pretty-printed JSON objects back-to-back (not a JSON array), each
object being a certificate produced by Sailfish.

Behavior:
- Skips certificates with empty payloads.
- For each batch digest, tries to take transactions from the certificate's `transactions` map.
  If missing/invalid, it invokes `sailfish_batch_cli` to fetch them. Retries with backoff until
  found or until `--max-retries` is exhausted. On exhaustion, snapshots progress and exits(2).
- Progressive **atomic snapshots** to the output file so you can see results while it runs.
- Resumable: If the output dict already contains some batches, new entries start from
  max(existing keys) + 1, and previously processed (cert_id, batch_digest) pairs are skipped.
- Ctrl+C / SIGTERM safe: it writes a final snapshot before exiting.

Output format example (object):
{
  "0": {
    "cert_id": "…",
    "round": 164,
    "author": "…",
    "batch_digest": "…",
    "transactions": ["0x…"],
    "blockhash": null,
    "blocknumber": -1
  },
  "1": { … }
}

Run:
  python3 extract_batches_from_ordered_certs.py \
      --input ordered_cert.json \
      --output Output/transactions_batch.json \
      --sailfish-cli ./target/release/sailfish_batch_cli \
      --db /path/to/worker-0 --db /path/to/worker-1 -vv
"""

import argparse
import json
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Union

# How often to snapshot (atomic write). Set to 1 to snapshot every new record.
SNAPSHOT_EVERY = 1

STOP_REQUESTED = False

def _signal_handler(signum, _frame):
    global STOP_REQUESTED
    STOP_REQUESTED = True
    logging.warning("Received signal %s; will stop after current step.", signum)

# -------------------- Helpers --------------------

def iter_json_objects(path: Path) -> Iterable[dict]:
    """Parse a file that contains multiple pretty-printed JSON objects back-to-back."""
    buf = ""
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not buf and not line.strip():
                continue
            buf += line
            try:
                obj = json.loads(buf)
                yield obj
                buf = ""
            except json.JSONDecodeError:
                continue
    if buf.strip():
        raise ValueError(f"Incomplete JSON object at end of file: {path}")

def normalize_tx_hex(tx: str) -> str:
    tx = tx.strip()
    if not tx:
        return tx
    if tx.startswith(("0x", "0X")):
        return tx
    return "0x" + tx

def run_sailfish_cli(
    cli_path: Path,
    digest: str,
    db_paths: List[Path],
    timeout_sec: int = 60,
) -> Optional[List[str]]:
    """Invoke sailfish_batch_cli to fetch txs for a digest. Expects JSON {"digest":"..","txns":[...]}."""
    cmd = [str(cli_path), "--json", digest] + [str(p) for p in db_paths]
    logging.debug("Running: %s", " ".join(cmd))
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
    except subprocess.TimeoutExpired:
        logging.warning("sailfish_batch_cli timed out for %s", digest)
        return None

    if proc.returncode != 0:
        logging.warning(
            "sailfish_batch_cli non-zero (%s) for %s; stderr: %s",
            proc.returncode, digest, (proc.stderr or "").strip()
        )
        return None

    out = (proc.stdout or "").strip()
    if not out:
        return None

    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        logging.warning("Failed to parse CLI JSON for %s; raw out (truncated): %s", digest, out[:500])
        return None

    txs = data.get("txns")
    if isinstance(txs, list) and all(isinstance(x, str) for x in txs):
        return txs
    return None


def extract_transactions_from_cert_transactions_field(
    cert_transactions: Dict[str, Union[str, List[str]]],
    batch_digest: str,
) -> Optional[List[str]]:
    """Pull tx list from cert.transactions[batch_digest] if present and not "missing"/"invalid"."""
    if not cert_transactions:
        return None
    val = cert_transactions.get(batch_digest)
    if val is None:
        return None
    if isinstance(val, str):
        logging.debug("Cert says txs for %s are: %s", batch_digest, val)
        return None
    if isinstance(val, list) and all(isinstance(x, str) for x in val):
        return val
    logging.debug("Unexpected 'transactions' value for %s: %r", batch_digest, val)
    return None


def load_existing_output(path: Path) -> Dict[str, dict]:
    """Load an existing output file expected to be a JSON object (dict)."""
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
        logging.warning("Existing output at %s is not a JSON object; ignoring.", path)
        return {}
    except Exception as e:
        logging.warning("Failed to read existing output at %s: %s", path, e)
        return {}


def snapshot_atomic(path: Path, records: Dict[str, dict]) -> None:
    """Atomically write JSON object to path and fsync."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(path)
    logging.debug("Snapshot written: %s (count=%d)", path, len(records))

# -------------------- Main --------------------

def main() -> int:
    # Handle signals
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    ap = argparse.ArgumentParser(description="Extract ordered batches into dict keyed by batch_index (string)")
    ap.add_argument("--input", required=True, type=Path, help="Path to ordered_cert.json (pretty JSON objects)")
    ap.add_argument("--output", required=True, type=Path, help="Path to write/append the batches JSON object")
    ap.add_argument("--sailfish-cli", required=True, type=Path, help="Path to sailfish_batch_cli binary")
    ap.add_argument("--db", dest="db_paths", action="append", type=Path, required=True,
                    help="Path to a RocksDB worker store. Repeat for multiple workers.")
    ap.add_argument("--retry-interval", type=float, default=2.0,
                    help="Seconds to wait between retries when a batch is missing (default: 2.0)")
    ap.add_argument("--max-retries", type=int, default=120,
                    help="Max retries per missing batch (default: 120). Use -1 to retry indefinitely.")
    ap.add_argument("-v", "--verbose", action="count", default=0, help="Increase logging verbosity (-v, -vv)")
    args = ap.parse_args()

    # Logging
    level = logging.WARNING
    if args.verbose == 1:
        level = logging.INFO
    elif args.verbose >= 2:
        level = logging.DEBUG
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(message)s")

    # Load existing dict and derive processed set & next index
    out_records: Dict[str, dict] = load_existing_output(args.output)
    processed = set()
    next_index = 0
    if out_records:
        try:
            next_index = max(int(k) for k in out_records.keys()) + 1
        except ValueError:
            next_index = 0
        for rec in out_records.values():
            cid = rec.get("cert_id")
            bd  = rec.get("batch_digest")
            if cid and bd:
                processed.add((cid, bd))
    logging.info("Loaded %d existing batches from %s; next_index=%d", len(out_records), args.output, next_index)

    since_last_snapshot = 0
    cert_counter = 0

    try:
        for cert in iter_json_objects(args.input):
            if STOP_REQUESTED:
                logging.warning("Stop requested; halting before next certificate.")
                break

            cert_counter += 1
            cert_id   = cert.get("id")
            author    = cert.get("author")
            round_num = cert.get("round")
            payload   = cert.get("payload", {}) or {}

            if not payload:
                logging.debug("Cert #%d has no payload; skipping.", cert_counter)
                continue

            cert_transactions = cert.get("transactions") or {}

            # Deterministic per-cert order
            for _i, (batch_digest, _worker_id) in enumerate(sorted(payload.items(), key=lambda kv: kv[0])):
                if STOP_REQUESTED:
                    logging.warning("Stop requested; halting in the middle of a certificate.")
                    break

                # Skip if already processed (supports skipping starting batches already present)
                if cert_id and (cert_id, batch_digest) in processed:
                    logging.debug("Skipping already-processed batch %s from cert %s", batch_digest, cert_id)
                    continue

                # 1) Try to use transactions from the certificate
                txs = extract_transactions_from_cert_transactions_field(cert_transactions, batch_digest)

                # 2) If missing, try CLI with retries
                if txs is None:
                    attempt = 0
                    while True:
                        if STOP_REQUESTED:
                            logging.warning("Stop requested during retries; snapshotting and exiting.")
                            snapshot_atomic(args.output, out_records)
                            return 130
                        attempt += 1
                        txs = run_sailfish_cli(args.sailfish_cli, batch_digest, args.db_paths)
                        if txs:
                            logging.info("Fetched %d txs for %s (attempt %d)", len(txs), batch_digest, attempt)
                            break
                        if args.max_retries == -1:
                            logging.info("No txs for %s yet (attempt %d). Retrying in %.2fs ...", batch_digest, attempt, args.retry_interval)
                            time.sleep(args.retry_interval)
                            continue
                        if attempt >= args.max_retries:
                            logging.error("Exhausted retries for %s after %d attempts.", batch_digest, attempt)
                            snapshot_atomic(args.output, out_records)
                            sys.exit(2)
                        logging.info("Missing txs for %s (attempt %d). Retrying in %.2fs ...", batch_digest, attempt, args.retry_interval)
                        time.sleep(args.retry_interval)

                txs_norm = [normalize_tx_hex(t) for t in txs]

                # Build record **without** embedding batch_index. Use key=str(next_index)
                record = {
                    "cert_id": cert_id,
                    "round": round_num,
                    "author": author,
                    "batch_digest": batch_digest,
                    "transactions": txs_norm,
                    "blockhash": None,
                    "blocknumber": -1,
                }

                out_records[str(next_index)] = record
                next_index += 1
                if cert_id:
                    processed.add((cert_id, batch_digest))

                since_last_snapshot += 1
                if since_last_snapshot >= SNAPSHOT_EVERY:
                    snapshot_atomic(args.output, out_records)
                    since_last_snapshot = 0

            if STOP_REQUESTED:
                break

    except KeyboardInterrupt:
        logging.warning("KeyboardInterrupt; writing final snapshot and exiting.")
        snapshot_atomic(args.output, out_records)
        return 130

    # Final snapshot
    snapshot_atomic(args.output, out_records)
    logging.info("Wrote %d batch records to %s", len(out_records), args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())

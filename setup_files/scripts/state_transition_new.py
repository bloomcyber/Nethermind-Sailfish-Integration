#!/usr/bin/env python3
"""
State Transition Driver for Nethermind (Engine API)

Reads a batches file produced by the ordered-batches extractor. The batches file is a
JSON **object** keyed by the global batch index (as a string: "0", "1", ...). Each value
contains:
  {
    cert_id, round, author, batch_digest,
    transactions: ["0x...", ...],
    blockhash: null | "0x...",
    blocknumber: -1 | <int>
  }

This script finds the first entry whose blockhash is empty, asserts that its key (batch index)
equals the current Nethermind `eth_blockNumber`, then executes the Engine API flow:
  - engine_forkchoiceUpdatedV3 (with attributes)
  - engine_getPayloadV4
  - compare payload.transactions to the expected batch transactions
  - engine_newPayloadV4
  - engine_forkchoiceUpdatedV3 (finalize to the new head)
On success it writes `blockhash` and `blocknumber` back into the batches file **immediately**
(atomic write), and also logs all RPCs to a log file (atomic write as well).

Flags:
  -v / -vv   : increase verbosity (INFO / DEBUG)

Exit codes:
  0  success
  1  batch index does not match current block height or payload mismatch
  2  general error in flow
 130 interrupted by user (Ctrl+C)
"""

import sys
import os
import time
import json
import binascii
import signal
from typing import Dict, List, Any

import jwt
import requests

# === CONFIGURATION ===
JWT_SECRET_PATH = "chain_data/jwt-secret"
OUTPUT_DIR      = "Output/.db-0"
os.makedirs(OUTPUT_DIR, exist_ok=True)

STATE_FILE = os.path.join(OUTPUT_DIR, "state.json")
BATCH_FILE = os.path.join(OUTPUT_DIR, "ordered_batches_nm.json")
LOG_FILE   = os.path.join(OUTPUT_DIR, "transition_log.json")

# Global JSON-RPC id & logs
next_id: int = 1
rpc_log: List[Dict[str, Any]] = []
pipeline_log: Dict[str, Any] = {}

# Verbosity (set by -v)
VERBOSE_LEVEL = 0

# ----------------- Small IO helpers -----------------

def atomic_write_json(path: str, data: Any) -> None:
    """Atomically write JSON with fsync to avoid data loss on crashes."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)

def flush_logs_safely() -> None:
    try:
        atomic_write_json(LOG_FILE, {"rpcCalls": rpc_log, "pipeline": pipeline_log})
    except Exception as e:
        print(f"[WARN] Failed to write {LOG_FILE}: {e}", file=sys.stderr)


def save_batches(batches: Dict[str, dict]) -> None:
    try:
        atomic_write_json(BATCH_FILE, batches)
    except Exception as e:
        print(f"[WARN] Failed to write {BATCH_FILE}: {e}", file=sys.stderr)

# --------------- Signals -----------------

def on_sigint(signum, frame):
    print("[INFO] Caught Ctrl+C. Flushing logs and exiting...")
    flush_logs_safely()
    # do not lose partial progress in memory: if caller updated batches dict already,
    # it has been saved immediately at that point.
    sys.exit(130)

signal.signal(signal.SIGINT, on_sigint)

# --------------- Core helpers -----------------

def dprint(level: int, *args):
    if VERBOSE_LEVEL >= level:
        print(*args)


def generate_jwt(path: str) -> str:
    raw = open(path).read().strip()
    if raw.startswith(("0x", "0X")):
        raw = raw[2:]
    key = binascii.unhexlify("".join(c for c in raw if c in "0123456789abcdefABCDEF"))
    now = int(time.time())
    token = jwt.encode({"iat": now, "exp": now + 300}, key, algorithm="HS256")
    return token if isinstance(token, str) else token.decode()


def rpc_call(url: str, method: str, params: Any, jwt_token: str) -> dict:
    global next_id, rpc_log
    req_id = next_id; next_id += 1
    hdr = {
        "Content-Type":  "application/json",
        "Authorization": f"Bearer {jwt_token}",
    }
    body = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}
    resp = requests.post(url, headers=hdr, json=body, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    rpc_log.append({"url": url, "request": body, "response": data})
    return data


def load_batches() -> Dict[str, dict]:
    if not os.path.exists(BATCH_FILE):
        return {}
    try:
        raw = json.load(open(BATCH_FILE, "r", encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("batches file must be a JSON object keyed by batch index")
        # Ensure keys are strings of ints and values dicts
        out: Dict[str, dict] = {}
        for k, v in raw.items():
            out[str(int(k))] = dict(v)
        return out
    except Exception as e:
        print(f"[WARN] Failed to read/parse {BATCH_FILE}: {e}. Starting empty.", file=sys.stderr)
        return {}


def first_unprocessed(batches: Dict[str, dict]) -> tuple[str, dict]:
    """Return (key, item) for first batch where blockhash is falsy. Raise KeyError if none."""
    for k in sorted(batches, key=lambda x: int(x)):
        it = batches[k]
        if not it.get("blockhash"):
            return k, it
    raise KeyError("No pending batch to process")


def set_block_fields(item: dict, block_hash: str, block_number_int: int) -> None:
    item["blockhash"]   = block_hash
    item["blocknumber"] = int(block_number_int)


# --------------- Main ----------------

def parse_args(argv: List[str]) -> tuple[List[str], int]:
    """Return (endpoints, verbose_level) from argv.
       Usage: state_transition_main.py [-v|-vv] <host1:port> [host2:port ...]
    """
    v = 0
    eps: List[str] = []
    for a in argv:
        if a == "-v":
            v = max(v, 1)
        elif a == "-vv":
            v = max(v, 2)
        else:
            eps.append(a)
    return eps, v


def main() -> int:
    global VERBOSE_LEVEL

    if len(sys.argv) < 2:
        print("Usage: python3 state_transition_main.py [-v|-vv] <host1:port> [host2:port ...]")
        return 1

    arg_eps, VERBOSE_LEVEL = parse_args(sys.argv[1:])
    if not arg_eps:
        print("error: no endpoints provided")
        return 1

    ENDPOINTS = [f"http://{h}" for h in arg_eps]

    token = generate_jwt(JWT_SECRET_PATH)

    # === Bootstrap state file if missing ===
    if not os.path.exists(STATE_FILE):
        chain_res = rpc_call(ENDPOINTS[0], "eth_chainId", [], token)
        chain_id  = int(chain_res["result"], 16)
        g0        = rpc_call(ENDPOINTS[0], "eth_getBlockByNumber", ["0x0", False], token)
        genesis   = g0["result"]["hash"]
        atomic_write_json(STATE_FILE, {"chainId": chain_id, "genesisHash": genesis})
        dprint(1, f"[INFO] Initialized state: chainId={chain_id}, genesis={genesis}")

    # === Load batches (dict keyed by batch index) ===
    batches = load_batches()
    if not batches:
        print("No batches file or it is empty. Nothing to do.")
        return 0

    try:
        batch_key, item = first_unprocessed(batches)
    except KeyError:
        print("No pending batch to process.")
        return 0

    batch_number = int(batch_key)
    expected_txs = item.get("transactions") or []

    latest_block_number = int(rpc_call(ENDPOINTS[0], "eth_blockNumber", [], token)["result"], 16)
    if batch_number != latest_block_number:
        print(f"[INFO] Batch {batch_number} does not match current block number {latest_block_number}.")
        print("       Waiting for Nethermind to be at the same height. Exiting.")
        flush_logs_safely()
        return 1

    print(f"Processing batch #{batch_number} with {len(expected_txs)} txs...")

    zero32   = "0x" + "0"*64
    now_hex  = hex(int(time.time()))
    # Default feeRecipient
    feeRecipient = "0xE25583099BA105D9ec0A67f5Ae86D90e50036425"

    latest   = rpc_call(ENDPOINTS[0], "eth_getBlockByNumber", ["latest", False], token)
    head_hash = latest["result"]["hash"]

    for url in ENDPOINTS:
        entry: Dict[str, Any] = {}

        # 1) forkchoiceUpdatedV3
        fc_state = {
            "finalizedBlockHash": zero32,
            "headBlockHash":      head_hash,
            "safeBlockHash":      zero32,
        }
        fc_attr  = {
            "parentBeaconBlockRoot": zero32,
            "timestamp":             now_hex,
            "prevRandao":            zero32,
            "suggestedFeeRecipient": feeRecipient,
            "withdrawals":           [],
        }
        fc = rpc_call(url, "engine_forkchoiceUpdatedV3", [fc_state, fc_attr], token)
        entry["forkchoiceUpdatedV3"] = fc

        # payloadId
        pid = None
        if fc.get("result"):
            pid = fc["result"].get("payloadId") or fc["result"].get("payloadStatus", {}).get("payloadId")
        if not pid:
            entry["error"] = "no payloadId returned"
            pipeline_log[url] = entry
            continue

        # 2) getPayloadV4
        gp = rpc_call(url, "engine_getPayloadV4", [pid], token)
        entry["getPayloadV4"] = gp

        payload = gp.get("result", {})
        exec_p  = payload.get("executionPayload", {})
        actual_txs = exec_p.get("transactions", [])

        if VERBOSE_LEVEL >= 2:
            print("actual txs:", actual_txs)
            print("expected txs:", expected_txs)

        # 3) compare txs
        match = (actual_txs == expected_txs)
        entry["compare"] = {"expected_count": len(expected_txs), "actual_count": len(actual_txs), "match": match}
        if not match:
            pipeline_log[url] = entry
            flush_logs_safely()
            print(f"[ERROR] Batch {batch_number} TXs did not match execution payload on {url}.")
            return 1

        # 4) newPayloadV4
        np = rpc_call(url, "engine_newPayloadV4",
                      [exec_p,
                       payload.get("blobsBundle", {}).get("blobs", []),
                       zero32,
                       []],
                      token)
        entry["newPayloadV4"] = np

        res = np.get("result", {})
        status = res.get("status") or res.get("latestValidHash")
        if not status or status not in ("VALID", "ACCEPTED"):
            entry["newPayloadV4_error"] = res
            pipeline_log[url] = entry
            flush_logs_safely()
            print(f"[ERROR] newPayloadV4 was not VALID/ACCEPTED on {url}.")
            return 2

        block_hash   = exec_p["blockHash"]
        block_number = int(exec_p.get("blockNumber", hex(batch_number)), 16)

        # Record immediately
        set_block_fields(item, block_hash, block_number)
        batches[str(batch_number)] = item
        save_batches(batches)

        # 5) finalize head
        fc2_state = {
            "finalizedBlockHash": zero32,
            "headBlockHash":      block_hash,
            "safeBlockHash":      zero32,
        }
        fc2 = rpc_call(url, "engine_forkchoiceUpdatedV3", [fc2_state, None], token)
        entry["forkchoiceUpdatedV3_final"] = fc2

        pipeline_log[url] = entry

    # write full log
    flush_logs_safely()
    print(f"Batch {batch_number} processed. Logs → {LOG_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

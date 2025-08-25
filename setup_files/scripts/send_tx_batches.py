#!/usr/bin/env python3
import os
import time
import jwt
import binascii
import json
import requests
import sys

# === CONFIGURATION ===
JWT_SECRET_PATH = "chain_data/jwt-secret"
CHAIN_ID = 3151908
OUTPUT_DIR = "Output"
BATCH_FILE = os.path.join(OUTPUT_DIR, "transactions_batch.json")
RAW_TX_FILE = "valid_txs_part_1.txt"
MARKER_FILE = os.path.join(OUTPUT_DIR, "tx_marker.txt")
BATCH_SIZE = 5

if len(sys.argv) < 2:
    print("Usage: python3 send_tx_batches.py <host1:port> [host2:port …]")
    sys.exit(1)

ENDPOINTS = [f"http://{h}" for h in sys.argv[1:]]

# global counter for JSON-RPC ids
global_id = 1

def generate_jwt(path):
    raw = open(path).read().strip()
    if raw.startswith(("0x", "0X")):
        raw = raw[2:]
    key = binascii.unhexlify("".join(c for c in raw if c in "0123456789abcdefABCDEF"))
    now = int(time.time())
    token = jwt.encode({"iat": now, "exp": now + 300}, key, algorithm="HS256")
    return token if isinstance(token, str) else token.decode()

def rpc_call(url, method, params, token):
    global global_id
    req_id = global_id; global_id += 1
    hdr = {
      "Content-Type": "application/json",
      "Authorization": f"Bearer {token}"
    }
    body = {
      "jsonrpc": "2.0",
      "id":      req_id,
      "method":  method,
      "params":  params
    }
    r = requests.post(url, headers=hdr, json=body)
    r.raise_for_status()
    return r.json()

def load_batches():
    if os.path.exists(BATCH_FILE):
        try:
            with open(BATCH_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}

def save_batches(batches):
    os.makedirs(os.path.dirname(BATCH_FILE), exist_ok=True)
    with open(BATCH_FILE, "w") as f:
        json.dump(batches, f, indent=2)

def load_marker():
    if os.path.exists(MARKER_FILE):
        with open(MARKER_FILE, "r") as f:
            try:
                return int(f.read().strip())
            except ValueError:
                return 0
    return 0

def save_marker(count):
    os.makedirs(os.path.dirname(MARKER_FILE), exist_ok=True)
    with open(MARKER_FILE, "w") as f:
        f.write(str(count))

def main():
    token = generate_jwt(JWT_SECRET_PATH)

    # determine next batch number
    batches = load_batches()
    next_batch = max([int(k) for k in batches.keys()] + [0]) + 1

    # load transactions from input file
    with open(RAW_TX_FILE, "r") as f:
        raw_txs = ["0x" + line.strip().strip('"') for line in f if line.strip()]

    start_index = load_marker()
    end_index = start_index + BATCH_SIZE
    batch_txs = raw_txs[start_index:end_index]

    if not batch_txs:
        print("No more transactions to process.")
        return

    batch_key = str(next_batch)

    for j, raw_hex in enumerate(batch_txs):
        for url in ENDPOINTS:
            try:
                resp = rpc_call(url, "eth_sendRawTransaction", [raw_hex], token)
                result = resp.get("result") or resp.get("error")
                print(f"{url}  Tx {j+1} → {raw_hex[:20]}... | {result}")
            except Exception as e:
                print(f"Error sending tx {j+1} to {url}: {e}")

    # record batch
    batches[batch_key] = {
        "transactions": batch_txs,
        "blockHash": None
    }

    save_batches(batches)
    save_marker(end_index)
    print(f"Saved batch {batch_key} with {len(batch_txs)} txs to {BATCH_FILE}")

if __name__ == "__main__":
    main()

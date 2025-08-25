#!/usr/bin/env python3
import os
import time
import jwt
import binascii
import json
import requests
import sys
from typing import Dict

# === CONFIGURATION ===
JWT_SECRET_PATH = "chain_data/jwt-secret"
CHAIN_ID = 3151908
BATCH_FILE = "Output/transactions_batch2.json"
LOG_FILE = "Output/transition_log.json"
RETRY_LIMIT = 15
RETRY_DELAY = 5  # seconds between retries
POST_TX_SLEEP = 5  # seconds to wait after sending transactions before state transition

if len(sys.argv) < 2:
    print("Usage: python3 state_transition_with_retry.py <engine_host:port>")
    sys.exit(1)

ENGINE_URL = f"http://{sys.argv[1]}"

# global counter for JSON-RPC ids
global_id = 1

def generate_jwt(path):
    raw = open(path).read().strip()
    if raw.startswith("0x"):
        raw = raw[2:]
    key = binascii.unhexlify(raw)
    now = int(time.time())
    token = jwt.encode({"iat": now, "exp": now + 300}, key, algorithm="HS256")
    return token if isinstance(token, str) else token.decode()

def rpc_call(method, params, token):
    global global_id
    req_id = global_id; global_id += 1
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    body = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}
    print(f"  RPC Call → {method} | Params: {json.dumps(params)[:100]}...")
    resp = requests.post(ENGINE_URL, headers=headers, json=body)
    print(f"  RPC Response ← {method} | Status: {resp.status_code}")
    resp.raise_for_status()
    return resp.json()

def load_json(path) -> Dict:
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except Exception as e:
            print(f"  Error loading {path}: {e}")
    return {}

def save_json(data, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  Saved → {path}")

def all_txs_included(payload_result, batch_txs):
    included = payload_result.get("transactions", [])
    included_set = set(tx.lower() for tx in included)
    print(f"  Checking inclusion: {len(batch_txs)} txs vs payload {len(included)} txs")
    return all(tx.lower() in included_set for tx in batch_txs)

def get_latest_block_hash(token):
    resp = rpc_call("eth_getBlockByNumber", ["latest", False], token)
    block = resp.get("result")
    hash = block.get("hash") if block else None
    print(f"  Latest block hash → {hash}")
    return hash

def main():
    token = generate_jwt(JWT_SECRET_PATH)
    print("Initialized JWT Token")

    batches = load_json(BATCH_FILE)
    log = load_json(LOG_FILE)

    print(f"Loaded {len(batches)} batches to process")

    for key in sorted(batches.keys(), key=int):
        batch = batches[key]
        if batch.get("blockhash"):
            print(f"Skipping batch {key}, already processed")
            continue

        print(f"\n--- Processing batch {key} ---")
        batch_txs = batch.get("transactions", [])

        # 1) send all raw txs
        for tx in batch_txs:
            try:
                res = rpc_call("eth_sendRawTransaction", [tx], token)
                print(f"  Sent tx → {res.get('result') or res.get('error')}")
            except Exception as e:
                print(f"  Error sending tx: {e}")

        # wait before checking
        print(f"  Sleeping for {POST_TX_SLEEP}s before transition...")
        
        time.sleep(POST_TX_SLEEP)
        zero32 = "0x" + "0"*64
        feeRecipient = "0xE25583099BA105D9ec0A67f5Ae86D90e50036425"

        included = False
        for attempt in range(1, RETRY_LIMIT + 1):
            print(f"  Attempt {attempt}/{RETRY_LIMIT}")
            head_hash = get_latest_block_hash(token)
            if not head_hash:
                print("  No head block available, retrying...")
                time.sleep(RETRY_DELAY)
                continue

            # build forkchoice params
            # fc_state = {
            #     "headBlockHash": head_hash,
            #     "safeBlockHash": "0x" + "0"*64,
            #     "finalizedBlockHash": "0x" + "0"*64
            # }
            # 1) forkchoiceUpdatedV3
            fc_state = {"finalizedBlockHash": zero32,
                    "headBlockHash":      head_hash,
                    "safeBlockHash":      zero32}
            # fc_attr = {
            #     "timestamp": hex(int(time.time())),
            #     "prevRandao": "0x0",
            #     "suggestedFeeRecipient": "0x" + "0"*40,
            #     "withdrawals": []
            # }
            fc_attr  = {"parentBeaconBlockRoot": zero32,
                    "timestamp":hex(int(time.time())),
                    "prevRandao":zero32,
                    "suggestedFeeRecipient":feeRecipient,
                    "withdrawals":           []}

            fc_resp = rpc_call("engine_forkchoiceUpdatedV3", [fc_state, fc_attr], token)
            payload_id = fc_resp.get("result", {}).get("payloadId")
            print(f"  Forkchoice response payloadId → {payload_id}")

            if not payload_id:
                time.sleep(RETRY_DELAY)
                continue

            pl_resp = rpc_call("engine_getPayloadV4", [payload_id], token)
            payload = pl_resp.get("result", {})

            if all_txs_included(payload, batch_txs):
                print("  All txs included, submitting newPayloadV4...")
                np_resp = rpc_call("engine_newPayloadV4", [payload], token)
                status = np_resp.get("result", {}).get("status")
                print(f"  newPayloadV4 status → {status}")
                if status == "VALID":
                    block_hash = payload.get("blockHash")
                    block_number = int(payload.get("blockNumber", "0x0"), 16)
                    print(f"  Transition successful: block {block_number}, hash {block_hash}")

                    batch["blockhash"] = block_hash
                    batch["blocknumber"] = block_number
                    log[key] = {"batch": key, "block_hash": block_hash, "block_number": block_number}
                    save_json(log, LOG_FILE)
                    save_json(batches, BATCH_FILE)
                    included = True
                    break
                else:
                    print("  newPayloadV4 invalid, aborting attempts")
                    break
            else:
                print("  Not all txs found in payload, retrying...")
                time.sleep(RETRY_DELAY)

        if not included:
            print("  Inclusion failed after retries")

if __name__ == "__main__":
    main()

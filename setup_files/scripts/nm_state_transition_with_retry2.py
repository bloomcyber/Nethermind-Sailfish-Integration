#!/usr/bin/env python3
import os
import time
import jwt
import binascii
import json
import requests
import sys
from typing import Dict


# === USAGE & ARGUMENTS ===
if len(sys.argv) != 4:
    print("Usage: python3 nm_state_transition_with_retry2.py <batch_file> <log_file> <end_point>")
    sys.exit(1)

BATCH_FILE = sys.argv[1]
LOG_FILE = sys.argv[2]


# === CONFIGURATION ===
JWT_SECRET_PATH = "chain_data/jwt-secret"
CHAIN_ID = 3151908
#BATCH_FILE = "Output/transactions_batch.json"
#LOG_FILE = "Output/transition_log.json"
RETRY_LIMIT = 15
RETRY_DELAY = 5
POST_TX_SLEEP = 5

if len(sys.argv) < 2:
    print("Usage: python3 nm_state_transition_with_retry2.py <engine_host:port>")
    sys.exit(1)

ENGINE_URL = f"http://{sys.argv[3]}"

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
    print(f" \n RPC Call → {method} | Params: {json.dumps(params)}")
    resp = requests.post(ENGINE_URL, headers=headers, json=body)
    print(f"  RPC Response ← {method} | Status: {resp.status_code}")
    resp.raise_for_status()
    result = resp.json()
    print(f"  Response JSON: {json.dumps(result)}")
    return result

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

# def all_txs_included(payload_result, batch_txs):
#     included = payload_result.get("transactions", [])
#     included_set = set(tx.lower() for tx in included)
#     print(f"  Checking inclusion: {len(batch_txs)} txs vs payload {len(included)} txs")
#     return all(tx.lower() in included_set for tx in batch_txs)


# def all_txs_included(payload_result, batch_txs):
#     exec_payload = payload_result.get("executionPayload", {})
#     included = exec_payload.get("transactions", [])
#     included_set = set(tx.lower() for tx in included)
#     print(f"  Checking inclusion: {len(batch_txs)} txs vs payload {len(included)} txs")
#     return all(tx.lower() in included_set for tx in batch_txs)
def all_txs_exactly_match(payload_result, batch_txs):
    exec_payload = payload_result.get("executionPayload", {})
    included = exec_payload.get("transactions", [])

    included_set = set(tx.lower() for tx in included)
    batch_set = set(tx.lower() for tx in batch_txs)

    print(f"  Checking inclusion: expected {len(batch_set)} txs vs payload {len(included_set)} txs")

    if included_set != batch_set:
        extra = included_set - batch_set
        missing = batch_set - included_set
        if extra:
            print(f"   Extra txs in payload: {list(extra)[:2]}{'...' if len(extra) > 2 else ''}")
        if missing:
            print(f"   Missing txs in payload: {list(missing)[:2]}{'...' if len(missing) > 2 else ''}")
        return False

    print("  Payload matches exactly.")
    return True


def get_latest_block_hash(token):
    for retry in range(2):
        try:
            resp = rpc_call("eth_getBlockByNumber", ["latest", False], token)
            block = resp.get("result")
            hash = block.get("hash") if block else None
            print(f"  Latest block hash → {hash}")
            return hash
        except requests.exceptions.HTTPError as e:
                if e.response.status_code == 401:
                    print("  JWT expired during get_latest_block_hash. Refreshing token...")
                    token = generate_jwt(JWT_SECRET_PATH)
                else:
                    raise
    print("  Failed to get latest block hash even after refreshing token.")
    return None

    

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

        for tx in batch_txs:
            try:
                res = rpc_call("eth_sendRawTransaction", [tx], token)
                print(f"  Sent tx: {tx[:20]}... → {res.get('result') or res.get('error')}")
            except Exception as e:
                print(f"  Error sending tx: {e}")

        print(f"  Sleeping for {POST_TX_SLEEP}s before checking transition...")
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

            fc_state = {"finalizedBlockHash": zero32,
                        "headBlockHash": head_hash,
                        "safeBlockHash": zero32}
            fc_attr  = {"parentBeaconBlockRoot": zero32,
                        "timestamp": hex(int(time.time())),
                        "prevRandao": zero32,
                        "suggestedFeeRecipient": feeRecipient,
                        "withdrawals": []}

            try:
                fc_resp = rpc_call("engine_forkchoiceUpdatedV3", [fc_state, fc_attr], token)
                payload_id = fc_resp.get("result", {}).get("payloadId")
                print(f"  Forkchoice response payloadId → {payload_id}")
            except Exception as e:
                print(f"  RPC error during forkchoiceUpdatedV3: {e}")
                token = generate_jwt(JWT_SECRET_PATH)
                continue

            if not payload_id:
                time.sleep(RETRY_DELAY)
                continue

            try:
                pl_resp = rpc_call("engine_getPayloadV4", [payload_id], token)
                payload = pl_resp.get("result", {})
            except Exception as e:
                print(f"  RPC error during getPayloadV4: {e}")
                token = generate_jwt(JWT_SECRET_PATH)
                continue

            if all_txs_exactly_match(payload, batch_txs):
                print("  All txs included, submitting newPayloadV4...")
                try:
                    
                    execution_payload = payload.get("executionPayload", {})
                    blobs = payload.get("blobsBundle", {}).get("blobs", [])
                    parent_beacon_block_root = "0x" + "0"*64
                    execution_requests = payload.get("executionRequests", [])

                    params = [
                        execution_payload,
                        blobs,
                        parent_beacon_block_root,
                        execution_requests
                    ]

                    np_resp = rpc_call("engine_newPayloadV4", params, token)
                    
                    # np_resp = rpc_call("engine_newPayloadV4", [payload], token)
                    status = np_resp.get("result", {}).get("status")
                    print(f"  newPayloadV4 status → {status}")
                except Exception as e:
                    print(f"  RPC error during newPayloadV4: {e}")
                    token = generate_jwt(JWT_SECRET_PATH)
                    continue

                # if status == "VALID":
                if status and status in ("VALID", "ACCEPTED"):
                    block_hash = execution_payload.get("blockHash")
                    block_number = int(execution_payload.get("blockNumber", "0x0"), 16)
                    
                    # Finalize the new head
                    final_fc_state = {
                        "finalizedBlockHash": zero32,
                        "headBlockHash": block_hash,
                        "safeBlockHash": zero32
                    }
                    try:
                        fc_final = rpc_call("engine_forkchoiceUpdatedV3", [final_fc_state, None], token)
                        print(f"  Final forkchoiceUpdatedV3 sent to confirm head → {block_hash}")
                    except Exception as e:
                        print(f"  RPC error during final forkchoiceUpdatedV3: {e}")
                        token = generate_jwt(JWT_SECRET_PATH)
                        continue
                    
                    
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

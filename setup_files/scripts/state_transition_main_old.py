#!/usr/bin/env python3
import sys, os, time, json, binascii
import jwt, requests

# === CONFIGURATION ===
JWT_SECRET_PATH = "chain_data/jwt-secret"
OUTPUT_DIR       = "Output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

STATE_FILE      = os.path.join(OUTPUT_DIR, "state.json")
BATCH_FILE      = os.path.join(OUTPUT_DIR, "transactions_batch.json")
LOG_FILE        = os.path.join(OUTPUT_DIR, "transition_log.json")


if len(sys.argv) < 2:
    print("Usage: python3 state_transition.py <host1:port> [host2:port ...]")
    sys.exit(1)

ENDPOINTS = [f"http://{h}" for h in sys.argv[1:]]

# global JSON-RPC id & call log
global next_id, rpc_log
next_id = 1
rpc_log = []


def generate_jwt(path):
    raw = open(path).read().strip()
    if raw.startswith(("0x","0X")):
        raw = raw[2:]
    key = binascii.unhexlify("".join(c for c in raw if c in "0123456789abcdefABCDEF"))
    now = int(time.time())
    token = jwt.encode({"iat": now, "exp": now + 300}, key, algorithm="HS256")
    return token if isinstance(token, str) else token.decode()


def rpc_call(url, method, params, jwt_token):
    global next_id, rpc_log
    req_id = next_id; next_id += 1
    hdr = {
        "Content-Type":  "application/json",
        "Authorization": f"Bearer {jwt_token}"
    }
    body = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}
    resp = requests.post(url, headers=hdr, json=body)
    resp.raise_for_status()
    data = resp.json()
    rpc_log.append({"url": url, "request": body, "response": data})
    return data


def load_batches():
    if os.path.exists(BATCH_FILE):
        try:
            return json.load(open(BATCH_FILE))
        except:
            return {}
    return {}


def save_batches(batches):
    with open(BATCH_FILE, "w") as f:
        json.dump(batches, f, indent=2)


def main():
    token = generate_jwt(JWT_SECRET_PATH)

    # === Bootstrap state file if missing ===
    if not os.path.exists(STATE_FILE):
        # get chainId
        chain_res = rpc_call(ENDPOINTS[0], "eth_chainId", [], token)
        chain_id  = int(chain_res["result"], 16)
        # get genesis hash
        g0 = rpc_call(ENDPOINTS[0], "eth_getBlockByNumber", ["0x0", False], token)
        genesis = g0["result"]["hash"]
        json.dump({"chainId": chain_id, "genesisHash": genesis}, open(STATE_FILE, "w"), indent=2)
    state = json.load(open(STATE_FILE))

    # === Load pending batches ===
    batches = load_batches()
    # find the first unprocessed batch (blockHash is None)
    batch_key = None
    for k in sorted(batches, key=int):
        if not batches[k].get("blockHash"):
            batch_key = k
            break
    if batch_key is None:
        print("No pending batch to process.")
        sys.exit(0)

    
    latest_block_number = int(rpc_call(ENDPOINTS[0], "eth_blockNumber", [], token)["result"], 16)

    # One to one mapping of batches and blocks
    if int(batch_key,10) < latest_block_number:
        print("error: batch key less than block number")
        sys.exit(1)
    else :
        if int(batch_key,10) == latest_block_number:
            print(f"No new block since batch {batch_key} → {latest_block_number}")
            if batch_key is None:
                print("No pending batch to process.")
                sys.exit(0)
        else:
            print(f"New block! last batch {batch_key}, latest block {latest_block_number}")
            print("Proceeding with state transition...")
            # proceed with forkchoice→getPayload→newPayload etc.



    expected_txs = batches[batch_key]["transactions"]
    print(f"Processing batch {batch_key} with {len(expected_txs)} txs...")

    zero32 = "0x" + "0"*64
    now_hex = hex(int(time.time()))
    # Default feeRecipient
    feeRecipient = "0xE25583099BA105D9ec0A67f5Ae86D90e50036425"
    latest = rpc_call(ENDPOINTS[0], "eth_getBlockByNumber", ["latest", False], token)
    head_hash = latest["result"]["hash"]



    pipeline_log = {}
    for url in ENDPOINTS:
        entry = {}

        # 1) forkchoiceUpdatedV3
        fc_state = {"finalizedBlockHash": zero32,
                    "headBlockHash":      head_hash,
                    "safeBlockHash":      zero32}
        fc_attr  = {"parentBeaconBlockRoot": zero32,
                    "timestamp":             now_hex,
                    "prevRandao":            zero32,
                    "suggestedFeeRecipient": feeRecipient,
                    "withdrawals":           []}
        fc = rpc_call(url, "engine_forkchoiceUpdatedV3", [fc_state, fc_attr], token)
        entry["forkchoiceUpdatedV3"] = fc

        # extract payloadId from forkchoiceUpdatedV3
        pid = None
        if fc.get("result"):
            pid = fc["result"].get("payloadId") \
               or fc["result"].get("payloadStatus", {}).get("payloadId")

        if not pid:
            entry["error"] = "no payloadId returned"
        else:
            # 2) getPayloadV4 (Build a block)
            gp = rpc_call(url, "engine_getPayloadV4", [pid], token)
            entry["getPayloadV4"] = gp


            payload = gp.get("result", {})
            exec_p = payload.get("executionPayload", {})
            actual_txs = exec_p.get("transactions", [])

            # 3) compare with expected batch to ensure txs in batch and block are same
            match = (actual_txs == expected_txs)
            entry["compare"] = {"expected": expected_txs, "actual": actual_txs, "match": match}

            if not match:
                print(f"Batch {batch_key} TXs did not match execution payload on {url}.")
                # write full log\    
                with open(LOG_FILE, "w") as f:
                    json.dump({"rpcCalls": rpc_log, "pipeline": pipeline_log}, f, indent=2)
                sys.exit(1)
            else:
                # 4) newPayloadV4
                # params: [executionPayload, blobsBundle.blobs, safeHash, withdrawals]
                np = rpc_call(url, "engine_newPayloadV4", [exec_p,
                                                         payload.get("blobsBundle", {}).get("blobs", []),
                                                         zero32,
                                                         []], token)
                entry["newPayloadV4"] = np

                res = np.get("result", {})
                status = res.get("status") or res.get("latestValidHash")
                if status and status in ("VALID", "ACCEPTED"):
                    block_hash = exec_p["blockHash"]
                    # record blockHash against batch
                    batches[batch_key]["blockHash"] = block_hash
                    save_batches(batches)

                    # 5) finalize head
                    fc2_state = {"finalizedBlockHash": zero32,
                                 "headBlockHash":      block_hash,
                                 "safeBlockHash":      zero32}
                    fc2 = rpc_call(url, "engine_forkchoiceUpdatedV3", [fc2_state, None], token)
                    entry["forkchoiceUpdatedV3_final"] = fc2
                else:
                    entry["newPayloadV4_error"] = res

        pipeline_log[url] = entry

    # write full log\    
    with open(LOG_FILE, "w") as f:
        json.dump({"rpcCalls": rpc_log, "pipeline": pipeline_log}, f, indent=2)

    print(f"Batch {batch_key} processed. Logs → {LOG_FILE}")

if __name__ == "__main__":
    main()
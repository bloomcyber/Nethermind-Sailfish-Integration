#!/usr/bin/env python3
import os
import time
import jwt
import binascii
import json
import requests
from eth_account import Account
from bip_utils import Bip39SeedGenerator, Bip44, Bip44Coins, Bip44Changes
import sys

# === CONFIGURATION ===

MNEMONIC           = "giant issue aisle success illegal bike spike question tent bar rely arctic volcano long crawl hungry vocal artwork sniff fantasy very lucky have athlete"
JWT_SECRET_PATH    = "chain_data/jwt-secret"
# RPC_URL            = "http://127.0.0.1:8545"
CHAIN_ID           = 3151908
TRANSFER_VALUE_ETH = 0.001    # ETH per tx
GAS_LIMIT          = 21000
# BATCH_FILE         = "transactions_batch.json"
OUTPUT_DIR         = "Output"
BATCH_FILE         = os.path.join(OUTPUT_DIR, "transactions_batch.json")

if len(sys.argv) < 2:
    print("Usage: python3 raw2_batches_main.py <host1:port> [host2:port …]")
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
    # ensure the output directory exists
    os.makedirs(os.path.dirname(BATCH_FILE), exist_ok=True)
    with open(BATCH_FILE, "w") as f:
        json.dump(batches, f, indent=2)

def main():
    token = generate_jwt(JWT_SECRET_PATH)

    # determine next batch number
    batches = load_batches()
    if batches:
        next_batch = max(int(k) for k in batches.keys()) + 1
    else:
        next_batch = 1
    batch_key = str(next_batch)

    # derive accounts from mnemonic
    seed = Bip39SeedGenerator(MNEMONIC).Generate()
    bip44_def = Bip44.FromSeed(seed, Bip44Coins.ETHEREUM)

    # collect raw txs for this batch
    batch_txs = []

    # Example: send 5 transactions (customize as needed)
    for i in range(5):
        acct = bip44_def.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(i)
        priv = acct.PrivateKey().Raw().ToHex()
        sk = binascii.unhexlify(priv)
        sender = acct.PublicKey().ToAddress()
        nonce_res = rpc_call(ENDPOINTS[0],"eth_getTransactionCount", [sender, "pending"], token)
        nonce = int(nonce_res["result"], 16)

        tx = {
            "to": sender,  # send to self
            "value": hex(int(TRANSFER_VALUE_ETH * 1e18)),
            "gas": hex(GAS_LIMIT),
            "gasPrice": hex(int(rpc_call(ENDPOINTS[0],"eth_gasPrice", [], token)["result"], 16)),
            "nonce": hex(nonce),
            "chainId": CHAIN_ID
        }
        signed = Account.sign_transaction(tx, sk)
        raw_tx = signed.rawTransaction.hex()
        if raw_tx.startswith("0x") or raw_tx.startswith("0X"):
            raw_tx = raw_tx[2:]
        raw_hex = "0x" + raw_tx


        for url in ENDPOINTS:
            resp = rpc_call(url, "eth_sendRawTransaction", [raw_hex], token)
            result = resp.get("result") or resp.get("error")
            print(f"{url}  Tx {i+1} → {sender[:8]} | {result}")


        # # send the transaction
        # resp = rpc_call("eth_sendRawTransaction", [raw_hex], token)
        # result = resp.get("result") or resp.get("error")
        # print(f" Tx {i+1} → {sender[:8]} | {result}")

        # append to batch
        batch_txs.append(raw_hex)

    # record batch
    batches[batch_key] = {
        "transactions": batch_txs,
        "blockHash": None
    }
    save_batches(batches)
    print(f"Batch {batch_key} saved with {len(batch_txs)} transactions to {BATCH_FILE}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import argparse
import binascii
import json
import os
import time
import jwt
import requests
from eth_account import Account
from bip_utils import Bip39SeedGenerator, Bip44, Bip44Coins, Bip44Changes

# === CONFIGURATION ===
MNEMONIC = "giant issue aisle success illegal bike spike question tent bar rely arctic volcano long crawl hungry vocal artwork sniff fantasy very lucky have athlete"
CHAIN_ID = 3151908
TRANSFER_VALUE_ETH = 0.001
GAS_LIMIT = 21000
JWT_SECRET_PATH = "chain_data/jwt-secret"

# JSON-RPC global ID counter
global_id = 1

def generate_jwt(path):
    raw = open(path).read().strip()
    if raw.startswith("0x"):
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
        "id": req_id,
        "method": method,
        "params": params
    }
    r = requests.post(url, headers=hdr, json=body)
    r.raise_for_status()
    return r.json()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--account", type=int, required=True, help="Account index to use")
    parser.add_argument("--count", type=int, required=True, help="Number of txs to sign")
    parser.add_argument("--endpoint", type=str, required=True, help="Ethereum JSON-RPC endpoint")
    parser.add_argument("--path", type=str, required=True, help="Directory path for output file")
    args = parser.parse_args()

    token = generate_jwt(JWT_SECRET_PATH)

    seed = Bip39SeedGenerator(MNEMONIC).Generate()
    bip44 = Bip44.FromSeed(seed, Bip44Coins.ETHEREUM)
    acct = bip44.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(args.account)
    sender = acct.PublicKey().ToAddress()
    priv = acct.PrivateKey().Raw().ToHex()
    sk = binascii.unhexlify(priv)

    nonce_resp = rpc_call(args.endpoint, "eth_getTransactionCount", [sender, "pending"], token)
    nonce = int(nonce_resp["result"], 16)
    gas_price_resp = rpc_call(args.endpoint, "eth_gasPrice", [], token)
    gas_price = int(gas_price_resp["result"], 16)

    # Ensure the output directory exists
    os.makedirs(args.path, exist_ok=True)
    out_file = os.path.join(args.path, f"valid_tx_{args.account}.json")

    with open(out_file, "w") as f:
        for i in range(args.count):
            tx = {
                "to": sender,
                "value": hex(int(TRANSFER_VALUE_ETH * 1e18)),
                "gas": hex(GAS_LIMIT),
                "gasPrice": hex(gas_price),
                "nonce": hex(nonce + i),
                "chainId": CHAIN_ID
            }
            signed = Account.sign_transaction(tx, sk)
            raw_tx = signed.rawTransaction.hex()
            if raw_tx.startswith("0x"):
                raw_tx = raw_tx[2:]
            f.write(f"\"{raw_tx}\"\n")

    print(f"✔️  Wrote {args.count} signed txs to {out_file}")

if __name__ == "__main__":
    main()

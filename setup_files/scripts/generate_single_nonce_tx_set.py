#!/usr/bin/env python3
import os
import time
import jwt
import binascii
import json
import requests
from eth_account import Account
from bip_utils import Bip39SeedGenerator, Bip44, Bip44Coins, Bip44Changes

# === CONFIGURATION ===
MNEMONIC           = "giant issue aisle success illegal bike spike question tent bar rely arctic volcano long crawl hungry vocal artwork sniff fantasy very lucky have athlete"
JWT_SECRET_PATH    = "chain_data/jwt-secret"
CHAIN_ID           = 3151908
TRANSFER_VALUE_ETH = 0.001    # ETH per tx
GAS_LIMIT          = 21000
TOTAL_TXS          = 100_000
TXS_PER_FILE       = 25_000
OUTPUT_DIR         = "Output"

RPC_URL            = "http://127.0.0.1:8545"  # Replace if needed

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

def rpc_call(method, params, token):
    global global_id
    req_id = global_id; global_id += 1
    headers = {
      "Content-Type": "application/json",
      "Authorization": f"Bearer {token}"
    }
    body = {
      "jsonrpc": "2.0",
      "id":      req_id,
      "method":  method,
      "params":  params
    }
    r = requests.post(RPC_URL, headers=headers, json=body)
    r.raise_for_status()
    return r.json()

def main():
    token = generate_jwt(JWT_SECRET_PATH)
    gas_price = int(rpc_call("eth_gasPrice", [], token)["result"], 16)

    # derive accounts from mnemonic
    seed = Bip39SeedGenerator(MNEMONIC).Generate()
    bip44_def = Bip44.FromSeed(seed, Bip44Coins.ETHEREUM)

    # prepare output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    files = [open(os.path.join(OUTPUT_DIR, f"valid_txs_part_{i+1}.txt"), "w") for i in range(TOTAL_TXS // TXS_PER_FILE)]

    for i in range(TOTAL_TXS):
        acct = bip44_def.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(i)
        priv = acct.PrivateKey().Raw().ToHex()
        sk = binascii.unhexlify(priv)
        sender = acct.PublicKey().ToAddress()

        tx = {
            "to": sender,  # send to self
            "value": hex(int(TRANSFER_VALUE_ETH * 1e18)),
            "gas": hex(GAS_LIMIT),
            "gasPrice": hex(gas_price),
            "nonce": hex(0),
            "chainId": CHAIN_ID
        }
        signed = Account.sign_transaction(tx, sk)
        raw_tx = signed.rawTransaction.hex()
        if raw_tx.startswith("0x") or raw_tx.startswith("0X"):
            raw_tx = raw_tx[2:]

        f = files[i // TXS_PER_FILE]
        f.write(f"{raw_tx}\n")


        if (i+1) % 1000 == 0:
            print(f"Generated {i+1} transactions...")

    for f in files:
        f.close()

    print(f"Done. {TOTAL_TXS} transactions written across {len(files)} files.")

if __name__ == "__main__":
    main()
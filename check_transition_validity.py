#!/usr/bin/env python3
import sys
import time
import json
import binascii
import requests
import jwt

# === CONFIG ===
JWT_SECRET_PATH = "chain_data/jwt-secret"
POLL_INTERVAL   = 5  # seconds between checks

if len(sys.argv) < 2:
    print("Usage: python3 check_transition_validity.py <host1[:port]> [host2[:port] ...]")
    sys.exit(1)

ENDPOINTS = [f"http://{h}" for h in sys.argv[1:]]

def generate_jwt(path):
    raw = open(path).read().strip()
    if raw.startswith(("0x","0X")):
        raw = raw[2:]
    key = binascii.unhexlify("".join(c for c in raw if c in "0123456789abcdefABCDEF"))
    now = int(time.time())
    token = jwt.encode({"iat": now, "exp": now + 300}, key, algorithm="HS256")
    return token if isinstance(token, str) else token.decode()

def rpc_call(url, method, params, token):
    hdr = {
      "Content-Type":  "application/json",
      "Authorization": f"Bearer {token}"
    }
    body = {"jsonrpc":"2.0","id":1,"method":method,"params":params}
    r = requests.post(url, headers=hdr, json=body)
    r.raise_for_status()
    return r.json()

def check_consistency(token):
    block_nums = {}
    roots      = {}
    for url in ENDPOINTS:
        try:
            resp = rpc_call(url, "eth_getBlockByNumber", ["latest", False], token)
            res  = resp.get("result", {})
            num  = int(res.get("number","0x0"), 16)
            root = res.get("stateRoot")
            block_nums[url] = num
            roots[url]      = root
        except Exception as e:
            block_nums[url] = None
            roots[url]      = None
            print(f"  Error querying {url}: {e}")

    # compare block numbers
    nums = set(v for v in block_nums.values() if v is not None)
    if len(nums) != 1:
        print(" Block‐number mismatch:", block_nums)
        return False

    # compare state roots
    rs = set(roots.values())
    if len(rs) != 1:
        blk = nums.pop()
        print(f" State‐root divergence at block {blk}:", roots)
        return False

    # all good
    blk = nums.pop()
    rt  = roots[ENDPOINTS[0]]
    print(f" All nodes, at block {blk}, have matching stateRoot {rt}")
    return True

def main():
    token = generate_jwt(JWT_SECRET_PATH)
    print(f" Monitoring consistency across {len(ENDPOINTS)} endpoints every {POLL_INTERVAL}s…\n")
    while True:
        check_consistency(token)
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()

#!/usr/bin/env python3

import json
import glob
from collections import Counter, defaultdict

# --- Configuration ---
ordered_file_path = ".db-0/ordered_batches.json"
input_tx_files = sorted(glob.glob("valid_tx_*.json"))

# --- Step 1: Load input transactions from all valid_tx_*.json files ---
input_tx_to_origin = {}
print("📦 Indexing input transactions from:")
for file in input_tx_files:
    print(f"  🔍 {file}")
    with open(file, "r") as f:
        for lineno, line in enumerate(f, 1):
            tx = line.strip().strip('"')
            if not tx:
                continue
            if tx in input_tx_to_origin:
                print(f"⚠️  Duplicate in inputs: {tx} already from {input_tx_to_origin[tx]}")
            input_tx_to_origin[tx] = f"{file}:{lineno}"

print(f"\n📥 Indexed {len(input_tx_to_origin)} unique input transactions.\n")

# --- Step 2: Load ordered transactions from ordered_batches.json ---
ordered_txs = []
print(f"📦 Extracting transactions from {ordered_file_path}...")
with open(ordered_file_path, "r") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            ordered_txs.extend([tx.strip('"') for tx in obj.get("transactions", [])])
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON line: {line}")
            raise e

ordered_counter = Counter(ordered_txs)
print(f"📥 Found {len(ordered_txs)} transactions in ordered_batches.json\n")

# --- Step 3: Verify ---
fail = 0
print("🔍 Verifying each input transaction appears exactly ONCE in ordered batches...\n")
for tx, origin in input_tx_to_origin.items():
    count = ordered_counter.get(tx, 0)
    if count == 1:
        print(f"✅ {origin} — found exactly once")
    elif count == 0:
        print(f"❌ {origin} — NOT FOUND in ordered batches ❌")
        fail += 1
    else:
        print(f"⚠️  {origin} — appears {count} times (expected once) ⚠️")
        fail += 1

# --- Step 4: Extra check: ordered txs that were not in inputs ---
extra_txs = [tx for tx in ordered_txs if tx not in input_tx_to_origin]
if extra_txs:
    print(f"\n🚨 {len(extra_txs)} transactions found in ordered_batches.json that were NOT in any valid_tx_*.json file.")
    print("   Example:", extra_txs[:5])

# --- Final report ---
print("\n📊 Final Report")
print(f"🧾 Total input transactions checked: {len(input_tx_to_origin)}")
print(f"🧾 Total ordered transactions: {len(ordered_txs)}")
if fail == 0:
    print("🎉 All input transactions found exactly once in ordered batches!")
else:
    print(f"🚨 {fail} input transactions failed the check (missing or duplicated).")

# Exit with non-zero code if any failure
exit(1 if fail > 0 else 0)


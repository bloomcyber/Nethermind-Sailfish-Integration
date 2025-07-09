#!/usr/bin/env python3
import json
import rlp
from rlp.sedes import big_endian_int, Binary, binary
import sys

# Define a legacy Ethereum transaction class
class LegacyTransaction(rlp.Serializable):
    fields = [
        ("nonce", big_endian_int),
        ("gas_price", big_endian_int),
        ("gas_limit", big_endian_int),
        ("to", Binary.fixed_length(20, allow_empty=True)),
        ("value", big_endian_int),
        ("data", binary),
        ("v", big_endian_int),
        ("r", big_endian_int),
        ("s", big_endian_int)
    ]

input_file = ".db-0/ordered_batches.json"
output_file = "deserialized_ordered_batches.json"

def deserialize_tx(hex_str):
    raw_bytes = bytes.fromhex(hex_str.lstrip("0x"))
    tx = rlp.decode(raw_bytes, LegacyTransaction)
    return {
        "nonce": tx.nonce,
        "gasPrice": tx.gas_price,
        "gas": tx.gas_limit,
        "to": tx.to.hex() if tx.to else None,
        "value": tx.value,
        "data": tx.data.hex(),
        "v": tx.v,
        "r": tx.r,
        "s": tx.s
    }

def main():
    result = []
    with open(input_file, "r") as f:
        for line in f:
            if not line.strip():
                continue
            batch_entry = json.loads(line.strip())
            raw_txs = batch_entry["transactions"]
            deserialized = []
            for raw_tx in raw_txs:
                try:
                    tx_obj = deserialize_tx(raw_tx)
                    deserialized.append(tx_obj)
                except Exception as e:
                    print(f"⚠️ Error decoding tx: {raw_tx[:20]}... - {e}", file=sys.stderr)
                    deserialized.append({"error": "invalid_tx", "raw": raw_tx})
            batch_entry["transactions"] = deserialized
            result.append(batch_entry)

    with open(output_file, "w") as f_out:
        for entry in result:
            json.dump(entry, f_out)
            f_out.write("\n")

    print(f"✅ Deserialized output written to: {output_file}")

if __name__ == "__main__":
    main()


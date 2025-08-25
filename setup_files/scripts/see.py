import json
from eth_utils import decode_hex
from eth_account._utils.typed_transactions import TypedTransaction
from hexbytes import HexBytes
import rlp
from eth_rlp import transactions
from eth_keys import keys

def decode_legacy_tx(raw_bytes):
    tx = rlp.decode(raw_bytes, transactions.SignedTransaction)
    sender = tx.get_sender()
    return {
        "type": "Legacy",
        "from": sender,
        "to": tx.to,
        "nonce": tx.nonce,
        "gas": tx.gas,
        "gas_price": tx.gas_price,
        "value": tx.value,
        "data": tx.data.hex()
    }

with open("Output/txs_set.json") as f:
    txs = json.load(f)

for i, tx_hex in enumerate(txs):
    print(f"\n--- Transaction {i} ---")
    raw_bytes = decode_hex(tx_hex)

    try:
        # Try EIP-2718 typed transaction
        typed = TypedTransaction.from_bytes(HexBytes(raw_bytes))
        tx = typed.transaction
        print(f"Type: {typed.tx_type}")
        print(f"From: {tx.sender}")
        print(f"To: {tx.to}")
        print(f"Nonce: {tx.nonce}")
        print(f"Gas: {tx.gas}")
        print(f"Max Fee Per Gas: {getattr(tx, 'max_fee_per_gas', 'N/A')}")
        print(f"Max Priority Fee: {getattr(tx, 'max_priority_fee_per_gas', 'N/A')}")
        print(f"Value: {tx.value}")
        print(f"Data: {tx.data.hex()}")
    except Exception:
        try:
            # Fallback to legacy RLP-signed transaction
            legacy_info = decode_legacy_tx(raw_bytes)
            for k, v in legacy_info.items():
                print(f"{k}: {v}")
        except Exception as e:
            print(f"  ❌ Failed to decode tx: {e}")

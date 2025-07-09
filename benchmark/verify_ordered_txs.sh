#!/bin/bash

# Ensure script stops on error
set -e

# Input files
BATCH_FILE=".db-0/ordered_batches.json"
TX_FILES=("valid_tx_0.json" "valid_tx_1.json" "valid_tx_2.json" "valid_tx_3.json")

# Create a temporary working file
TMP_ALL_TXS=$(mktemp)

# Extract all txs from valid_tx_*.json into a flat list
echo "📦 Indexing transactions from valid_tx_*.json..."
for file in "${TX_FILES[@]}"; do
    jq -r .[] "$file"
done > "$TMP_ALL_TXS"

# Check each transaction from ordered_batches.json
echo "🔍 Verifying transactions in $BATCH_FILE..."

MISSING_COUNT=0
DUPLICATE_COUNT=0

# Extract all transactions from ordered_batches.json
jq -r '.transactions[]' "$BATCH_FILE" | while read -r tx; do
    count=$(grep -cF "$tx" "$TMP_ALL_TXS")

    if [[ $count -eq 0 ]]; then
        echo "❌ Missing: $tx"
        ((MISSING_COUNT++))
    elif [[ $count -gt 1 ]]; then
        echo "⚠️  Duplicate found: $tx appears $count times"
        ((DUPLICATE_COUNT++))
    fi
done

echo ""
echo "✅ Verification complete."
echo "Missing transactions:   $MISSING_COUNT"
echo "Duplicated transactions: $DUPLICATE_COUNT"

# Clean up
rm "$TMP_ALL_TXS"


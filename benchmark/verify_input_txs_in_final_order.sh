#!/bin/bash

set -euo pipefail

ORDERED_FILE=".db-0/ordered_batches.json"
TX_FILES=(valid_tx_*.json)

TMP_INPUT_TXS=$(mktemp)
TMP_ORDERED_TXS=$(mktemp)

echo "📦 Indexing input transactions from:"
for file in "${TX_FILES[@]}"; do
    echo "  🔍 $file"
    lineno=0
    while IFS= read -r tx || [[ -n "$tx" ]]; do
        ((lineno++))
        tx_clean=$(echo "$tx" | sed -e 's/^"//' -e 's/"$//' -e 's/^0x//')
        if [[ -n "$tx_clean" ]]; then
            echo "$tx_clean|$file:$lineno" >> "$TMP_INPUT_TXS"
        else
            echo "⚠️  Skipping empty/invalid line $lineno in $file"
        fi
    done < "$file"
done

input_count=$(wc -l < "$TMP_INPUT_TXS")
echo "📥 Indexed $input_count input transactions."

echo "📦 Extracting transactions from $ORDERED_FILE ..."
if ! jq -e . "$ORDERED_FILE" > /dev/null; then
    echo "❌ Invalid JSON in $ORDERED_FILE"
    exit 1
fi

jq -r '.transactions[]' "$ORDERED_FILE" | sed -e 's/^"//' -e 's/"$//' -e 's/^0x//' > "$TMP_ORDERED_TXS"
ordered_count=$(wc -l < "$TMP_ORDERED_TXS")
echo "📥 Found $ordered_count ordered transactions."

echo ""
echo "🔍 Verifying each input tx appears exactly ONCE in ordered batches..."
fail=0
total=0

while IFS="|" read -r tx origin; do
    ((total++))
    count=$(grep -Fc "$tx" "$TMP_ORDERED_TXS")
    if [[ "$count" -eq 1 ]]; then
        echo "✅ $origin — found exactly once"
    elif [[ "$count" -eq 0 ]]; then
        echo "❌ $origin — NOT FOUND in ordered batches ❌"
        fail=1
    else
        echo "⚠️  $origin — appears $count times (expected once) ⚠️"
        fail=1
    fi
done < "$TMP_INPUT_TXS"

echo ""
if [[ "$fail" -eq 0 ]]; then
    echo "🎉 All $total input transactions appear exactly once in ordered batches!"
else
    echo "🚨 Verification FAILED. Check logs above — some transactions are missing or duplicated."
    exit 1
fi

# Clean up
rm "$TMP_INPUT_TXS" "$TMP_ORDERED_TXS"


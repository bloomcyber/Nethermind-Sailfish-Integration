#!/bin/bash
set -e

ORDERED_FILE=".db-0/ordered_batches.json"
TX_FILES=(valid_tx_*.json)
TMP_ALL_TXS=$(mktemp)

echo "📦 Indexing transactions from valid_tx_*.json..."
for file in "${TX_FILES[@]}"; do
  while read -r tx; do
    clean_tx=$(echo "$tx" | tr -d '"')
    echo "$clean_tx|$file"
  done < "$file"
done > "$TMP_ALL_TXS"

echo "📑 Verifying transactions from $ORDERED_FILE..."
MISSING_COUNT=0
DUPLICATE_COUNT=0

grep '"transactions":' "$ORDERED_FILE" | sed 's/.*"transactions":\[\(.*\)\].*/\1/' | tr -d '",' | tr -s ' ' '\n' | while read -r tx; do
  matches=$(grep -F "$tx" "$TMP_ALL_TXS" || true)
  count=$(echo "$matches" | wc -l)
  if [[ "$count" -eq 0 ]]; then
    echo "❌ Missing tx: $tx"
    ((MISSING_COUNT++))
  elif [[ "$count" -gt 1 ]]; then
    echo "⚠️  Duplicate tx ($count files): $tx"
    echo "$matches"
    ((DUPLICATE_COUNT++))
  fi
done

echo ""
echo "✅ Done. Summary:"
echo "  ❌ Missing txs: $MISSING_COUNT"
echo "  ⚠️  Duplicates: $DUPLICATE_COUNT"
rm "$TMP_ALL_TXS"


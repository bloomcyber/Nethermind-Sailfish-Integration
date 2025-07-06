#!/bin/bash

set -e

DB_PATH=".db-0-0"
CLI="../target/debug/sailfish_batch_cli"
MAX_INDEX=1000

for i in $(seq 0 $MAX_INDEX); do
  echo "Checking batch at index $i..."
  output=$($CLI "$DB_PATH" "$i" --json 2>/dev/null || true)

  if [[ "$output" == *"\"txns\":"* ]]; then
    tx_count=$(echo "$output" | jq '.txns | length' 2>/dev/null || echo 0)
    if [[ "$tx_count" -gt 0 ]]; then
      echo "✅ Found batch with $tx_count transactions at index $i"
      echo "$output" | jq
      exit 0
    fi
  fi

  sleep 0.1
done

echo "❌ No non-empty batch found in the first $MAX_INDEX entries."


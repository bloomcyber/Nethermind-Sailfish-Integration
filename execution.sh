#!/usr/bin/env bash
set -uo pipefail

if [ $# -lt 2 ]; then
  echo "Usage: $0 <rounds> <endpoint1> [endpoint2 ...]" >&2
  exit 1
fi

ROUNDS=$1
# drop the first arg, collect the rest as endpoints
shift
ENDPOINTS=("$@")

echo "Running $ROUNDS rounds against endpoints: ${ENDPOINTS[*]}"


# URL="127.0.0.1:8545 127.0.0.1:8546 127.0.0.1:8547 127.0.0.1:8548"

for (( i=1; i<=ROUNDS; i++ )); do
  echo "=== Round $i of $ROUNDS ==="

  echo "--- sending batch (#$i) ---"
  python3 raw2_batches_main.py "${ENDPOINTS[@]}"
  if [ $? -ne 0 ]; then
    echo " raw2_batch_main.py failed on round $i"
    exit 1
  fi

  echo " sleeping 5s before applying transitions..."
  sleep 5

  echo "--- state transition (#$i) ---"
  python3 state_transition_with_retry.py "${ENDPOINTS[@]}"
  if [ $? -ne 0 ]; then
    echo " state_transition_with_retry.py failed on round $i"
    exit 1
  fi

  if [ $i -lt $ROUNDS ]; then
    echo " sleeping 3s before next round..."
    sleep 3
  fi
done

echo " All $ROUNDS rounds completed successfully."

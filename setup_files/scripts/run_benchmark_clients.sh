#!/bin/bash

set -e

mkdir -p logs
CLIENT=../target/debug/benchmark_client
BURST=$1
RATE=$2
WORKER_COUNT=1
PID_FILE=sailfish_benchmark_pids.txt

# Clean up any stale PID file from previous runs
if [[ -f $PID_FILE ]]; then
  echo "Removing stale PID file: $PID_FILE"
  rm $PID_FILE
fi



# Optional: pass --worker <count>
while [[ "$#" -gt 0 ]]; do
  case $1 in
    --worker)
      WORKER_COUNT=$2
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done

# Compute base ports for each worker per node
for ((wid=0; wid<WORKER_COUNT; wid++)); do
  for base in 3010 3020 3030 3040; do
    port=$((base + 4 + wid*3))
    echo "Starting client for port $port"
    $CLIENT 127.0.0.1:$port --size 512 --burst $BURST --rate $RATE > logs/client-$port.log 2>&1 &
    echo $! >> sailfish_benchmark_pids.txt
    sleep 0.5
  done
done

echo "Benchmark clients running. To stop them, run: xargs kill < sailfish_benchmark_pids.txt"

# Wait for user input to stop all
echo "All client nodes running. Type 'exit' and press Enter to stop them."
while read -r input; do
  if [[ "$input" == "exit" ]]; then
    echo "Stopping all sailfish benchmark client node processes..."
    xargs kill < sailfish_benchmark_pids.txt
    rm sailfish_benchmark_pids.txt
    break
  fi
  echo "Unrecognized input. Type 'exit' to stop."
done


#!/bin/bash

set -e

mkdir -p logs
CLIENT=../target/debug/benchmark_client
BURST=$1
RATE=$2

# Start benchmark clients
for port in 3014 3024 3034 3044; do
  echo "Starting client for port $port"
  $CLIENT 127.0.0.1:$port --size 512 --burst $BURST --rate $RATE > logs/client-$port.log 2>&1 &
  echo $! >> sailfish_benchmark_pids.txt
  sleep 0.5
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



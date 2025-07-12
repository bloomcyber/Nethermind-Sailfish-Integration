#!/bin/bash

# Exit on error
set -e

# Create log directory
mkdir -p logs

# Build paths
BIN=../target/debug/node
CLIENT=../target/debug/benchmark_client

# Launch Primaries
for i in 0 1 2 3; do
  echo "Starting primary node-$i"
  $BIN -vvv run \
    --keys .node-$i.json \
    --committee .committee.json \
    --store .db-$i \
    --parameters .parameters.json \
    primary > logs/primary-$i.log 2>&1 &
  sleep 0.5
done

# Launch Workers (worker 0 for each primary)
for i in 0 1 2 3; do
  echo "Starting worker-0 for node-$i"
  $BIN -vvv run \
    --keys .node-$i.json \
    --committee .committee.json \
    --store .db-$i-0 \
    --parameters .parameters.json \
    worker --id 0 > logs/worker-$i-0.log 2>&1 &
  sleep 0.5
done

# Launch Benchmark Clients
for port in 3014 3024 3034 3044; do
  echo "Starting client for port $port"
  $CLIENT 127.0.0.1:$port --size 512 --burst 5000 --rate 100 > logs/client-$port.log 2>&1 &
  sleep 0.5
done

# Wait for all background processes
wait


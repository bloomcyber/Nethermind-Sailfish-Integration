#!/bin/bash

set -e

mkdir -p logs
BIN=../target/release/node

BASE=/home/yuvaraj/newSailfish/network_config_files
PARAMETERS=$BASE/.dev_parameters.json
COMMITTEE=$BASE/.two_worker_committee.json



PID_FILE=sailfish_pids.txt

# Clean up any stale PID file from previous runs
if [[ -f $PID_FILE ]]; then
  echo "Removing stale PID file: $PID_FILE"
  rm $PID_FILE
fi


# Start primary nodes
for i in 0 1 2 3; do
  echo "Starting primary node-$i"
  $BIN -vvvv run \
    --keys $BASE/.node-$i.json \
    --committee $COMMITTEE \
    --store .db-$i \
    --parameters $PARAMETERS \
    primary > logs/primary-$i.log 2>&1 &
  echo $! >> sailfish_pids.txt
  sleep 0.5
done

# Start worker-0 for each primary
for i in 0 1 2 3; do
  echo "Starting worker-0 for node-$i"
  $BIN -vvvv run \
    --keys $BASE/.node-$i-0.json \
    --committee $COMMITTEE \
    --store .db-$i \
    --parameters $PARAMETERS \
    worker --id 0 > logs/worker-$i-0.log 2>&1 &
  echo $! >> sailfish_pids.txt
  sleep 0.5
done

# Start worker-1 for each primary
for i in 0 1 2 3; do
  echo "Starting worker-1 for node-$i"
  $BIN -vvvv run \
    --keys $BASE/.node-$i-1.json \
    --committee $COMMITTEE \
    --store .db-$i \
    --parameters $PARAMETERS \
    worker --id 1 > logs/worker-$i-1.log 2>&1 &
  echo $! >> sailfish_pids.txt
  sleep 0.5
done


# Wait for user input to stop all
echo "All nodes running. Type 'exit' and press Enter to stop them."
while read -r input; do
  if [[ "$input" == "exit" ]]; then
    echo "Stopping all sailfish node processes..."
    xargs kill < sailfish_pids.txt
    rm sailfish_pids.txt
    break
  fi
  echo "Unrecognized input. Type 'exit' to stop."
done


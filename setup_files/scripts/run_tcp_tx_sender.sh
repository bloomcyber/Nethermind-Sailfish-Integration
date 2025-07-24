#!/bin/bash

#set -e


BIN=../target/debug/tcp_tx_sender



PID_FILE=sender_pids.txt

# Clean up any stale PID file from previous runs
if [[ -f $PID_FILE ]]; then
  echo "Removing stale PID file: $PID_FILE"
  rm $PID_FILE
fi

# Start tx-sender for worker nodes
k=1
for i in 0 1 2 3; do
  echo "Starting Tx-Sender-0 for worker node-$i"
  ((k++))
  $BIN valid_tx_$i.json --addr 127.0.0.1:30$k4 --delay 500 &
  pid=$!
  wait $pid
  echo "Exit code for node-$i: $?"

  echo $pid >> sender_pids.txt

  sleep 0.5
done


# Wait for user input to stop all
echo "All tpc_tx_senders running. Type 'exit' and press Enter to stop them."
while read -r input; do
  if [[ "$input" == "exit" ]]; then
    echo "Stopping all senders"
    xargs kill < sender_pids.txt
    rm sender_pids.txt
    break
  fi
  echo "Unrecognized input. Type 'exit' to stop."
done


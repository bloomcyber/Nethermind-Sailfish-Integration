#!/bin/bash

set -e



#clean .db*
#rm -r .db*
mkdir -p Output/sailfish_logs
# mkdir -p Output
BIN=target/debug/node

BASE=setup_files/network_config_files
#PARAMETERS=$BASE/dev_parameters_try.json
PARAMETERS=$BASE/dev_parameters_try_new.json
 COMMITTEE=$BASE/two_worker_committee.json
#COMMITTEE=$BASE/committee.json
P_VERBOSITY=-vv
W_VERBOSITY=-vvv

PID_FILE=sailfish_pids.txt

# Clean up any stale PID file from previous runs
if [[ -f $PID_FILE ]]; then
  echo "Removing stale PID file: $PID_FILE"
  rm $PID_FILE
fi



for i in 0 1 2 3; do
  echo "Starting worker-0 for node-$i"
  $BIN $W_VERBOSITY run \
    --keys $BASE/node-$i.json \
    --committee $COMMITTEE \
    --store Output/.db-$i-0 \
    --parameters $PARAMETERS \
    worker --id 0  > Output/sailfish_logs/worker-$i-0.log  2>&1 &
  echo $! >> sailfish_pids.txt
  sleep 0.5

  echo "Starting worker-1 for node-$i"
   $BIN $W_VERBOSITY run \
     --keys $BASE/node-$i.json \
     --committee $COMMITTEE \
     --store Output/.db-$i-1 \
     --parameters $PARAMETERS \
     worker --id 1 > Output/sailfish_logs/worker-$i-1.log 2>&1 &
   echo $! >> sailfish_pids.txt
   sleep 0.5
  
  # Start primary node  
  echo "Starting primary node-$i"
  $BIN $P_VERBOSITY run \
    --keys $BASE/node-$i.json \
    --committee $COMMITTEE \
    --store Output/.db-$i \
    --parameters $PARAMETERS \
    primary > Output/sailfish_logs/primary-$i.log  2>&1 &
  echo $! >> sailfish_pids.txt

  # sleep 6000
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


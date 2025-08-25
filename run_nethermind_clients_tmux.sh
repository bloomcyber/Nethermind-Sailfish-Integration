#!/usr/bin/env bash

# run_nethermind_tmux.sh
# Launch four isolated Nethermind clients in a single tmux session
#
# Usage: chmod +x run_nethermind_tmux.sh && ./run_nethermind_tmux.sh

SESSION="isolated-nethermind"
BASE_DIR="$PWD"
CHAINSPEC="${BASE_DIR}/chain_data/chainspec_100000.json"
JWT="${BASE_DIR}/chain_data/jwt-secret"
OUTPUT_DIR="$BASE_DIR/Output"
mkdir -p "$OUTPUT_DIR"

# Kill existing session if any
tmux kill-session -t "$SESSION" 2>/dev/null

# Create new tmux session
tmux new-session -d -s "$SESSION"

for i in 1 2 3 4; do
  idx=$((i-1))
  RPC_PORT=$((8544 + i))
  ENGINE_PORT=$((8550 + i))
  METRICS_PORT=$((8007 + i))
  DATA_DIR="${OUTPUT_DIR}/node${idx}"
  IPC_SOCK="${OUTPUT_DIR}/node${idx}.ipc"
  WINDOW_NAME="node${i}"


  CMD="nethermind \
    --config none \
    --data-dir=\"$DATA_DIR\" \
    --Init.ChainSpecPath=\"$CHAINSPEC\" \
    --Init.BaseDbPath=\"node${idx}/db2\" \
    --JsonRpc.Enabled=true \
    --JsonRpc.Host=127.0.0.1 \
    --JsonRpc.Port=$RPC_PORT \
    --JsonRpc.EngineHost=0.0.0.0 \
    --JsonRpc.EnginePort=$ENGINE_PORT \
    --JsonRpc.IpcUnixDomainSocketPath=\"$IPC_SOCK\" \
    --JsonRpc.EnabledModules='[admin,client,debug,engine,eth,evm,health,net,personal,rpc,txpool,web3]' \
    --Mining.Enabled=false \
    --Init.IsMining=false \
    --Sync.NetworkingEnabled=false \
    --Init.DiscoveryEnabled=false \
    --Init.PeerManagerEnabled=false \
    --Network.StaticPeers=[] \
    --Metrics.Enabled=true \
    --Metrics.ExposePort=$METRICS_PORT \
    --HealthChecks.Enabled=false \
    --Network.P2PPort=0 \
    --JsonRpc.JwtSecretFile=\"$JWT\" \
    "
    # --log debug

  if [ "$i" -eq 1 ]; then
    tmux rename-window -t "$SESSION:0" "$WINDOW_NAME"
    tmux send-keys -t "$SESSION:0" "$CMD" C-m
  else
    tmux new-window -t "$SESSION" -n "$WINDOW_NAME"
    tmux send-keys -t "$SESSION:$WINDOW_NAME" "$CMD" C-m
  fi
done

# Select first window and attach
tmux select-window -t "$SESSION:node1"
tmux attach -t "$SESSION"

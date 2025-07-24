#!/bin/bash

SESSION="sailfish_tx_senders"
TX_SENDER_BIN="../target/debug/tcp_tx_sender"

# Clean up previous session
tmux kill-session -t $SESSION 2>/dev/null

# Start new session
tmux new-session -d -s $SESSION

# Define commands
declare -a cmds=(
  "$TX_SENDER_BIN valid_tx_0.json --addr 127.0.0.1:3014 --delay 1000"
  "$TX_SENDER_BIN valid_tx_1.json --addr 127.0.0.1:3024 --delay 1000"
  "$TX_SENDER_BIN valid_tx_2.json --addr 127.0.0.1:3034 --delay 1000"
  "$TX_SENDER_BIN valid_tx_3.json --addr 127.0.0.1:3044 --delay 1000"
)

# Run commands in tmux panes
tmux send-keys -t $SESSION "${cmds[0]}" C-m

for i in 1 2 3
do
  tmux split-window -t $SESSION
  tmux select-layout -t $SESSION tiled
  tmux send-keys -t $SESSION "${cmds[$i]}" C-m
done

# Attach to the session
tmux attach-session -t $SESSION

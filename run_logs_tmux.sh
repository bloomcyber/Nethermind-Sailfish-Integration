#!/bin/bash

# Usage: ./run_logs_tmux.sh <node-id>
# Example: ./run_logs_tmux.sh 0

if [ -z "$1" ]; then
  echo "Usage: $0 <node-id>"
  exit 1
fi

NODE="$1"
SESSION="logs-$NODE"

# Kill any existing session
tmux kill-session -t "$SESSION" 2>/dev/null

# Create a new session
tmux new-session -d -s "$SESSION"

# Pane 0: primary log
tmux send-keys -t "$SESSION:0.0" "tail -f logs/primary-$NODE.log" C-m

# Split pane horizontally (side by side)
tmux split-window -h -t "$SESSION:0.0"

# Pane 1: worker log
tmux send-keys -t "$SESSION:0.1" "tail -f logs/worker-$NODE-0.log" C-m

# Select the first pane
tmux select-pane -t "$SESSION:0.0"

# Attach to the session
tmux attach -t "$SESSION"

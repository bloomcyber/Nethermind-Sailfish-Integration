#!/usr/bin/env bash
# kill_nethermind.sh
# Gracefully stop isolated Nethermind tmux windows and kill the session

SESSION="isolated-nethermind"

# Send Ctrl-C to each pane to allow graceful shutdown
for idx in 0 1 2 3; do
  tmux send-keys -t "${SESSION}:${idx}" C-c
done


echo "Allowing processes to terminate smoothly"
# Allow processes a moment to terminate
sleep 10


# Kill the tmux session completely
tmux kill-session -t "${SESSION}"

echo "Session '${SESSION}' and its tmux panes have been terminated."

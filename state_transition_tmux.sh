#!/usr/bin/env bash
# state_transition_tmux.sh
# Launch 4 tmux windows to run nm_state_transition_with_retry3.py for 4 nodes
# Usage: ./state_transition_tmux.sh start | stop

SESSION="state_transition"
GRACE=10

start() {
    echo "Starting tmux session: $SESSION"

    tmux new-session -d -s "$SESSION" -n "node0" \
      "bash -c 'python3 nm_state_transition_with_retry3.py Output/transactions_batch_node_0.json Output/transition_log_node_0.json 127.0.0.1:8545; echo \"[node0 exited] Press Enter to close...\"; read'"

    tmux new-window -t "$SESSION" -n "node1" \
      "bash -c 'python3 nm_state_transition_with_retry3.py Output/transactions_batch_node_1.json Output/transition_log_node_1.json 127.0.0.1:8546; echo \"[node1 exited] Press Enter to close...\"; read'"

    tmux new-window -t "$SESSION" -n "node2" \
      "bash -c 'python3 nm_state_transition_with_retry3.py Output/transactions_batch_node_2.json Output/transition_log_node_2.json 127.0.0.1:8547; echo \"[node2 exited] Press Enter to close...\"; read'"

    tmux new-window -t "$SESSION" -n "node3" \
      "bash -c 'python3 nm_state_transition_with_retry3.py Output/transactions_batch_node_3.json Output/transition_log_node_3.json 127.0.0.1:8548; echo \"[node3 exited] Press Enter to close...\"; read'"

    tmux attach -t "$SESSION"
}

stop() {
    if ! tmux has-session -t "$SESSION" 2>/dev/null; then
        echo "No session '$SESSION' found."
        return
    fi

    echo "Sending Ctrl-C to all panes in '$SESSION'..."
    for win in $(tmux list-windows -t "$SESSION" -F "#{window_index}"); do
        for pane in $(tmux list-panes -t "$SESSION:$win" -F "#{pane_index}"); do
            tmux send-keys -t "$SESSION:$win.$pane" C-c
        done
    done

    echo "Waiting $GRACE seconds before killing session..."
    sleep $GRACE
    tmux kill-session -t "$SESSION"
    echo "Session '$SESSION' killed."
}

case "$1" in
  start) start ;;
  stop)  stop ;;
  *) echo "Usage: $0 {start|stop}" ;;
esac

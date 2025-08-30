#!/usr/bin/env bash
# ----------------------------------------------------------------
# extract_batches.sh
# Launch or stop a tmux session to extract batches for nodes 0-3
# Usage:
#   To start: ./extract_batches.sh start
#   To stop:  ./extract_batches.sh stop
# ----------------------------------------------------------------

SESSION="extract_batches"
GRACE_PERIOD=10  # seconds to wait after Ctrl-C before force kill

start() {
    echo "Starting tmux session '$SESSION'..."

    # Create a new tmux session in detached mode with window node0
    tmux new-session -d -s ${SESSION} -n node0
    tmux send-keys -t ${SESSION}:0 \
      "python3 extract_batches_from_ordered_certs.py \
        --input Output/.db-0/ordered_certificates.json \
        --output Output/transactions_batch_node_0.json \
        --sailfish-cli ./target/release/sailfish_batch_cli \
        --db Output/.db-0-0/ --db Output/.db-0-1 -vv" C-m

    # Window 1: node 1
    tmux new-window -t ${SESSION} -n node1
    tmux send-keys -t ${SESSION}:1 \
      "python3 extract_batches_from_ordered_certs.py \
        --input Output/.db-1/ordered_certificates.json \
        --output Output/transactions_batch_node_1.json \
        --sailfish-cli ./target/release/sailfish_batch_cli \
        --db Output/.db-1-0/ --db Output/.db-1-1 -vv" C-m

    # Window 2: node 2
    tmux new-window -t ${SESSION} -n node2
    tmux send-keys -t ${SESSION}:2 \
      "python3 extract_batches_from_ordered_certs.py \
        --input Output/.db-2/ordered_certificates.json \
        --output Output/transactions_batch_node_2.json \
        --sailfish-cli ./target/release/sailfish_batch_cli \
        --db Output/.db-2-0/ --db Output/.db-2-1 -vv" C-m

    # Window 3: node 3
    tmux new-window -t ${SESSION} -n node3
    tmux send-keys -t ${SESSION}:3 \
      "python3 extract_batches_from_ordered_certs.py \
        --input Output/.db-3/ordered_certificates.json \
        --output Output/transactions_batch_node_3.json \
        --sailfish-cli ./target/release/sailfish_batch_cli \
        --db Output/.db-3-0/ --db Output/.db-3-1 -vv" C-m

    # Attach to the session
    tmux select-window -t ${SESSION}:0
    tmux attach-session -t ${SESSION}
}

stop() {
    echo "Stopping tmux session '$SESSION' gracefully…"

    # Check session exists
    if ! tmux has-session -t "$SESSION" 2>/dev/null; then
        echo "No tmux session named '$SESSION' found."
        exit 0
    fi

    # Send Ctrl-C to each pane
    for win in $(tmux list-windows -t "$SESSION" -F '#{window_index}'); do
        panes=$(tmux list-panes -t "$SESSION:$win" -F '#{pane_index}')
        for pane in $panes; do
            echo " → Sending Ctrl-C to pane $SESSION:$win.$pane"
            tmux send-keys -t "$SESSION:$win.$pane" C-c
        done
    done

    echo "Waiting ${GRACE_PERIOD}s for processes to clean up…"
    sleep $GRACE_PERIOD

    # Kill session if it's still alive
    if tmux has-session -t "$SESSION" 2>/dev/null; then
        echo "Forcing tmux session '$SESSION' to exit."
        tmux kill-session -t "$SESSION"
    else
        echo "All panes exited cleanly; session is gone."
    fi
}

case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    *)
        echo "Usage: $0 {start|stop}"
        exit 1
        ;;
esac

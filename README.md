# Sailfish

This repo is forked from the repository https://github.com/nibeshrestha/sailfish.

## Quick Start


```
$ git clone https://github.com/bloomcyber/sailfish.git
$ cd sailfish/
$ pip install -r requirements.txt
```

Compile 
cargo build --features benchmark






#Run Sailfish 4 node network
/bin/bash run_nodes.sh

#Send rlp signed transactions in valid_txs file to the sailfish nodes for consensus
./run_tx_senders_tmux.sh

#Stop sending the transactions
tmux kill-session -t sailfish_tx_senders

#Check the final agreement of nodes on the final order.
sha256sum .db-0/ordered_certificates.json .db-1/ordered_certificates.json .db-2/ordered_certificates.json .db-3/ordered_certificates.json

b2816ed10d8580496326bd8ef45dd70941fc2415cf4e9b23d2307320100460dc  .db-0/ordered_certificates.json
b2816ed10d8580496326bd8ef45dd70941fc2415cf4e9b23d2307320100460dc  .db-1/ordered_certificates.json
b2816ed10d8580496326bd8ef45dd70941fc2415cf4e9b23d2307320100460dc  .db-2/ordered_certificates.json
b2816ed10d8580496326bd8ef45dd70941fc2415cf4e9b23d2307320100460dc  .db-3/ordered_certificates.json


#Optional
#tail primary and worker logs of node 0 or 1 or 2 or 3
script 0 
for node 0 , tmux for primary and worker











Isolated Nethermind Clients 
tmux script run using 



Python Scripts
state_transition.py
state_validity
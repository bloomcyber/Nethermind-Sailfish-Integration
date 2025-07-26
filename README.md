# Sailfish

This repository is forked from [nibeshrestha/sailfish](https://github.com/nibeshrestha/sailfish).

## Quick Start

Clone the repository and install Python dependencies:

```bash
git clone https://github.com/bloomcyber/sailfish.git
cd sailfish/
pip install -r requirements.txt
```

### Compile Rust Components

```bash
cargo build --features benchmark
```

## Running the Sailfish Network

###  Launch a 4-node Sailfish network

```bash
/bin/bash run_nodes.sh
```

###  Send RLP-signed transactions to Sailfish nodes

```bash
./run_tx_senders_tmux.sh
```

###  Stop sending transactions

```bash
tmux kill-session -t sailfish_tx_senders
```

###  Check final agreement (ordered certificate hashes)

```bash
sha256sum .db-0/ordered_certificates.json .db-1/ordered_certificates.json .db-2/ordered_certificates.json .db-3/ordered_certificates.json
```

Example output:

```
b2816ed10d8580496326bd8ef45dd70941fc2415cf4e9b23d2307320100460dc  .db-0/ordered_certificates.json
b2816ed10d8580496326bd8ef45dd70941fc2415cf4e9b23d2307320100460dc  .db-1/ordered_certificates.json
b2816ed10d8580496326bd8ef45dd70941fc2415cf4e9b23d2307320100460dc  .db-2/ordered_certificates.json
b2816ed10d8580496326bd8ef45dd70941fc2415cf4e9b23d2307320100460dc  .db-3/ordered_certificates.json
```

## Optional: Debugging Logs

To tail logs of a specific node (e.g., node-0):

```bash
script 0
```

Logs for primary and workers can be monitored using `tmux`.

---

## Isolated Nethermind Clients

A tmux script is provided for launching isolated Nethermind clients. Refer to the appropriate shell script for details.

---

## Python Scripts

- `state_transition.py`: Verifies batch to block consistency using Engine API.
- `state_validity.py`: Additional validity checks and state evaluation.

---

Feel free to contribute or report issues!

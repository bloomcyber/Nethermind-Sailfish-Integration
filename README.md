
# Sailfish [Documentation not yet completed]

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

### Get Nethermind Binary
The codebase uses nethermind client version 1.31.11
get the nethermind 1.31.11 from https://github.com/NethermindEth/nethermind/releases/tag/1.31.11 and place it under Nethermind folder. 
The code assumes the nethermind binary is present in the Working_directory/Nethermind/ folder and the folder should look like below 

Nethermind 
nethermind
configs

```
ls Nethermind/
configs  Data  logs  nethermind  nethermind-cli  Nethermind.Runner  nethermind.staticwebassets.endpoints.json  NLog.config  plugins
```

```
Nethermind/nethermind --version
Version:    1.31.11+2be1890e
Commit:     2be1890ee4f21f921a471de058dcb57937bd9b90
Build date: 2025-05-22 08:48:38Z
Runtime:    .NET 9.0.5
Platform:   Linux x64
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




python3 extract_batches_from_ordered_certs.py --input Output/.db-0/ordered_certificates.json --output Output/.db-0/ordered_batches_nm.json --sailfish-cli target/debug/sailfish_batch_cli --db Output/.db-0-0/ --retry-interval 5.0 --max-retries 120 -v
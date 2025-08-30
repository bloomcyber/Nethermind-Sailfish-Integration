# Sailfish ↔ Nethermind (Design 1 PoC)

This repository integrates the **Sailfish** consensus with **Nethermind** execution.

- We send Ethereum-compatible (RLP-signed) transactions to **Sailfish worker** nodes.
- Workers assemble transactions into batches and send digests to **primary** components.
- Primaries across nodes run Sailfish to agree on a **global order of batches**.
- We extract the ordered transactions and **execute** them in **isolated Nethermind clients** (no p2p/gossip).
- Since all nodes agree on the order, the **final state** in their Nethermind clients converges.

## Credits

- Sailfish consensus is forked from [nibeshrestha/sailfish](https://github.com/nibeshrestha/sailfish).
- Work done during my Nethermind internship under the guidance of **Stefano De Angelis**.

---

## Quick Start

Clone the repository and install Python dependencies:

```bash
git clone https://github.com/bloomcyber/Nethermind-Sailfish-Integration.git
cd Nethermind-Sailfish-Integration
pip install -r requirements.txt
```
- Note: Python 3.8.10 is used. Higher versions may require changes in the python files.

### Compile Rust Components

```bash
cargo build --features benchmark --release
```

### Get Nethermind Binary

This PoC uses Nethermind **v1.31.11** (assumed installed or on PATH):  
https://github.com/NethermindEth/nethermind/releases/tag/1.31.11

```
nethermind --version
Version:    1.31.11+2be1890e
Commit:     2be1890ee4f21f921a471de058dcb57937bd9b90
Build date: 2025-05-22 08:48:38Z
Runtime:    .NET 9.0.5
Platform:   Linux x64
```

---

## Launch a 4-node Sailfish network

Start the network with:

```bash
/bin/bash run_nodes.sh
```

This script launches **4 Sailfish nodes**, where each node consists of:

- **1 Primary** — participates in the Sailfish consensus algorithm to agree on the global order of batches.  
- **2 Workers** — build batches from received transactions and forward their batch digests to the primary.

Logs for each component are stored under `Output/sailfish_logs/`:

```bash
ls Output/sailfish_logs/
primary-0.log  primary-1.log  primary-2.log  primary-3.log  
worker-0-0.log worker-0-1.log  
worker-1-0.log worker-1-1.log  
worker-2-0.log worker-2-1.log  
worker-3-0.log worker-3-1.log
```

Node databases are stored under the `Output/` directory (hidden by default):

- **Primary databases:** `.db-x` (e.g., `.db-0`, `.db-1`, `.db-2`, `.db-3`)  
- **Worker databases:** `.db-x-0`, `.db-x-1` (e.g., `.db-0-0`, `.db-0-1`)  

---

## Send RLP-signed transactions to Sailfish worker nodes

Start the transaction senders:

```bash
./run_tx_senders_tmux.sh
```

This script opens a **tmux session** with multiple panes. Each pane runs a transaction sender that:

- Sends **EVM-compatible transactions** to the worker components of Sailfish nodes.  
- Reads its transactions from `setup_files/valid_txs/valid_txs_part_<x>_quoted.txt`, where `<x>` is the Sailfish node index.  
- Uses a **different transaction set for each node**, ensuring coverage across the network.  

> See the [Valid transaction generation](#valid-transaction-generation) section for details on how these transactions are created.

### Observing execution

- **Worker logs** show the building of batches from incoming transactions.  
- **Primary logs** reflect the commit and ordering of these (non-empty) batches.  

### Ordered certificates

The globally agreed order of batches is stored in each primary’s database:

```
.db-x/ordered_certificates.json
```

Notes:

- Some batches may be **empty** (no transactions).  
- Some batches may appear **missing** transactions — primaries only receive the **batch digest**; transactions are later fetched from the workers’ databases.  

### Verify agreement across primaries

Check that all primaries agree on the same ordered certificates:

```bash
sha256sum .db-0/ordered_certificates.json .db-1/ordered_certificates.json .db-2/ordered_certificates.json .db-3/ordered_certificates.json
```

Example output (all hashes match):

```
b2816ed10d8580496326bd8ef45dd70941fc2415cf4e9b23d2307320100460dc  .db-0/ordered_certificates.json
b2816ed10d8580496326bd8ef45dd70941fc2415cf4e9b23d2307320100460dc  .db-1/ordered_certificates.json
b2816ed10d8580496326bd8ef45dd70941fc2415cf4e9b23d2307320100460dc  .db-2/ordered_certificates.json
b2816ed10d8580496326bd8ef45dd70941fc2415cf4e9b23d2307320100460dc  .db-3/ordered_certificates.json
```

---

## Extract ordered batches

Start extracting batches:

```bash
./extract_batches_tmux.sh start
```

The extractor reads the ordered batches from `.db-x/ordered_certificates.json`, fetches transactions from the worker directories `.db-x-0` and `.db-x-1`, and creates `Output/transactions_batch_node_<x>.json`.

Example snippet:

```bash
head -n 24 Output/transactions_batch_node_0.json 
{
  "0": {
    "cert_id": "JFgPAakDBuSp0X2bo1vNptd++KzuVi8YRxfZ3lEd8ws=",
    "round": 49,
    "author": "XSrQJ5NUFy7r+1R1",
    "batch_digest": "mqcmuHgHzzJZrTcFIGXWChJy4PA8RHkyfS0u3BufU3M=",
    "transactions": [
      "0xf86d8084...d76f9",
      "0xf86d8084...1c27e"
    ],
    "blockhash": null,
    "blocknumber": -1
  },
  "1": {
    "cert_id": "PvsL0NlONCllvF3ibOJK69g1lVyjOiE+Q6blLFkSPU8=",
    "round": 49,
    "author": "tp/ADzF/k6Y9IEtH",
    "batch_digest": "Brv2T9bz0lkZ4MB5hWoXWt4FkRePboPOWiq8jg7I2Q8=",
    "transactions": [
      "0xf86d8084...8897d"
    ],
    "blockhash": null,
    "blocknumber": -1
  },
}
```

---

## Run isolated Nethermind clients

Start the four Nethermind clients (one per node):

```bash
./run_nethermind_clients_tmux.sh
```

This command starts a tmux session titled `isolated-nethermind` with **four panes**. Each pane runs a Nethermind client. All clients use the genesis and JWT files in the `chain_data/` directory.  
Client data directories are under `Output/node-<x>/`.

> Wait for the Nethermind clients to fully boot before proceeding.

---

## Drive state transitions

Guide each Nethermind client through state transitions using the Engine API:

```bash
./state_transition_tmux.sh start
```

- The script processes `Output/transactions_batch_node_<x>.json` **batch-by-batch**.
- After each batch is turned into a block, the script updates `blockhash` and `blocknumber` in the corresponding JSON.

Example (after execution):

```bash
head -n 24 Output/transactions_batch_node_0.json 
{
  "0": {
    "cert_id": "JFgPAakDBuSp0X2bo1vNptd++KzuVi8YRxfZ3lEd8ws=",
    "round": 49,
    "author": "XSrQJ5NUFy7r+1R1",
    "batch_digest": "mqcmuHgHzzJZrTcFIGXWChJy4PA8RHkyfS0u3BufU3M=",
    "transactions": [
      "0xf86d8084...d76f9",
      "0xf86d8084...1c27e"
    ],
    "blockhash": "0xd483463ad555e3a445abed6d2a957eff5a4c802cb7cc2903c970819cb045ee40",
    "blocknumber": 1
  },
  "1": {
    "cert_id": "PvsL0NlONCllvF3ibOJK69g1lVyjOiE+Q6blLFkSPU8=",
    "round": 49,
    "author": "tp/ADzF/k6Y9IEtH",
    "batch_digest": "Brv2T9bz0lkZ4MB5hWoXWt4FkRePboPOWiq8jg7I2Q8=",
    "transactions": [
      "0xf86d8084...8897d"
    ],
    "blockhash": "0xf3dc265916a2c7280da545cf4e93a19b4c9c05d166136441bdc67cb96ed728c0",
    "blocknumber": 2
  },
}
```

The script also writes a concise log per node, e.g. `Output/transition_log_node_0.json`:

```bash
head -n 11 Output/transition_log_node_0.json 
{
  "0": { "batch": "0", "block_hash": "0xd483463ad555e3a445abed6d2a957eff5a4c802cb7cc2903c970819cb045ee40", "block_number": 1 },
  "1": { "batch": "1", "block_hash": "0xf3dc265916a2c7280da545cf4e93a19b4c9c05d166136441bdc67cb96ed728c0", "block_number": 2 }
}
```

**State agreement check** (all nodes agree on the same block hashes/numbers for each batch index):

```bash
head -n 11 Output/transition_log_node_0.json 
head -n 11 Output/transition_log_node_1.json 
head -n 11 Output/transition_log_node_2.json 
head -n 11 Output/transition_log_node_3.json 
```

To stop the above scripts:

```bash
./state_transition_tmux.sh stop
./extract_batches_tmux.sh stop
./stop_nethermind_tmux.sh
tmux kill-session -t sailfish_tx_senders
```

To stop the 4 Sailfish nodes, type `exit` in the Sailfish tmux pane.

---

## Valid transaction generation

For this PoC, transactions are designed to be *valid by construction*. By “valid,” we mean that:

- No duplicate transactions are sent.
- Nonces are always correct and in-order.
- Every transaction can be executed independently, without waiting on missing nonces.

To guarantee this, we pre-generate **100,000 accounts**, each producing exactly **one transaction**.  
All of these accounts are included in `chain_data/chainspec.json` so that Nethermind recognizes them from genesis.

In short, using 100,000 single-use accounts allows us to **focus on testing Sailfish ordering and Nethermind execution determinism**, without introducing complications from nonce management. This is a conscious simplification/limitation of this PoC.

---

## Repository layout

```text
.
├── chain_data/                         # genesis, JWT, and chainspec files
├── Output/
│   ├── sailfish_logs/                  # logs from primaries and workers
│   ├── node-{0..3}/                    # Nethermind datadirs (one per node)
│   ├── .db-{0..3}/                     # Sailfish primary databases
│   ├── .db-*-{0,1}/                    # Sailfish worker databases
│   ├── transactions_batch_node_*.json  # extracted ordered batches
│   └── transition_log_node_*.json      # per-node execution logs
├── setup_files/
│   └── valid_txs/                      # pre-generated valid tx sets
├── run_nodes.sh                        # launch 4-node Sailfish network
├── run_tx_senders_tmux.sh              # send RLP-signed transactions
├── extract_batches_tmux.sh             # extract ordered batches
├── run_nethermind_clients_tmux.sh      # start isolated Nethermind clients
├── state_transition_tmux.sh            # drive state transitions via Engine API
└── stop_nethermind_tmux.sh             # stop Nethermind clients cleanly
```

---

## Contributing

Feel free to open issues or pull requests. Contributions are welcome!

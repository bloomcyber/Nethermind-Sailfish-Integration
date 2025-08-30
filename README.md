
# Sailfish
This repository tries to integrate the Sailfish consensus with the nethermind client execution. We send ethereum compatible transactions to the Sailfish workers node. The worker nodes process them into batches and send to the respective primary components. The primary components of different nodes agree on the order of the transactions based on the Sailfish consensus. We extract the ordered transactions and execute them in the isolated nethermind clients. Since all the nodes agree on the order , all the nodes achieve on the same final state in their nethermind clients. 

Credits
The sailfish consensus is forked from [nibeshrestha/sailfish](https://github.com/nibeshrestha/sailfish). 
Work done during my Nethermind internship under the guidance of Stefano De Angelis.


## Quick Start

Clone the repository and install Python dependencies:

```bash
git clone https://github.com/bloomcyber/sailfish.git
cd sailfish/
pip install -r requirements.txt

```
## Compile Rust Components

```bash
cargo build --features benchmark --release
```

## Get Nethermind Binary
The codebase uses nethermind client version 1.31.11 from https://github.com/NethermindEth/nethermind/releases/tag/1.31.11.
The code assumes the nethermind binary is installed.

```
Nethermind-Sailfish-Integration/nethermind --version
Version:    1.31.11+2be1890e
Commit:     2be1890ee4f21f921a471de058dcb57937bd9b90
Build date: 2025-05-22 08:48:38Z
Runtime:    .NET 9.0.5
Platform:   Linux x64
```


##  Launch a 4-node Sailfish network

```bash
/bin/bash run_nodes.sh
```
The above script starts 4 sailfish nodes. Each node comprises of 1 primary and 2 worker components. The workers build batches out of received transactions and the primaries participate in sailfish consensus algorithm to agree on the order of batches among multiple sailfish nodes. The logs of the primary and the worker components can be seen in the Output/sailfish_nodes directory.  The primary logs are named as primary-x.log and its respective workers logs as worker-x-0.log, worker-x-1.log.

```bash
ls Output/sailfish_logs/
primary-0.log  primary-1.log  primary-2.log  primary-3.log  worker-0-0.log  worker-0-1.log  worker-1-0.log  worker-1-1.log  worker-2-0.log  worker-2-1.log  worker-3-0.log  worker-3-1.log

```

The directories of the Sailfish nodes are in the Output directory and are hidden. The primary node databases are named as .db-x and the worker nodes database are .db-x-0 and .db-x-1.
###  Send RLP-signed transactions to Sailfish Worker nodes

```bash
./run_tx_senders_tmux.sh
```
The above script starts a tmux session with multiple panes. Each pane consists of a transaction sender which sends evm compatible transactions to the worker components in the sailfish nodes. The transactions are read from the setup_files/valid_txs/valid_txs_part_x_quoted.txt file, where x is the sailfish node index. We send different set of transactions to each node. The transactions are valid. See the transaction generation section for further information about this transaction set. 

When the transactions are being sent, the building of batches can be observed in the worker logs. The primary logs reflect the commit and ordering of these batches which are non empty.

The agreed order of batches can be found in the db-x/ordered_certificates.json file of each primary. The transactions in each batch can be either empty or missing. IN the former case, it is due to empty batches and in the later the transactions has to be fetched from the workers database as the workers only send the batch hash to the primary. We extract the transactions for the ordered batches later. To check the agreement of the ordered batches , we can run the below command.

Check final agreement (ordered certificate hashes)

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

We now derive ordered batches of transactions from each file to prepare for execution in a nethermind client. To start the extraction, we run the below script.

```bash
./extract_batches_tmux.sh start
```

The script reads the ordered batches from .db-x-0/ordered_certificates.json and fetches the transactions from the worker directories .db-x-0 and .db-x-1 and creates Output/transactions_batch_node_x.json file. A sample batch in the file looks as shown below.

```bash
head -n 24 Output/transactions_batch_node_0.json 
{
  "0": {
    "cert_id": "JFgPAakDBuSp0X2bo1vNptd++KzuVi8YRxfZ3lEd8ws=",
    "round": 49,
    "author": "XSrQJ5NUFy7r+1R1",
    "batch_digest": "mqcmuHgHzzJZrTcFIGXWChJy4PA8RHkyfS0u3BufU3M=",
    "transactions": [
      "0xf86d80844190ab018252089456bddb0c1fe0f64c7ad5843cb725f2b34a4fbf3c87038d7ea4c68000808360306ba0d7f5a8473072313f2b8bb3aee7116bc20b5add524d6f9cde16eae46056eefac4a03a2408a4425bed994f77b96e307c2de75679a97c110deda06562a18af48d76f9",
      "0xf86d80844190ab018252089412fe8e71aef801be2ce13d22b10d546352631d5487038d7ea4c68000808360306ca0cfa04950427bde5e9390a84d40b4464745a8422de00a52d3d364b4c55346e948a007bff38803e7165188bd46de4e4e74af2204656574350b302dc76a42ca11c27e"
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
      "0xf86d80844190ab0182520894952672c87f1aa6f23ffe29e49e98edb092c1fa0987038d7ea4c68000808360306ca0ad73848edf57540086881fae145be0efb424cc2b66b3987774a9379a1dcdb237a01984ddc6a204991b02faa60d18c0a746d7a5ebad04458352f27c25840118897d"
    ],
    "blockhash": null,
    "blocknumber": -1
  },

```

We store the blockhash and the blocknumber fields once we process each batch in the nethermind client. Next we proceed to the state transition of the isolated nethermind clients. We use nethermind client for execution of these batches. We run 4 nethermind clients corresponding to each ordered_certificates file and these clients only does state transition and all the other functionalities like gossipping, peer discovery etc. are suppressed. To start the 4 nethermind clients, we run the below command.

```bash 
./run_nethermind_clients_tmux.sh
```

The above command starts a tmux session titled "isolated-nethermind" with four panes. Each pane consists of a nethermind client. All the clients use the genesis and jwt files in the chain_data directory. The nethermind client has its data in Output/node-x directory.  Wait for the nethermind clients to boot. Upon successful start of the nethermind clients, we proceed to send the transactions in the extracted batches in the Output/transactions_batch_node_x.json file to the respective nethermind client by running the below script.


```bash
./state_transition_tmux.sh start
```

This script fetches the transactions batch wise and guides the nethermind client through state transition using the engine api calls like consensus clients (eg: Prysm). After the successful transition of each batch to a block in the nethermind client, the blockhash and the block number fields gets updated in the Output/transactions_batch_node_x.json file as shown below. 

```bash
head -n 24 Output/transactions_batch_node_0.json 
{
  "0": {
    "cert_id": "JFgPAakDBuSp0X2bo1vNptd++KzuVi8YRxfZ3lEd8ws=",
    "round": 49,
    "author": "XSrQJ5NUFy7r+1R1",
    "batch_digest": "mqcmuHgHzzJZrTcFIGXWChJy4PA8RHkyfS0u3BufU3M=",
    "transactions": [
      "0xf86d80844190ab018252089456bddb0c1fe0f64c7ad5843cb725f2b34a4fbf3c87038d7ea4c68000808360306ba0d7f5a8473072313f2b8bb3aee7116bc20b5add524d6f9cde16eae46056eefac4a03a2408a4425bed994f77b96e307c2de75679a97c110deda06562a18af48d76f9",
      "0xf86d80844190ab018252089412fe8e71aef801be2ce13d22b10d546352631d5487038d7ea4c68000808360306ca0cfa04950427bde5e9390a84d40b4464745a8422de00a52d3d364b4c55346e948a007bff38803e7165188bd46de4e4e74af2204656574350b302dc76a42ca11c27e"
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
      "0xf86d80844190ab0182520894952672c87f1aa6f23ffe29e49e98edb092c1fa0987038d7ea4c68000808360306ca0ad73848edf57540086881fae145be0efb424cc2b66b3987774a9379a1dcdb237a01984ddc6a204991b02faa60d18c0a746d7a5ebad04458352f27c25840118897d"
    ],
    "blockhash": "0xf3dc265916a2c7280da545cf4e93a19b4c9c05d166136441bdc67cb96ed728c0",
    "blocknumber": 2
  },
```

The state_transition_tmux.sh script also stores the transition details in a separate file named Output/transition_log_node_x.json as shown below.

```bash
head -n 11 Output/transition_log_node_0.json 
{
  "0": {
    "batch": "0",
    "block_hash": "0xd483463ad555e3a445abed6d2a957eff5a4c802cb7cc2903c970819cb045ee40",
    "block_number": 1
  },
  "1": {
    "batch": "1",
    "block_hash": "0xf3dc265916a2c7280da545cf4e93a19b4c9c05d166136441bdc67cb96ed728c0",
    "block_number": 2
  },
```

All the isolated nethermind clients involved in the state transition of the respective agreed ordered batches does the same state transitions and this is reflected in the matching block hashes seen in the Output/transition_log_node_x.json files.

ex: 
```bash
user1@server13t:Nethermind-Sailfish-Integration$ head -n 11 Output/transition_log_node_0.json 
{
  "0": {
    "batch": "0",
    "block_hash": "0xd483463ad555e3a445abed6d2a957eff5a4c802cb7cc2903c970819cb045ee40",
    "block_number": 1
  },
  "1": {
    "batch": "1",
    "block_hash": "0xf3dc265916a2c7280da545cf4e93a19b4c9c05d166136441bdc67cb96ed728c0",
    "block_number": 2
  },
user1@server13t:Nethermind-Sailfish-Integration$ head -n 11 Output/transition_log_node_1.json 
{
  "0": {
    "batch": "0",
    "block_hash": "0xd483463ad555e3a445abed6d2a957eff5a4c802cb7cc2903c970819cb045ee40",
    "block_number": 1
  },
  "1": {
    "batch": "1",
    "block_hash": "0xf3dc265916a2c7280da545cf4e93a19b4c9c05d166136441bdc67cb96ed728c0",
    "block_number": 2
  },
user1@server13t:Nethermind-Sailfish-Integration$ head -n 11 Output/transition_log_node_2.json 
{
  "0": {
    "batch": "0",
    "block_hash": "0xd483463ad555e3a445abed6d2a957eff5a4c802cb7cc2903c970819cb045ee40",
    "block_number": 1
  },
  "1": {
    "batch": "1",
    "block_hash": "0xf3dc265916a2c7280da545cf4e93a19b4c9c05d166136441bdc67cb96ed728c0",
    "block_number": 2
  },
user1@server13t:~/Nethermind-Sailfish-Integration$ head -n 11 Output/transition_log_node_3.json 
{
  "0": {
    "batch": "0",
    "block_hash": "0xd483463ad555e3a445abed6d2a957eff5a4c802cb7cc2903c970819cb045ee40",
    "block_number": 1
  },
  "1": {
    "batch": "1",
    "block_hash": "0xf3dc265916a2c7280da545cf4e93a19b4c9c05d166136441bdc67cb96ed728c0",
    "block_number": 2
  },
```
The nethermind clients continue to agree on the blocks. 

To stop the above scripts, follow the below steps. 

``bash 
    ./state_transition_tmux.sh stop
    ./extract_batches_tmux.sh stop
    ./stop_nethermind_tmux.sh
    tmux kill-session -t sailfish_tx_senders
```
To stop the 4 sailfish nodes, type 'exit' in the sailfish tmux pane.


### Valid transaction generation

For this PoC, transactions are designed to be *valid by construction*. By “valid,” we mean that:

- No duplicate transactions are sent.
- Nonces are always correct and in-order.
- Every transaction can be executed independently, without waiting on missing nonces.

To guarantee this, we pre-generate **100,000 accounts**, each producing exactly **one transaction**.  
All of these accounts are included in `chain_data/chainspec.json` so that Nethermind recognizes them from genesis.

In short, using 100,000 single-use accounts allows us to **focus on testing Sailfish ordering and Nethermind execution determinism**, without introducing complications from nonce management. This is the limitation of the design used in this PoC.


### Repository Layout
├── chain_data/ # genesis, JWT, and chainspec files
├── Output/
│ ├── sailfish_logs/ # logs from primaries and workers
│ ├── node-{0..3}/ # Nethermind datadirs (one per node)
│ ├── .db-{0..3}/ # Sailfish primary databases
│ ├── .db--{0,1}/ # Sailfish worker databases
│ ├── transactions_batch_node_.json # extracted ordered batches
│ └── transition_log_node_*.json # per-node execution logs
├── setup_files/
│ └── valid_txs/ # pre-generated valid tx sets
├── run_nodes.sh # launch 4-node Sailfish network
├── run_tx_senders_tmux.sh # send RLP-signed transactions
├── extract_batches_tmux.sh # extract ordered batches
├── run_nethermind_clients_tmux.sh # start isolated Nethermind clients
├── state_transition_tmux.sh # drive state transitions via Engine API
└── stop_nethermind_tmux.sh # stop Nethermind clients cleanly


Feel free to contribute or report issues!




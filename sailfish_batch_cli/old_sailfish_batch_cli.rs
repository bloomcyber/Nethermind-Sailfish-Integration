//! A CLI tool to scan and print Sailfish batches from RocksDB with optional JSON and listing support

use rocksdb::{Options, DB, IteratorMode};
use bincode;
use serde::{Deserialize, Serialize};
use std::env;
use base64::{engine::general_purpose, Engine as _};

#[derive(Deserialize, Serialize, Debug)]
struct Metadata {
    id: u32,
    worker_id: u8,
    timestamp: u64,
}

#[derive(Deserialize, Serialize, Debug)]
struct Batch {
    #[allow(dead_code)]
    digest: [u8; 32],
    metadata: Metadata,
    txns: Vec<Vec<u8>>,
}

fn print_batch_by_key(db: &DB, cf: &rocksdb::ColumnFamily, key_input: &str, json: bool) {
    let key_bytes = if let Ok(hex) = hex::decode(key_input) {
        hex
    } else if let Ok(base64) = general_purpose::STANDARD.decode(key_input) {
        base64
    } else if let Ok(index) = key_input.parse::<usize>() {
        let iter = db.iterator_cf(cf, IteratorMode::Start);
        let digest = iter.skip(index).next().map(|res| res.unwrap().0.to_vec());
        if let Some(d) = digest {
            d
        } else {
            println!("No batch at index {}", index);
            return;
        }
    } else {
        println!("Invalid input: must be hex, base64, or integer index");
        return;
    };

    match db.get_cf(cf, &key_bytes) {
        Ok(Some(value)) => {
            let batch: Batch = bincode::deserialize(&value).expect("Failed to decode batch");
            if json {
                let output = serde_json::to_string_pretty(&batch).unwrap();
                println!("{}", output);
            } else {
                println!("Batch Digest = {}", hex::encode(&key_bytes));
                println!("  Metadata: id={}, worker_id={}, timestamp={}",
                    batch.metadata.id,
                    batch.metadata.worker_id,
                    batch.metadata.timestamp);
                for (j, tx) in batch.txns.iter().enumerate() {
                    println!("    Tx {}: 0x{}", j, hex::encode(tx));
                }
            }
        }
        Ok(None) => println!("No batch found with key {}", key_input),
        Err(e) => println!("Error retrieving batch: {}", e),
    }
}

fn list_batches(db: &DB, cf: &rocksdb::ColumnFamily) {
    let iter = db.iterator_cf(cf, IteratorMode::Start);
    for (i, res) in iter.enumerate() {
        if let Ok((key, value)) = res {
            let batch: Batch = bincode::deserialize(&value).unwrap_or_else(|_| Batch {
                digest: [0u8; 32],
                metadata: Metadata { id: 0, worker_id: 0, timestamp: 0 },
                txns: vec![],
            });
            println!("Batch {}: Digest = {}", i, hex::encode(key));
            println!("  Metadata: id={}, worker_id={}, timestamp={}",
                batch.metadata.id,
                batch.metadata.worker_id,
                batch.metadata.timestamp);
        }
    }
}

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() < 2 {
        eprintln!("Usage: sailfish_batch_cli <rocksdb_path> [<batch_key|--list>] [--json]");
        std::process::exit(1);
    }

    let db_path = &args[1];
    let json = args.contains(&"--json".to_string());
    let list_mode = args.get(2).map(|s| s == "--list").unwrap_or(false);
    let key_input = if args.len() >= 3 && !list_mode { Some(&args[2]) } else { None };

    let db = DB::open_cf_for_read_only(&Options::default(), db_path, vec!["default"], false)
        .expect("Failed to open DB");
    let cf = db.cf_handle("default").expect("Missing 'default' column family");

    if list_mode {
        list_batches(&db, cf);
    } else if let Some(key) = key_input {
        print_batch_by_key(&db, cf, key, json);
    } else {
        eprintln!("Error: Please provide either a batch key or --list");
    }
}


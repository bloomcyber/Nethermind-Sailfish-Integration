//! A CLI tool to scan and print Sailfish batches from RocksDB with optional JSON and listing support

use base64::{Engine as _, engine::general_purpose};
use bincode;
use hex;
use rocksdb::{DB, IteratorMode, Options};
use serde_json::json;
use std::collections::HashSet;
use std::env;
use worker::WorkerMessage;

fn decode_key_input(key_input: &str) -> Option<Vec<u8>> {
    if let Ok(hex) = hex::decode(key_input) {
        Some(hex)
    } else if let Ok(base64) = general_purpose::STANDARD.decode(key_input) {
        Some(base64)
    } else {
        None
    }
}

fn print_batch_from_db(db: &DB, cf: &rocksdb::ColumnFamily, key_bytes: &[u8], json: bool) -> bool {
    match db.get_cf(cf, key_bytes) {
        Ok(Some(value)) => match bincode::deserialize::<WorkerMessage>(&value) {
            Ok(WorkerMessage::Batch(txs)) => {
                if json {
                    let txs_hex: Vec<String> = txs.iter().map(|tx| hex::encode(tx)).collect();
                    let output = json!({
                        "digest": hex::encode(key_bytes),
                        "txns": txs_hex
                    });
                    println!("{}", serde_json::to_string_pretty(&output).unwrap());
                } else {
                    let txs_hex: Vec<String> = txs.iter().map(|tx| hex::encode(tx)).collect();
                    println!("{}: {:?}", hex::encode(key_bytes), txs_hex);
                }
                true
            }
            _ => false,
        },
        _ => false,
    }
}

fn list_batches(db_paths: &[String]) {
    let mut seen = HashSet::new();
    for path in db_paths {
        let db = DB::open_cf_for_read_only(&Options::default(), path, vec!["default"], false)
            .expect("Failed to open DB");
        let cf = db
            .cf_handle("default")
            .expect("Missing 'default' column family");
        let iter = db.iterator_cf(cf, IteratorMode::Start);
        for res in iter {
            if let Ok((key, value)) = res {
                if let Ok(WorkerMessage::Batch(_)) = bincode::deserialize::<WorkerMessage>(&value) {
                    let digest = hex::encode(&key);
                    if seen.insert(digest.clone()) {
                        println!("{}", digest);
                    }
                }
            }
        }
    }
}

fn print_batch_from_dbs(db_paths: &[String], key_input: &str, json: bool) {
    let key_bytes = match decode_key_input(key_input) {
        Some(b) => b,
        None => {
            println!("Invalid digest: must be hex or base64");
            return;
        }
    };

    for path in db_paths {
        let db = DB::open_cf_for_read_only(&Options::default(), path, vec!["default"], false)
            .expect("Failed to open DB");
        let cf = db
            .cf_handle("default")
            .expect("Missing 'default' column family");
        if print_batch_from_db(&db, cf, &key_bytes, json) {
            return;
        }
    }
    println!("Batch not found in provided databases");
}

fn main() {
    let mut args: Vec<String> = env::args().skip(1).collect();

    let json = if let Some(pos) = args.iter().position(|s| s == "--json") {
        args.remove(pos);
        true
    } else {
        false
    };

    let list_mode = if let Some(pos) = args.iter().position(|s| s == "--list") {
        args.remove(pos);
        true
    } else {
        false
    };

    if list_mode {
        if args.is_empty() {
            eprintln!("Usage: sailfish_batch_cli [--json] --list <db_path> [db_path ...]");
            std::process::exit(1);
        }
        list_batches(&args);
        return;
    }

    if args.len() < 2 {
        eprintln!("Usage: sailfish_batch_cli [--json] <batch_digest> <db_path> [db_path ...]");
        std::process::exit(1);
    }

    let key_input = args.remove(0);
    let db_paths = args;

    print_batch_from_dbs(&db_paths, &key_input, json);
}

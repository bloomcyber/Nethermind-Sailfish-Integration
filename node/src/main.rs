// Copyright(C) Facebook, Inc. and its affiliates.
use anyhow::{Context, Result};
use clap::{crate_name, crate_version, App, AppSettings, ArgMatches, SubCommand};
use config::Export as _;
use config::Import as _;
use config::{Committee, KeyPair, Parameters, WorkerId};
use consensus::Consensus;
use env_logger::Env;
use primary::{Certificate, Primary};
use store::Store;
use worker::WorkerMessage;
use serde::Serialize;
use serde_json::json;
use std::fs::{OpenOptions};
use std::io::Write as _;
use std::path::{Path, PathBuf};
use tokio::sync::mpsc::{channel, Receiver};
use worker::Worker;
use log::{debug, error, warn,info};
use hex;
use std::collections::BTreeMap;
use std::fs::{File, write};
use base64::{encode};

// use ethers::core::utils::rlp;
// use ethers::types::Transaction;
// use rlp::Rlp;


/// The default channel capacity.
pub const CHANNEL_CAPACITY: usize = 1_000;

#[tokio::main]
async fn main() -> Result<()> {
    let matches = App::new(crate_name!())
        .version(crate_version!())
        .about("A research implementation of Narwhal and Tusk.")
        .args_from_usage("-v... 'Sets the level of verbosity'")
        .subcommand(
            SubCommand::with_name("generate_keys")
                .about("Print a fresh key pair to file")
                .args_from_usage("--filename=<FILE> 'The file where to print the new key pair'"),
        )
        .subcommand(
            SubCommand::with_name("run")
                .about("Run a node")
                .args_from_usage("--keys=<FILE> 'The file containing the node keys'")
                .args_from_usage("--committee=<FILE> 'The file containing committee information'")
                .args_from_usage("--parameters=[FILE] 'The file containing the node parameters'")
                .args_from_usage("--store=<PATH> 'The path where to create the data store'")
                .subcommand(SubCommand::with_name("primary").about("Run a single primary"))
                .subcommand(
                    SubCommand::with_name("worker")
                        .about("Run a single worker")
                        .args_from_usage("--id=<INT> 'The worker id'"),
                )
                .setting(AppSettings::SubcommandRequiredElseHelp),
        )
        .setting(AppSettings::SubcommandRequiredElseHelp)
        .get_matches();

    let log_level = match matches.occurrences_of("v") {
        0 => "error",
        1 => "warn",
        2 => "info",
        3 => "debug",
        _ => "trace",
    };
    let mut logger = env_logger::Builder::from_env(Env::default().default_filter_or(log_level));
    #[cfg(feature = "benchmark")]
    logger.format_timestamp_millis();
    logger.init();

    match matches.subcommand() {
        ("generate_keys", Some(sub_matches)) => KeyPair::new()
            .export(sub_matches.value_of("filename").unwrap())
            .context("Failed to generate key pair")?,
        ("run", Some(sub_matches)) => run(sub_matches).await?,
        _ => unreachable!(),
    }
    Ok(())
}

// Runs either a worker or a primary.
async fn run(matches: &ArgMatches<'_>) -> Result<()> {
    let key_file = matches.value_of("keys").unwrap();
    let committee_file = matches.value_of("committee").unwrap();
    let parameters_file = matches.value_of("parameters");
    let store_path = matches.value_of("store").unwrap();

    let keypair = KeyPair::import(key_file).context("Failed to load the node's keypair")?;
    let committee =
        Committee::import(committee_file).context("Failed to load the committee information")?;

    let parameters = match parameters_file {
        Some(filename) => {
            Parameters::import(filename).context("Failed to load the node's parameters")?
        }
        None => Parameters::default(),
    };

    let store = Store::new(store_path).context("Failed to create a store")?;

    let consensus_output_file = PathBuf::from(store_path).join("ordered_certificates.json");
    let mut cert_file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(&consensus_output_file)
        .expect("Failed to open output file for certificates");

    let analysis_store = match matches.subcommand() {
        ("primary", _) => {
            let path = format!("{}-0", store_path);
            if Path::new(&path).exists() {
                Store::new_read_only(&path).unwrap_or_else(|_| {
                    warn!("Failed to open worker store at '{}'. Using primary store instead.", path);
                    store.clone()
                })
            } else {
                warn!("Worker store not found at '{}'. Will skip batch content lookup.", path);
                store.clone()
            }
        }
        _ => store.clone(),
    };

    let (tx_output, rx_output) = channel(CHANNEL_CAPACITY);

    match matches.subcommand() {
        ("primary", _) => {
            let (tx_new_certificates, rx_new_certificates) = channel(CHANNEL_CAPACITY);
            let (tx_feedback, rx_feedback) = channel(CHANNEL_CAPACITY);
            let (tx_consensus_header, rx_consensus_header) = channel(CHANNEL_CAPACITY);
            Primary::spawn(
                keypair,
                committee.clone(),
                parameters.clone(),
                store.clone(),
                tx_new_certificates,
                rx_feedback,
                tx_consensus_header,
            );
            Consensus::spawn(
                committee,
                parameters.gc_depth,
                rx_new_certificates,
                rx_consensus_header,
                tx_feedback,
                tx_output,
            );
            let output_file = PathBuf::from(store_path).join("ordered_batches.json");
            // analyze(rx_output, analysis_store, output_file, &mut cert_file).await;
            let output_file2 = PathBuf::from(store_path).join("ordered_batches2.json");
            analyze2(rx_output, analysis_store, output_file2, &mut cert_file).await;

            unreachable!();
        }
        
            ("worker", Some(sub_matches)) => {
            let id = sub_matches
                .value_of("id")
                .unwrap()
                .parse::<WorkerId>()
                .context("The worker id must be a positive integer")?;
            Worker::spawn(keypair.name, id, committee, parameters, store);
            info!("Worker spawned. Blocking indefinitely...");
            tokio::signal::ctrl_c().await.expect("Failed to listen for ctrl+c");
            info!("Worker received ctrl+c. Exiting.");
        }
        _ => unreachable!(),
    }

    Ok(())
}

#[derive(Serialize)]
struct JsonBatch {
    batch: String,
    transactions: Vec<String>,
}



pub async fn analyze2(
    mut rx_output: Receiver<Certificate>,
    mut store: Store,
    output_file2: PathBuf,
    cert_file: &mut File,
) -> Result<(), Box<dyn std::error::Error>> {
    let mut ordered_batches: Vec<serde_json::Value> = Vec::new();

    while let Some(certificate) = rx_output.recv().await {
        let mut payload_json = BTreeMap::new();
        let mut tx_map = BTreeMap::new();

        for (digest, worker_id) in &certificate.header.payload {
            let digest_str = encode(digest);

            payload_json.insert(digest_str.clone(), *worker_id);

            match store.read(digest.to_vec()).await {
                Ok(Some(batch_bytes)) => {
			match bincode::deserialize::<WorkerMessage>(&batch_bytes) {
                        Ok(WorkerMessage::Batch(batch)) => {
                            let txs: Vec<String> = batch
                                .into_iter()
                                .map(|tx| hex::encode(tx))
                                .collect();
                            tx_map.insert(digest_str, json!(txs));
                        }
                        _ => {
                            tx_map.insert(digest_str, json!("invalid"));
                        }
                    }
                }
                _ => {
                    tx_map.insert(digest_str, json!("missing"));
                }
            }
        }

        let timeout_cert_json = {
            let tc = &certificate.header.timeout_cert;
            serde_json::json!({
                "round": tc.round,
                "timeouts": tc
                    .timeouts
                    .iter()
                    .map(|(pk, sig)| {
                        // let sig_compact = format!("{}.{}", base64::encode(&sig.part1), base64::encode(&sig.part2));
                        // serde_json::json!([ base64::encode(pk), sig_compact ])
                        serde_json::json!([ pk.to_string(), format!("{:?}", sig) ])
                    })
                    .collect::<Vec<_>>()
            })
        };

        let no_vote_cert_json = {
            let nvc = &certificate.header.no_vote_cert;
            serde_json::json!({
                "round": nvc.round,
                "no_votes": nvc
                    .no_votes
                    .iter()
                    .map(|(pk, sig)| {
                        // let sig_compact = format!("{}.{}", base64::encode(&sig.part1), base64::encode(&sig.part2));
                        // serde_json::json!([ base64::encode(pk), sig_compact ])
                        serde_json::json!([ pk.to_string(), format!("{:?}", sig) ])
                    })
                    .collect::<Vec<_>>()
            })
        };

        let cert_output = json!({
            "author": certificate.header.author.to_string(),
            "round": certificate.header.round,
            "id": encode(certificate.header.id.0),
            "payload": payload_json,
            "transactions": tx_map,
            "parents": certificate.header.parents.iter().map(|d| encode(d)).collect::<Vec<_>>(),
            // "signature": encode(&certificate.header.signature),
            "signature": format!("{:?}", certificate.header.signature),
            // "timeout_cert": render_timeout_cert(&certificate.header.timeout_cert),
            // "no_vote_cert": render_no_vote_cert(&certificate.header.no_vote_cert),
            "timeout_cert": timeout_cert_json,
            "no_vote_cert": no_vote_cert_json
            // "timeout_cert": certificate.header.timeout_cert,
            // "no_vote_cert": certificate.header.no_vote_cert
            // "votes": certificate.votes
            // "votes": votes_formatted
        });

        writeln!(
            cert_file,
            "{}",
            serde_json::to_string_pretty(&cert_output)?
        )?;

        ordered_batches.push(cert_output);
    }

    write(
        output_file2,
        serde_json::to_string_pretty(&ordered_batches)?,
    )?;

    Ok(())
}



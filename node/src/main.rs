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
use std::fs::{OpenOptions};
use std::io::Write as _;
use std::path::{Path, PathBuf};
use tokio::sync::mpsc::{channel, Receiver};
use worker::Worker;
use log::{debug, error, warn,info};
use hex;

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
            analyze(rx_output, analysis_store, output_file, &mut cert_file).await;
            unreachable!();
        }
        // ("worker", Some(sub_matches)) => {
        //     let id = sub_matches
        //         .value_of("id")
        //         .unwrap()
        //         .parse::<WorkerId>()
        //         .context("The worker id must be a positive integer")?;
        //     Worker::spawn(keypair.name, id, committee, parameters, store.clone());
        // }
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

async fn analyze(mut rx_output: Receiver<Certificate>, mut store: Store, output_file: std::path::PathBuf, cert_file: &mut std::fs::File) {
    let mut file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(&output_file)
        .expect("Failed to open output file");

    while let Some(certificate) = rx_output.recv().await {
        if let Ok(cert_line) = serde_json::to_string(&certificate) {
            if let Err(e) = writeln!(cert_file, "{}", cert_line) {
                error!("Failed to write certificate to file: {}", e);
            }
        }

        for (digest, _) in certificate.header.payload.iter() {
            debug!("Analyzing digest {}", digest);
            match store.read(digest.to_vec()).await {
                Ok(Some(bytes)) => {
                    debug!("Read batch {} from store", digest);
                    if let Ok(WorkerMessage::Batch(batch)) = bincode::deserialize::<WorkerMessage>(&bytes) {
                        let record = JsonBatch {
                            batch: hex::encode(&digest.0),
                            transactions: batch.into_iter().map(|tx| hex::encode(&tx)).collect(),
                        };
                        match serde_json::to_string(&record) {
                            Ok(line) => {
                                if let Err(e) = writeln!(file, "{}", line) {
                                    error!("Failed to write batch {} to file: {}", digest, e);
                                } else {
                                    debug!("Serialized batch {} to JSON", digest);
                                }
                            }
                            Err(e) => error!("Failed to serialize batch {}: {}", digest, e),
                        }
                    }
                }
                Ok(None) => debug!("Batch {} not found in store", digest),
                Err(e) => error!("Store read failed for batch {}: {}", digest, e),
            }
        }
    }
}

use anyhow::{Context, Result};
use bytes::Bytes;
use clap::{crate_name, crate_version, App, AppSettings};
use coins_bip39::English;
use env_logger::Env;
use ethers_core::types::{transaction::eip2718::TypedTransaction, Address, TransactionRequest};
use ethers_signers::{LocalWallet, MnemonicBuilder, Signer};
use jsonwebtoken::{encode, EncodingKey, Header};
use log::{info, warn};
use serde::Serialize;
use serde_json::json;
use std::fs;
use chrono::{Duration as ChronoDuration, Utc};
use reqwest;
use tokio::time::{sleep, Duration};

#[derive(Serialize)]
struct Claims {
    exp: usize,
}

#[tokio::main]
async fn main() -> Result<()> {
    let matches = App::new(crate_name!())
        .version(crate_version!())
        .about("Worker RPC client")
        .args_from_usage("<RPC> 'The HTTP endpoint of the worker'" )
        .args_from_usage("--size=<INT> 'The size of each transaction in bytes'")
        .args_from_usage("--burst=<INT> 'Burst duration (in ms)'")
        .args_from_usage("--rate=<INT> 'The rate (txs/s) at which to send the transactions'")
        .args_from_usage("--nodes=[RPC]... 'Endpoints that must be reachable before starting the benchmark.'")
        .args_from_usage("--jwt-secret=<FILE> 'Path to the JWT secret file'")
        .args_from_usage("--mnemonic=<FILE> 'Path to the mnemonic file'")
        .args_from_usage("--transactions=<INT> 'Number of transactions to send'")
        .setting(AppSettings::ArgRequiredElseHelp)
        .get_matches();

    env_logger::Builder::from_env(Env::default().default_filter_or("info"))
        .format_timestamp_millis()
        .init();

    let endpoint = matches.value_of("RPC").unwrap().to_string();
    let size = matches
        .value_of("size")
        .unwrap()
        .parse::<usize>()
        .context("The size of transactions must be a non-negative integer")?;
    let burst_duration = matches
        .value_of("burst")
        .unwrap()
        .parse::<u64>()
        .context("Burst duration must be a non-negative integer")?;
    let rate = matches
        .value_of("rate")
        .unwrap()
        .parse::<u64>()
        .context("The rate of transactions must be a non-negative integer")?;
    let other_endpoints = matches
        .values_of("nodes")
        .unwrap_or_default()
        .into_iter()
        .map(|x| x.to_string())
        .collect::<Vec<_>>();
    let jwt_secret_path = matches.value_of("jwt-secret").unwrap();
    let mnemonic_path = matches.value_of("mnemonic").unwrap();
    let tx_count = matches
        .value_of("transactions")
        .unwrap_or("1")
        .parse::<u32>()
        .context("Invalid number of transactions")?;

    let secret = fs::read_to_string(jwt_secret_path).context("Reading JWT secret")?;
    let claims = Claims { exp: (Utc::now() + ChronoDuration::minutes(5)).timestamp() as usize };
    let token = encode(&Header::default(), &claims, &EncodingKey::from_secret(secret.trim().as_bytes()))?;

    let mnemonic = fs::read_to_string(mnemonic_path).context("Reading mnemonic")?;
    let client = reqwest::Client::new();
    let mut batch = Vec::new();
    let mut interval = tokio::time::interval(Duration::from_millis(burst_duration));
    tokio::pin!(interval);

    for i in 0..tx_count {
        interval.as_mut().tick().await;
        let wallet: LocalWallet = MnemonicBuilder::<English>::default()
            .phrase(mnemonic.trim())
            .index(i)
            .context("Deriving key")?
            .build()?
            .with_chain_id(1u64);
        let tx: TypedTransaction = TransactionRequest::new()
            .to(Address::zero())
            .value(0u64)
            .data(Bytes::from(vec![0u8; size]))
            .nonce(i)
            .from(wallet.address())
            .into();
        let sig = wallet.sign_transaction(&tx).await?;
        let raw_tx = format!("0x{}", hex::encode(sig.to_vec()));

        // Previously this client dispatched each signed transaction to all
        // endpoints using the `eth_sendRawTransaction` RPC call. The current
        // workload only requires generating the signed payloads, so the
        // network request logic is disabled for now.
        // let mut endpoints = vec![endpoint.clone()];
        // endpoints.extend(other_endpoints.clone());
        // for ep in &endpoints {
        //     let payload = json!({
        //         "jsonrpc": "2.0",
        //         "method": "eth_sendRawTransaction",
        //         "params": [raw_tx.clone()],
        //         "id": i,
        //     });
        //     let resp = client
        //         .post(ep)
        //         .bearer_auth(&token)
        //         .json(&payload)
        //         .send()
        //         .await;
        //     match resp {
        //         Ok(r) if r.status().is_success() => info!("sent transaction {} to {}", i, ep),
        //         Ok(r) => warn!("failed to send transaction {} to {}: {}", i, ep, r.status()),
        //         Err(e) => warn!("failed to send transaction {} to {}: {}", i, ep, e),
        //     }
        // }
        batch.push(raw_tx);
        if rate > 0 {
            sleep(Duration::from_millis(1000 / rate)).await;
        }
    }

    fs::write(
        "transactions_batch.json",
        serde_json::to_string_pretty(&batch)?,
    )?;

    Ok(())
}

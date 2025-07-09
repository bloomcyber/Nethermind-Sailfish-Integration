use anyhow::{Context, Result};
use bytes::BytesMut;
use clap::{App, Arg};
use log::{error, info, warn};
use std::{fs::File, io::BufReader, net::SocketAddr};
use tokio::{net::TcpStream, time::{sleep, Duration}};
use tokio_util::codec::{Framed, LengthDelimitedCodec};
use serde_json::Deserializer;
use futures::sink::SinkExt;


#[tokio::main]
async fn main() -> Result<()> {
    env_logger::init();

    let matches = App::new("TcpTxSender")
        .version("0.1")
        .about("Sends signed Ethereum txs over TCP preserving order")
        .arg(Arg::with_name("INPUT")
            .help("Input file containing signed txs (JSON array)")
            .required(true))
        .arg(Arg::with_name("addr")
            .long("addr")
            .takes_value(true)
            .required(true)
            .help("Target address in form IP:PORT"))
        .arg(Arg::with_name("delay")
            .long("delay")
            .takes_value(true)
            .default_value("100")
            .help("Delay between txs in milliseconds"))
        .get_matches();

    let file_path = matches.value_of("INPUT").unwrap();
    let target = matches.value_of("addr").unwrap().parse::<SocketAddr>()?;
    let delay = matches.value_of("delay").unwrap().parse::<u64>()?;

    let file = File::open(file_path).context("Unable to open tx file")?;
    let reader = BufReader::new(file);
    let stream = Deserializer::from_reader(reader).into_iter::<String>();

    let socket = TcpStream::connect(target).await.context("Failed to connect")?;
    let mut transport = Framed::new(socket, LengthDelimitedCodec::new());

    for (i, maybe_tx) in stream.enumerate() {
        let tx = match maybe_tx {
            Ok(t) => t,
            Err(e) => {
                error!("Failed to parse tx {}: {}", i, e);
                continue;
            }
        };

        let tx_bytes = match hex::decode(tx.strip_prefix("0x").unwrap_or(&tx)) {
            Ok(b) => b,
            Err(e) => {
                error!("Invalid hex for tx {}: {}", i, e);
                continue;
            }
        };

        let mut attempts = 0;
        loop {
            attempts += 1;
            match transport.send(BytesMut::from(&tx_bytes[..]).freeze()).await {
                Ok(_) => {
                    info!("Tx {} sent successfully (attempt {})", i, attempts);
                    break;
                }
                Err(e) => {
                    warn!("Tx {} failed on attempt {}: {}", i, attempts, e);
                    if attempts >= 3 {
                        eprintln!("Tx {} failed after 3 attempts. Retry? (y/n): ", i);
                        let mut input = String::new();
                        std::io::stdin().read_line(&mut input)?;
                        if input.trim().to_lowercase() != "y" {
                            error!("Aborting at tx {} after user opted out", i);
                            return Ok(());
                        }
                        attempts = 0; // reset
                    }
                }
            }
        }

        sleep(Duration::from_millis(delay)).await;
    }

    info!("All transactions sent.");
    Ok(())
}

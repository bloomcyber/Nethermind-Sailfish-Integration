use super::*;
use crypto::{generate_keypair, PublicKey, SecretKey};
use rand::rngs::StdRng;
use rand::SeedableRng as _;

// Small fixture returning deterministic keypairs
fn keys() -> Vec<(PublicKey, SecretKey)> {
    let mut rng = StdRng::from_seed([0; 32]);
    (0..4).map(|_| generate_keypair(&mut rng)).collect()
}

fn committee() -> Committee {
    Committee {
        authorities: keys()
            .iter()
            .enumerate()
            .map(|(i, (id, _))| {
                let primary = PrimaryAddresses {
                    primary_to_primary: format!("127.0.0.1:{}", 100 + i).parse().unwrap(),
                    worker_to_primary: format!("127.0.0.1:{}", 200 + i).parse().unwrap(),
                };
                let workers = vec![(
                    0,
                    WorkerAddresses {
                        primary_to_worker: format!("127.0.0.1:{}", 300 + i).parse().unwrap(),
                        transactions: format!("127.0.0.1:{}", 400 + i).parse().unwrap(),
                        worker_to_worker: format!("127.0.0.1:{}", 500 + i).parse().unwrap(),
                    },
                )]
                .iter()
                .cloned()
                .collect();
                (
                    *id,
                    Authority {
                        stake: 1,
                        primary,
                        workers,
                    },
                )
            })
            .collect(),
    }
}

#[test]
fn worker_returns_unknown_worker_error() {
    let committee = committee();
    let name = *committee.authorities.keys().next().unwrap();
    let result = committee.worker(&name, &1); // only worker 0 exists
    match result {
        Err(ConfigError::UnknownWorker(id)) => assert_eq!(id, 1),
        other => panic!("Unexpected result: {:?}", other),
    }
}

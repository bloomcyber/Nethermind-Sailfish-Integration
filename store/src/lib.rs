// Copyright(C) Facebook, Inc. and its affiliates.
use std::collections::{HashMap, VecDeque};
use tokio::sync::mpsc::{channel, Sender};
use tokio::sync::oneshot;
use log::{debug, error};

#[cfg(test)]
#[path = "tests/store_tests.rs"]
pub mod store_tests;

pub type StoreError = rocksdb::Error;
type StoreResult<T> = Result<T, StoreError>;

type Key = Vec<u8>;
type Value = Vec<u8>;

pub enum StoreCommand {
    Write(Key, Value),
    Read(Key, oneshot::Sender<StoreResult<Option<Value>>>),
    NotifyRead(Key, oneshot::Sender<StoreResult<Value>>),
}

#[derive(Clone)]
pub struct Store {
    channel: Sender<StoreCommand>,
}

impl Store {
    pub fn new(path: &str) -> StoreResult<Self> {
        let db = match rocksdb::DB::open_default(path) {
            Ok(db) => {
                debug!("Created RocksDB store at {}", path);
                db
            }
            Err(e) => {
                error!("Failed to open RocksDB at {}: {}", path, e);
                return Err(e);
            }
        };
        let mut obligations = HashMap::<_, VecDeque<oneshot::Sender<_>>>::new();
        let (tx, mut rx) = channel(100);
        tokio::spawn(async move {
            while let Some(command) = rx.recv().await {
                match command {
                    StoreCommand::Write(key, value) => {
                        debug!("Store write request for {} bytes", key.len());
                        match db.put(&key, &value) {
                            Ok(_) => debug!("Write successful for {} bytes", key.len()),
                            Err(e) => error!("Failed to write key ({} bytes): {}", key.len(), e),
                        }
                        if let Some(mut senders) = obligations.remove(&key) {
                            while let Some(s) = senders.pop_front() {
                                let _ = s.send(Ok(value.clone()));
                            }
                        }
                    }
                    StoreCommand::Read(key, sender) => {
                        debug!("Store read request for {} bytes", key.len());
                        let response = db.get(&key);
                        match &response {
                            Ok(Some(_)) => debug!("Read hit for {} bytes", key.len()),
                            Ok(None) => debug!("Read miss for {} bytes", key.len()),
                            Err(e) => error!("Read error for {} bytes: {}", key.len(), e),
                        }
                        let _ = sender.send(response);
                    }
                    StoreCommand::NotifyRead(key, sender) => {
                        debug!("Store notify_read request for {} bytes", key.len());
                        let response = db.get(&key);
                        match &response {
                            Ok(Some(_)) => debug!("Notify read hit for {} bytes", key.len()),
                            Ok(None) => debug!("Notify read miss for {} bytes", key.len()),
                            Err(e) => error!("Notify read error for {} bytes: {}", key.len(), e),
                        }
                        match response {
                            Ok(None) => obligations
                                .entry(key)
                                .or_insert_with(VecDeque::new)
                                .push_back(sender),
                            _ => {
                                let _ = sender.send(response.map(|x| x.unwrap()));
                            }
                        }
                    }
                }
            }
        });
        Ok(Self { channel: tx })
    }

    pub async fn write(&mut self, key: Key, value: Value) {
        debug!("Sending Write command for {} bytes", key.len());
        if let Err(e) = self.channel.send(StoreCommand::Write(key, value)).await {
            error!("Failed to send Write command to store: {}", e);
            panic!("Failed to send Write command to store: {}", e);
        } else {
            debug!("Write command sent");
        }
    }

    pub async fn read(&mut self, key: Key) -> StoreResult<Option<Value>> {
        let (sender, receiver) = oneshot::channel();
        debug!("Sending Read command for {} bytes", key.len());
        if let Err(e) = self.channel.send(StoreCommand::Read(key, sender)).await {
            error!("Failed to send Read command to store: {}", e);
            panic!("Failed to send Read command to store: {}", e);
        }
        let result = receiver
            .await
            .expect("Failed to receive reply to Read command from store");
        match &result {
            Ok(Some(_)) => debug!("Received data for Read"),
            Ok(None) => debug!("Read returned none"),
            Err(e) => error!("Read command error: {}", e),
        }
        result
    }

    pub async fn notify_read(&mut self, key: Key) -> StoreResult<Value> {
        let (sender, receiver) = oneshot::channel();
        debug!("Sending NotifyRead command for {} bytes", key.len());
        if let Err(e) = self
            .channel
            .send(StoreCommand::NotifyRead(key, sender))
            .await
        {
            error!("Failed to send NotifyRead command to store: {}", e);
            panic!("Failed to send NotifyRead command to store: {}", e);
        }
        let result = receiver
            .await
            .expect("Failed to receive reply to NotifyRead command from store");
        match &result {
            Ok(_) => debug!("Received data for NotifyRead"),
            Err(e) => error!("NotifyRead command error: {}", e),
        }
        result
    }
}

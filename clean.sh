#!/usr/bin/env bash


#Remove all ordered certificates
for i in {0..3}; do
  rm -f "Output/.db-$i/ordered_certificates.json"
done

# Remove all nethermind node directories
rm -rf Output/node*

# Remove transaction batch files
for i in {0..3}; do
  rm -f "Output/transactions_batch_node_$i.json"
done

# Remove transition log files
for i in {0..3}; do
  rm -f "Output/transition_log_node_$i.json"
done

#!/bin/bash

set -e

DB_PATH=".db-0-0"
CLI="/home/yuvaraj/newSailfish/sailfish_batch_cli/target/debug/sailfish_batch_cli"
DIGEST_FILE="batch_digests.txt"

if [[ "$1" == "store" ]]; then
  echo "Storing all batch digests to $DIGEST_FILE..."
  $CLI "$DB_PATH" --list | grep 'Digest =' | awk '{ print $NF }' > "$DIGEST_FILE"
  echo "Stored $(wc -l < "$DIGEST_FILE") digests."

elif [[ "$1" == "check" ]]; then
  START=${2:-0}
  END=${3:-10}

  if [[ ! -f "$DIGEST_FILE" ]]; then
    echo "Digest file $DIGEST_FILE not found. Run with 'store' first."
    exit 1
  fi

  echo "Checking batches $START to $END..."
  mapfile -t digests < "$DIGEST_FILE"

  for (( i=START; i<=END; i++ )); do
    if [[ $i -ge ${#digests[@]} ]]; then
      echo "Index $i out of range. Max index: ${#digests[@]}"
      break
    fi

    digest=${digests[$i]}
    echo "--- Batch $i: $digest ---"
    $CLI "$DB_PATH" "$digest" --json | jq
    echo
  done

else
  echo "Usage: $0 store            # To store all digests in a file"
  echo "       $0 check <start> <end>  # To check batches from <start> to <end>"
  exit 1
fi


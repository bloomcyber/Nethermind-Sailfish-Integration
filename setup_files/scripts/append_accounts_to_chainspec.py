import json

# Paths
chainspec_path = "chain_data/chainspec_copy.json"
new_accounts_path = "chainspec_accounts.json"  # your file with 1 lakh accounts

# Load existing chainspec
with open(chainspec_path) as f:
    chainspec = json.load(f)

# Load new accounts
with open(new_accounts_path) as f:
    new_accounts = json.load(f)

# Merge into "accounts"
chainspec["accounts"].update(new_accounts)

# Write back safely
with open("chainspec_updated.json", "w") as f:
    json.dump(chainspec, f, indent=2)

print(" Merged new accounts. Output → chainspec_updated.json")

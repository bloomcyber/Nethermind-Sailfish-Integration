from bip_utils import Bip39SeedGenerator, Bip44, Bip44Coins, Bip44Changes
import json

# === CONFIGURATION ===
MNEMONIC = "giant issue aisle success illegal bike spike question tent bar rely arctic volcano long crawl hungry vocal artwork sniff fantasy very lucky have athlete"
ACCOUNT_COUNT = 100000

# === Step 1: Derive accounts ===
seed = Bip39SeedGenerator(MNEMONIC).Generate()
accounts = []
chainspec_accounts = {}

for i in range(ACCOUNT_COUNT):
    bip44 = Bip44.FromSeed(seed, Bip44Coins.ETHEREUM).Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(i)
    addr = bip44.PublicKey().ToAddress()
    priv = bip44.PrivateKey().Raw().ToHex()
    accounts.append({
        "address": addr,
        "private_key": "0x" + priv,
        "nonce": 0
    })
    chainspec_accounts[addr] = {"balance": str(10**18)}  # 1 ETH in wei

# === Step 2: Save outputs ===

# Output 1: accounts.json for tx generation
with open("accounts.json", "w") as f:
    json.dump({a["address"]: {"private_key": a["private_key"], "nonce": 0} for a in accounts}, f, indent=2)
print(" accounts.json written.")

# Output 2: chainspec_accounts.json for inclusion in genesis
with open("chainspec_accounts.json", "w") as f:
    json.dump(chainspec_accounts, f, indent=2)
print(" chainspec_accounts.json written.")

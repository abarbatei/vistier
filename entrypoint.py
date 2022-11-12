import json
import marketplace

from solana.rpc.api import Client, PublicKey
from solana.transaction import Transaction
from solders.signature import Signature
from solders.rpc.responses import (
    GetTransactionResp
)
endpoint = 'https://api.mainnet-beta.solana.com'
# https://magiceden.io/marketplace/shadowy_super_coder_dao
# listing on magic eden https://solana.fm/tx/2ANop8DQxoJsXNvfkAVAzpVLEk1UoGKcgP9YZcKfgRPzstgNaYWiBzJrBF4vxqEmS8Jz7sw926C9JSidJ9QcrsL1?cluster=mainnet-qn1

magic_eden_program_id = "M2mx93ekt1fmXSVkTrUL9xVFHkmME8HTUi5Cyc5aF7K"

solana_client = Client(endpoint)
res = solana_client.is_connected()
if not res:
    print("Problems connection got endpoint")


def dump_transaction_data(tx_response: GetTransactionResp):
    txs = json.loads(tx_response.to_json())
    print(json.dumps(txs, indent=4))


def process_transaction(tx_hash):
    tx_sig = Signature.from_string(tx_hash)
    tx_response = solana_client.get_transaction(tx_sig=tx_sig)
    tx_data = json.loads(tx_response.to_json())
    result = tx_data['result']
    meta_info = result["meta"]
    status = meta_info["status"]
    account_keys = result["transaction"]["message"]["accountKeys"]

    dump_transaction_data(tx_response)

    if status["Ok"]:
        # odd, if this is not null, it means an error occurred
        print(f"Problem with tx: {tx_hash}")

    if not marketplace.is_marketplace(account_keys):
        print(f"Transaction {tx_hash} is not a NFT marketplace transaction")
        return

    if marketplace.MagicEdenTransaction.is_marketplace_tx(result):
        me = marketplace.MagicEdenTransaction(result)
        print(f"Found a Magic Eden transaction of {me.instruction} for {me.price} SOL (fee {me.fee} SOL): {tx_hash}")


def main():

    tx_hash = "2ANop8DQxoJsXNvfkAVAzpVLEk1UoGKcgP9YZcKfgRPzstgNaYWiBzJrBF4vxqEmS8Jz7sw926C9JSidJ9QcrsL1"
    tx_hash = "443p6HwXwSqVBYBxGn5TvtYhgPzHosMX7XaK9AVAv2cMjUjAuG2GhBfQ23cQccyxwNxsdQuivoUmf3gCE5CyTqdt"
    # https://explorer.solana.com/tx/5Ko8Gi5NyJg1k2j7mdErjYGhENWdtVSnBCeJfD1Y7UWvJqsgVxjgWBuCjbxKuiQdAD6Fb1Chxd15bj1gEPzWPr6W
    tx_hash = "5Ko8Gi5NyJg1k2j7mdErjYGhENWdtVSnBCeJfD1Y7UWvJqsgVxjgWBuCjbxKuiQdAD6Fb1Chxd15bj1gEPzWPr6W"
    process_transaction(tx_hash)


main()

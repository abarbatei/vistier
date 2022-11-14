import json

import solana.transaction
from solana.rpc.types import TokenAccountOpts
import marketplace

from solana.rpc.api import Client, PublicKey
from solana.transaction import Transaction
from solders.signature import Signature
from solders.rpc.responses import (
    GetTransactionResp
)

import marketplace.templates

endpoint = 'https://api.mainnet-beta.solana.com'

import nfts

# https://magiceden.io/marketplace/shadowy_super_coder_dao
# listing on magic eden https://solana.fm/tx/2ANop8DQxoJsXNvfkAVAzpVLEk1UoGKcgP9YZcKfgRPzstgNaYWiBzJrBF4vxqEmS8Jz7sw926C9JSidJ9QcrsL1?cluster=mainnet-qn1


solana_client = Client(endpoint)
res = solana_client.is_connected()
if not res:
    print("Problems connection got endpoint")


def dump_transaction_data(tx_response: GetTransactionResp):
    txs = json.loads(tx_response.to_json())
    print(json.dumps(txs, indent=4))


def get_tokens_held_by_address(public_key: PublicKey):
    opts = TokenAccountOpts(program_id=PublicKey("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"))
    return solana_client.get_token_accounts_by_owner_json_parsed(public_key, opts)


def process_transaction(tx_hash):
    tx_sig = Signature.from_string(tx_hash)
    tx_response = solana_client.get_transaction(tx_sig=tx_sig)
    transaction = tx_response.value.transaction

    # if status["Ok"]:
    #     # odd, if this is not null, it means an error occurred
    #     print(f"Problem with tx: {tx_hash}")

    # dump_transaction_data(tx_response)

    if not marketplace.is_marketplace(transaction.transaction.message.account_keys):
        print(f"Transaction {tx_hash} is not a NFT marketplace transaction")
        return

    if marketplace.MagicEdenTransaction.is_marketplace_tx(transaction):
        me = marketplace.MagicEdenTransaction(transaction)
        print(f"Found a Magic Eden transaction of {me.type} for {me.price} SOL: {tx_hash}")
        print(f"\t - creators_fee: {me.creators_fee} SOL ({(me.creators_fee / me.price) * 100:.2f}%)")
        print(f"\t - marketplace_fee: {me.marketplace_fee} SOL ({(me.marketplace_fee/me.price)*100:.2f}%)")


def main():

    tx_hash = "2ANop8DQxoJsXNvfkAVAzpVLEk1UoGKcgP9YZcKfgRPzstgNaYWiBzJrBF4vxqEmS8Jz7sw926C9JSidJ9QcrsL1"
    # https://explorer.solana.com/tx/5Ko8Gi5NyJg1k2j7mdErjYGhENWdtVSnBCeJfD1Y7UWvJqsgVxjgWBuCjbxKuiQdAD6Fb1Chxd15bj1gEPzWPr6W
    tx_hash = "5Ko8Gi5NyJg1k2j7mdErjYGhENWdtVSnBCeJfD1Y7UWvJqsgVxjgWBuCjbxKuiQdAD6Fb1Chxd15bj1gEPzWPr6W"
    tx_hash = "443p6HwXwSqVBYBxGn5TvtYhgPzHosMX7XaK9AVAv2cMjUjAuG2GhBfQ23cQccyxwNxsdQuivoUmf3gCE5CyTqdt"
    # https://solana.fm/tx/5viR6rqH2CEieDQMEk11JcNN18R5vnhg8iAL8zH4SwNFvx93ik243aTyYQRQUhAs8HnfrcfBRzrt3wFKtxCaTWWW?cluster=mainnet-qn1
    # 5viR6... has creator fee paid and magic eden fees
    tx_hash = "5viR6rqH2CEieDQMEk11JcNN18R5vnhg8iAL8zH4SwNFvx93ik243aTyYQRQUhAs8HnfrcfBRzrt3wFKtxCaTWWW"
    # owner BYhbuuLPaM7zL18gGTDPzkVVTPzddrZPZiuhDZqYv5bn
    process_transaction(tx_hash)


main()

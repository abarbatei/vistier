import json
import os
from typing import List

import solana.transaction
from  datetime import datetime
from solana.rpc.types import TokenAccountOpts
import marketplace

from solana.rpc.api import Client, PublicKey
from solana.transaction import Transaction
from solders.signature import Signature
from solders.rpc.responses import (
    GetTransactionResp
)

import marketplace.templates
import nfts


# https://magiceden.io/marketplace/shadowy_super_coder_dao
# listing on magic eden https://solana.fm/tx/2ANop8DQxoJsXNvfkAVAzpVLEk1UoGKcgP9YZcKfgRPzstgNaYWiBzJrBF4vxqEmS8Jz7sw926C9JSidJ9QcrsL1?cluster=mainnet-qn1


def dump_transaction_data(tx_response: GetTransactionResp):
    txs = json.loads(tx_response.to_json())
    print(json.dumps(txs, indent=4))


def get_client():
    # endpoint = 'https://api.mainnet-beta.solana.com'
    # endpoint = 'https://solana-api.projectserum.com'
    # endpoint = 'https://rpc.ankr.com/solana'
    endpoint = os.environ['endpoint']  # alchemy or quicknode
    solana_client = Client(endpoint=endpoint)
    res = solana_client.is_connected()
    if not res:
        print("Problems connection on connecting to endpoint")
        return
    return solana_client


def process_transaction(tx_hash, nft_treasuries):
    solana_client = get_client()
    if not solana_client:
        return
    tx_sig = Signature.from_string(tx_hash)
    tx_response = solana_client.get_transaction(tx_sig=tx_sig)
    transaction = tx_response.value.transaction

    # if status["Ok"]:
    #     # odd, if this is not null, it means an error occurred
    #     print(f"Problem with tx: {tx_hash}")

    if not marketplace.is_marketplace(transaction.transaction.message.account_keys):
        print(f"Transaction {tx_hash} is not a NFT marketplace transaction")
        return

    if marketplace.MagicEdenTransaction.is_marketplace_tx(transaction):
        me = marketplace.MagicEdenTransaction(transaction)
        if me.type == marketplace.MarketplaceInstructions.Sale:
            me.calculate_fees(nft_treasuries)
            # dump_transaction_data(tx_response)
            # print(f"Found a Magic Eden transaction of {me.type} for {me.price} SOL: {tx_hash}")
            # print(f"\t - creators_fee: {me.creators_fee} SOL ({(me.creators_fee / me.price) * 100:.2f}%)")
            # print(f"\t - marketplace_fee: {me.marketplace_fee} SOL ({(me.marketplace_fee / me.price) * 100:.2f}%)")
            # print(json.dumps(me.executed_instructions, indent=4))
            return me
    return False


def api_entrypoint(wallet_address: str, collection_candy_machine_ids: List[str]):
    solana_client = get_client()
    if not solana_client:
        return

    output = list()
    owned_nfts = nfts.find_nft(solana_client, wallet_address, collection_candy_machine_ids)

    print(f"Wallet {wallet_address} has {len(owned_nfts)} NFTs from our collection: "
          f"{[e['data']['name'] for e in owned_nfts]}")

    nft_treasuries = [c.decode("utf8") for c in owned_nfts[0]['data']['creators'][1:]]
    for owned_nft in owned_nfts:
        trans = get_nft_history(owned_nft['mint'].decode("utf8"), nft_treasuries)
        output.append(trans)

    print("Finished processing")
    for me in output:
        print(f"Found a Magic Eden transaction of {me.type} for {me.price} SOL: {me.encoded_tx}")
        print(f"\t - creators_fee: {me.creators_fee} SOL ({(me.creators_fee / me.price) * 100:.2f}%)")
        print(f"\t - marketplace_fee: {me.marketplace_fee} SOL ({(me.marketplace_fee / me.price) * 100:.2f}%)")


def get_nft_history(nft_mint_address: str, nft_treasuries):
    # https://stackoverflow.com/questions/72903266/get-all-transactions-for-an-nft-on-solana
    solana_client = get_client()
    transactions_batch = solana_client.get_signatures_for_address(PublicKey(nft_mint_address), limit=100)

    for trans in transactions_batch.value:
        block_time = trans.block_time
        signature = trans.signature

        print(f"Working with {signature} from {datetime.fromtimestamp(block_time)}")
        try:
            trans = process_transaction(str(signature), nft_treasuries)
            if trans:
                print("found one")
                return trans
        except Exception as e:
            print(e.args)


def main():

    tx_hash = "2ANop8DQxoJsXNvfkAVAzpVLEk1UoGKcgP9YZcKfgRPzstgNaYWiBzJrBF4vxqEmS8Jz7sw926C9JSidJ9QcrsL1"
    # https://explorer.solana.com/tx/5Ko8Gi5NyJg1k2j7mdErjYGhENWdtVSnBCeJfD1Y7UWvJqsgVxjgWBuCjbxKuiQdAD6Fb1Chxd15bj1gEPzWPr6W
    tx_hash = "5Ko8Gi5NyJg1k2j7mdErjYGhENWdtVSnBCeJfD1Y7UWvJqsgVxjgWBuCjbxKuiQdAD6Fb1Chxd15bj1gEPzWPr6W"
    tx_hash = "443p6HwXwSqVBYBxGn5TvtYhgPzHosMX7XaK9AVAv2cMjUjAuG2GhBfQ23cQccyxwNxsdQuivoUmf3gCE5CyTqdt"
    # https://solana.fm/tx/5viR6rqH2CEieDQMEk11JcNN18R5vnhg8iAL8zH4SwNFvx93ik243aTyYQRQUhAs8HnfrcfBRzrt3wFKtxCaTWWW?cluster=mainnet-qn1
    # 5viR6... has creator fee paid and magic eden fees
    tx_hash = "5viR6rqH2CEieDQMEk11JcNN18R5vnhg8iAL8zH4SwNFvx93ik243aTyYQRQUhAs8HnfrcfBRzrt3wFKtxCaTWWW"
    # owner BYhbuuLPaM7zL18gGTDPzkVVTPzddrZPZiuhDZqYv5bn
    # process_transaction(tx_hash)

    # nft is "2AHSrTqXMX9rk9zdBmnNAowiAz4VMATLiyeftpB1Tyn"
    # own = "46BtRifF7jVcMYaoPu9E6Mdh9ahyEr8TMkrxKFwJ3QDa"  # animal
    # x = nfts.find_nft(solana_client, PublicKey(own))
    # api_entrypoint("4gHhR7ZywaWEQ1aqT9hbGDu78DC9BdXxvD4cPKeAfdmi", "71ghWqucipW661X4ht61qvmc3xKQGMBGZxwSDmZrYQmf")

    # degods 6f7evqx9wtZbsK5T5GLwWAz7PYf2dJ2CabfiuoyxKjEw 6XxjKYFbcndh2gDcsUrmZgVEsoDxXMnfsaGY6fpTJzNr
    api_entrypoint("6f7evqx9wtZbsK5T5GLwWAz7PYf2dJ2CabfiuoyxKjEw",
                   ["9MynErYQ5Qi6obp4YwwdoDmXkZ1hYVtPUqYmJJ3rZ9Kn", "8RMqBV79p8sb51nMaKMWR94XKjUvD2kuUSAkpEJTmxyx"])

    # print(json.dumps(x, indent=4))
    # x = nfts.get_metadata(solana_client, PublicKey(own))

    # a degod mint address from the above owner 7Emgb9ck74kLar3PFd4xRL4YwACGUHYk4hFPJN21zXKB
    # get_nft_history("7Emgb9ck74kLar3PFd4xRL4YwACGUHYk4hFPJN21zXKB")


if __name__ == "__main__":
    main()

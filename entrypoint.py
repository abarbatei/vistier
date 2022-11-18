import os
import json
import traceback
from typing import List
from datetime import datetime

from solana.rpc.api import Client, PublicKey
from solders.signature import Signature

import nfts
import marketplace
import marketplace.templates


def process_transaction(solana_client, tx_sig: Signature, nft_treasuries: List[str]):
    tx_response = solana_client.get_transaction(tx_sig=tx_sig)
    transaction = tx_response.value.transaction

    if not marketplace.is_marketplace(transaction.transaction.message.account_keys):
        print(f"Transaction {tx_sig} is not a NFT marketplace transaction")
        return

    if marketplace.MagicEdenTransaction.is_marketplace_tx(transaction):
        marketplace_transaction = marketplace.MagicEdenTransaction(transaction)
        if marketplace_transaction.is_sale():
            marketplace_transaction.calculate_fees(nft_treasuries)
            return marketplace_transaction
    return


def get_nft_marketplace_history(solana_client, nft_mint_address: str, nft_treasuries: List[str]):
    transactions_batch = solana_client.get_signatures_for_address(PublicKey(nft_mint_address), limit=100)
    signature = None

    maximum_to_check = 100
    query_chunk_size = 100
    already_checked = 0

    while True:
        for transaction in transactions_batch.value:
            block_time = transaction.block_time
            signature = transaction.signature

            print(f"Processing tx:{signature} from {datetime.fromtimestamp(block_time)}")
            try:
                transaction = process_transaction(solana_client, signature, nft_treasuries)
                if transaction:

                    transaction.sold_nft_mint_address = nft_mint_address
                    transaction.sell_signature = signature
                    transaction.sell_block_time = block_time

                    print(f"Found sell transaction for NFT {nft_mint_address}. tx:{signature}")
                    return transaction

                # TODO also check if transaction is a MINT, for cases where owner minted instead of buying

            except Exception:
                print(f"Error processing transaction: {signature}:{traceback.format_exc()}")
                from utils import dump_transaction_data
                dump_transaction_data(solana_client.get_transaction(tx_sig=signature))

        already_checked += query_chunk_size
        if already_checked >= maximum_to_check:
            print(f"Tolerated tx parsing limit of {maximum_to_check} reached, exiting")
            return

        transactions_batch = solana_client.get_signatures_for_address(PublicKey(nft_mint_address),
                                                                      limit=query_chunk_size,
                                                                      before=signature)


def api_entrypoint(wallet_address: str, collection_candy_machine_ids: List[str]) -> dict:
    endpoint = os.environ.get('SOLANA_RPC_ENDPOINT', 'https://api.mainnet-beta.solana.com')
    solana_client = Client(endpoint=endpoint)
    if not solana_client.is_connected():
        raise Exception(f"Could not connect to mainnet RPC endpoint: {endpoint}!")

    output_response = {
        "owner_address": wallet_address,
        "collection_creator_fee_percent_on_sale": None,
        "total_fees_on_owned_nfts": {
            "creator": 0,
            "marketplace": 0
        },
        'owned_nfts_count': 0,
        "owned_nfts": list(),
        "transactions": list()
    }

    print(f"Processing wallet {wallet_address} with regards to collection CM Ids: {collection_candy_machine_ids}")

    owned_nfts = nfts.find_nft(solana_client, wallet_address, collection_candy_machine_ids)
    print(f"Wallet {wallet_address} has {len(owned_nfts)} NFTs from our collection:")

    if not owned_nfts:
        print("exiting")
        return output_response

    for owned_nft in owned_nfts:
        print(f"\t- {owned_nft['data']['name']:<12} mint_address: {owned_nft['mint']}")

    collection_creator_fee = owned_nfts[0]['data']['seller_fee_basis_points']

    output_response['owned_nfts'] = [o['mint'] for o in owned_nfts]
    output_response['owned_nfts_count'] = len(output_response['owned_nfts'])
    output_response['collection_creator_fee_percent_on_sale'] = collection_creator_fee/100

    nft_treasuries = [o for o in owned_nfts[0]['data']['creators'][1:]]
    print(f"Collection has {len(nft_treasuries)} treasuries: {nft_treasuries} "
          f"and a creators fee tax of: {collection_creator_fee/100}%")

    print("Processing each owned NFT to determine fee payments history")
    for owned_nft in owned_nfts:
        transaction = get_nft_marketplace_history(solana_client, owned_nft['mint'], nft_treasuries)
        transaction.sold_nft_name = owned_nft['data']['name']

        print(f"Found a {transaction.marketplace_name} transaction of {transaction.type} "
              f"for {transaction.price} SOL: {transaction.encoded_tx.transaction.signatures[0]}")
        print(f"\t - creators_fee: {transaction.creators_fee} SOL "
              f"({(transaction.creators_fee / transaction.price) * 100:.2f}%)")
        print(f"\t - marketplace_fee: {transaction.marketplace_fee} SOL "
              f"({(transaction.marketplace_fee / transaction.price) * 100:.2f}%)")
        output_response['transactions'].append(
            {
                'tx': str(transaction.sell_signature),
                "operation": transaction.type,
                'block_time': transaction.sell_block_time,
                "mint": transaction.sold_nft_mint_address,
                'name': transaction.sold_nft_name,
                'creator_fee_paid': transaction.creators_fee,
                'market_fee_paid': transaction.marketplace_fee
            }
        )
        output_response['total_fees_on_owned_nfts']['creator'] += transaction.creators_fee
        output_response['total_fees_on_owned_nfts']['marketplace'] += transaction.marketplace_fee

    return output_response


def main():
    wallet_address = "6f7evqx9wtZbsK5T5GLwWAz7PYf2dJ2CabfiuoyxKjEw"
    collection_candy_machine_ids = [  # this is an example with DeGods
        "9MynErYQ5Qi6obp4YwwdoDmXkZ1hYVtPUqYmJJ3rZ9Kn", "8RMqBV79p8sb51nMaKMWR94XKjUvD2kuUSAkpEJTmxyx"
    ]

    # wallet_address = "34SPGTEybdNiEJ4LKeZPYH9aZA3K9g1X7m8Eu1wWcco7"
    # collection_candy_machine_ids = ["71ghWqucipW661X4ht61qvmc3xKQGMBGZxwSDmZrYQmf"]  # this is for SSC
    response = api_entrypoint(wallet_address, collection_candy_machine_ids)

    print(json.dumps(response, indent=4))


if __name__ == "__main__":
    main()

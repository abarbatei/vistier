import os
import json
import traceback
from typing import List
from datetime import datetime, timedelta
import solders
from solders.rpc.responses import GetTransactionResp

from solders.transaction_status import EncodedTransactionWithStatusMeta
from solana.rpc.api import Client, PublicKey
from solders.signature import Signature

import nfts
import marketplace
from dotenv import load_dotenv

load_dotenv()


def process_transaction_for_sale(solana_client, tx_sig: Signature, nft_treasuries: List[str]):
    tx_response: GetTransactionResp = solana_client.get_transaction(tx_sig=tx_sig)
    if not tx_response.value:
        return
    transaction = tx_response.value.transaction

    if not marketplace.is_marketplace(transaction.transaction.message.account_keys):
        return

    if marketplace.MagicEdenTransaction.is_marketplace_tx(transaction):
        marketplace_transaction = marketplace.MagicEdenTransaction(tx_response)
        if marketplace_transaction.is_sale():
            marketplace_transaction.calculate_fees(nft_treasuries)
            return marketplace_transaction
    return


def get_nft_marketplace_history(solana_client, nft_mint_address: str, nft_treasuries: List[str],
                                max_tx_cnt_to_check=150):
    query_chunk_size = min(1000, max_tx_cnt_to_check)
    signature_batch = solana_client.get_signatures_for_address(PublicKey(nft_mint_address), limit=query_chunk_size)
    signature = None

    processed_tx = 0
    while True:

        for transaction in signature_batch.value:
            block_time = datetime.fromtimestamp(transaction.block_time)
            processed_tx += 1

            signature = transaction.signature

            print(f"Processing #{processed_tx} tx:{signature} from {block_time}")
            try:
                marketplace_tx = process_transaction_for_sale(solana_client, signature, nft_treasuries)
                if marketplace_tx:
                    print(f"Found sell transaction for NFT {nft_mint_address}. tx:{signature}")
                    return marketplace_tx

            except Exception:
                print(f"Error processing transaction: {signature}:{traceback.format_exc()}")
                from utils import dump_transaction_data
                dump_transaction_data(solana_client.get_transaction(tx_sig=signature))

        if processed_tx >= max_tx_cnt_to_check:
            print(f"Tolerated tx parsing limit of {max_tx_cnt_to_check} reached, exiting")
            return

        signature_batch = solana_client.get_signatures_for_address(PublicKey(nft_mint_address),
                                                                   limit=query_chunk_size,
                                                                   before=signature)
        if not len(signature_batch.value):
            print("No more transactions with this token, we reached mint")
            return


def get_client():
    endpoint = os.environ.get('SOLANA_RPC_ENDPOINT', 'https://api.mainnet-beta.solana.com')
    solana_client = Client(endpoint=endpoint)
    if not solana_client.is_connected():
        raise Exception(f"Could not connect to mainnet RPC endpoint: {endpoint}!")
    return solana_client


def api_entrypoint(wallet_address: str, collection_candy_machine_ids: List[str]) -> dict:

    solana_client = get_client()

    output_response = {
        "owner_address": wallet_address,
        "creator_fee_percent_on_sale": None,
        "fees_on_owned_nfts": {
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

    escrowed_nfts = get_escrowed_nfts(solana_client, wallet_address)
    print(f"Wallet has {len(escrowed_nfts)} escrowed NFTs")
    owned_nfts += [nfts.get_metadata(solana_client, mint_address) for mint_address in escrowed_nfts]

    if not owned_nfts:
        print("exiting")
        return output_response

    for owned_nft in owned_nfts:
        print(f"\t- {owned_nft['data']['name']:<12} mint_address: {owned_nft['mint']}")

    collection_creator_fee = owned_nfts[0]['data']['seller_fee_basis_points']

    output_response['owned_nfts'] = [o['mint'] for o in owned_nfts]
    output_response['owned_nfts_count'] = len(output_response['owned_nfts'])
    output_response['creator_fee_percent_on_sale'] = collection_creator_fee/100

    creators = owned_nfts[0]['data']['creators']
    if len(creators) == 1:
        nft_treasuries = creators
    else:
        nft_treasuries = [c for c in creators[1:]]
    print(f"Collection has {len(nft_treasuries)} treasuries: {nft_treasuries} "
          f"and a creators fee tax of: {collection_creator_fee/100}%")

    print("Processing each owned NFT to determine fee payments history")
    for owned_nft in owned_nfts:
        transaction = get_nft_marketplace_history(solana_client, owned_nft['mint'], nft_treasuries)
        if not transaction:
            continue
        transaction.sold_nft_name = owned_nft['data']['name']

        print(f"Found a {transaction.marketplace_name} transaction of {transaction.type} "
              f"for {transaction.price} SOL: {transaction.encoded_tx.transaction.signatures[0]}")
        print(f"\t - creators_fee: {transaction.creators_fee} SOL "
              f"({(transaction.creators_fee / transaction.price) * 100:.2f}%)")
        print(f"\t - marketplace_fee: {transaction.marketplace_fee} SOL "
              f"({(transaction.marketplace_fee / transaction.price) * 100:.2f}%)")
        output_response['transactions'].append(transaction.to_dict())
        output_response['fees_on_owned_nfts']['creator'] += transaction.creators_fee_lamports
        output_response['fees_on_owned_nfts']['marketplace'] += transaction.marketplace_fee_lamports

    output_response['fees_on_owned_nfts']['total'] = (
            output_response['fees_on_owned_nfts']['creator'] + output_response['fees_on_owned_nfts']['marketplace']
    )

    return output_response


def api_process_signature(sig: str, nft_treasuries: List[str]):
    solana_client = get_client()

    result = process_transaction_for_sale(solana_client, Signature.from_string(sig), nft_treasuries)
    if result:
        nft_metadata = nfts.get_metadata(solana_client, result.nft_mint)
        result.sold_nft_name = nft_metadata['data']['name']
        return result.to_dict()
    response = marketplace.empty_marketplace_data_dict()
    response['type'] = "Unknown"
    response['signature'] = sig
    return response


def get_escrowed_nfts(solana_client, nft_mint_address, max_tx_cnt_to_check=100):
    query_chunk_size = min(1000, max_tx_cnt_to_check)
    signature_batch = solana_client.get_signatures_for_address(PublicKey(nft_mint_address), limit=query_chunk_size)
    signature = None
    ledger = dict()
    processed_tx = 0

    while True:
        for transaction in signature_batch.value:
            block_time = datetime.fromtimestamp(transaction.block_time)
            processed_tx += 1

            signature = transaction.signature

            print(f"Processing #{processed_tx} tx:{signature} from {block_time}")
            try:
                tx_response: GetTransactionResp = solana_client.get_transaction(tx_sig=signature)
                marketplace_transaction = marketplace.MagicEdenTransaction(tx_response)

                if marketplace_transaction.is_listing():
                    mint = str(marketplace_transaction.nft_mint)
                    if mint not in ledger:
                        ledger[mint] = "listed"
                if marketplace_transaction.is_sale():
                    mint = str(marketplace_transaction.nft_mint)
                    if mint not in ledger:
                        ledger[mint] = "sale"
                # print(f"Current ledger: {json.dumps(ledger, indent=4)}")

            except Exception:
                print(f"Error processing transaction: {signature}:{traceback.format_exc()}")
                from utils import dump_transaction_data
                dump_transaction_data(solana_client.get_transaction(tx_sig=signature))

        if processed_tx >= max_tx_cnt_to_check:
            print(f"Tolerated tx parsing limit of {max_tx_cnt_to_check} reached, exiting")
            break

        signature_batch = solana_client.get_signatures_for_address(PublicKey(nft_mint_address),
                                                                   limit=query_chunk_size,
                                                                   before=signature)
        if not len(signature_batch.value):
            print("No more transactions with this token. We reached mint")
            return
    return [nft_address for nft_address in ledger.keys() if ledger[nft_address] == "listed"]


def main():
    wallet_address = "6f7evqx9wtZbsK5T5GLwWAz7PYf2dJ2CabfiuoyxKjEw"
    collection_candy_machine_ids = [  # this is an example with DeGods
        "9MynErYQ5Qi6obp4YwwdoDmXkZ1hYVtPUqYmJJ3rZ9Kn", "8RMqBV79p8sb51nMaKMWR94XKjUvD2kuUSAkpEJTmxyx"
    ]

    # wallet_address = "34SPGTEybdNiEJ4LKeZPYH9aZA3K9g1X7m8Eu1wWcco7"
    # collection_candy_machine_ids = ["71ghWqucipW661X4ht61qvmc3xKQGMBGZxwSDmZrYQmf"]  # this is for SSC

    wallet_address = "djq8NNpWTEDGFZyu58euBSQuqAU8ta4exSffrPqQHNi"
    collection_candy_machine_ids = ["yootn8Kf22CQczC732psp7qEqxwPGSDQCFZHkzoXp25"]  # this is for yoot

    wallet_address = "DPFjrR6ybkyoxrcETdVCw7r3ftSMWiZXZds6rrXd1QfJ"
    collection_candy_machine_ids = ["yootn8Kf22CQczC732psp7qEqxwPGSDQCFZHkzoXp25"]  # this is for yoot

    response = api_entrypoint(wallet_address, collection_candy_machine_ids)

    print(json.dumps(response, indent=4))


if __name__ == "__main__":
    main()

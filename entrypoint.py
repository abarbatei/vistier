import os
import json
import traceback
import asyncio

from typing import List
from datetime import datetime

from solana.rpc.api import Client, PublicKey
from solana.rpc.async_api import AsyncClient
from solders.signature import Signature
from solders.rpc.responses import GetTransactionResp
from dotenv import load_dotenv
import platform

import nfts
import marketplace

load_dotenv()

if platform.system() == 'Windows':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def get_sale(solana_client, tx_sig: Signature, nft_treasuries: List[str]):
    tx_response: GetTransactionResp = await solana_client.get_transaction(tx_sig=tx_sig)
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


async def _get_nft_last_sale(nft_batch, index_base, nft_treasuries: List[str], max_tx_cnt_to_check=300):
    solana_client = await get_async_client()
    query_chunk_size = min(1000, max_tx_cnt_to_check)

    nft_sell_txs = list()

    for nft_index, nft_mint_address in enumerate(nft_batch):
        signature_batch = await solana_client.get_signatures_for_address(PublicKey(nft_mint_address),
                                                                         limit=query_chunk_size)
        for index, confirmed_transaction in enumerate(signature_batch.value):
            block_time = datetime.fromtimestamp(confirmed_transaction.block_time)

            signature = confirmed_transaction.signature

            print(f"Processing NFT {index_base + nft_index} tx #{index + 1} tx:{signature} from {block_time}")
            try:
                sale_tx = await get_sale(solana_client, signature, nft_treasuries)
                if sale_tx:
                    nft_sell_txs.append(sale_tx)
                    print(f"Found sale for NFT {index_base + nft_index}")
                    break
            except Exception:
                print(f"Error processing transaction: {signature}:{traceback.format_exc()}")
    return nft_sell_txs


def split(list_, parts_cnt):
    # https://stackoverflow.com/questions/2130016/splitting-a-list-into-n-parts-of-approximately-equal-length
    k, m = divmod(len(list_), parts_cnt)
    return (list_[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(parts_cnt))


async def get_nft_last_sale_batch(owned_nfts, nft_treasuries):

    background_tasks = list()

    worker_count = min(3, len(owned_nfts))

    nft_mint_addresses = [k for k in owned_nfts.keys()]

    index_base = 0
    for batch in split(nft_mint_addresses, worker_count):
        background_tasks.append(_get_nft_last_sale(batch, index_base, nft_treasuries))
        index_base += len(batch)

    results = await asyncio.gather(*background_tasks)
    combined = sum(results, [])
    for tx in combined:
        tx.sold_nft_name = owned_nfts[str(tx.nft_mint)]
    return combined


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
                marketplace_tx = get_sale(solana_client, signature, nft_treasuries)
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


async def api_entrypoint(wallet_address: str, collection_candy_machine_ids: List[str]) -> dict:

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

    escrowed_nfts = await get_escrow_nfts(solana_client, wallet_address)
    print(f"Wallet has {len(escrowed_nfts)} escrowed NFTs")
    owned_nfts += [nfts.get_metadata(solana_client, mint_address) for mint_address in escrowed_nfts]

    if not owned_nfts:
        print("exiting")
        return output_response

    for owned_nft in owned_nfts:
        print(f"\t- {owned_nft['data']['name']:<12} mint_address: {owned_nft['mint']}")

    collection_creator_fee = owned_nfts[0]['data']['seller_fee_basis_points']

    output_response['owned_nfts'] = {o['mint']: o['data']['name'] for o in owned_nfts}
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

    transactions = await get_nft_last_sale_batch(output_response['owned_nfts'], nft_treasuries)
    for transaction in transactions:

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


async def api_process_signature(sig: str, nft_treasuries: List[str]):
    solana_client = get_client()
    solana_async_client = await get_async_client()

    result = await get_sale(solana_async_client, Signature.from_string(sig), nft_treasuries)
    if result:
        nft_metadata = nfts.get_metadata(solana_client, result.nft_mint)
        result.sold_nft_name = nft_metadata['data']['name']
        return result.to_dict()
    response = marketplace.empty_marketplace_data_dict()
    response['type'] = "Unknown"
    response['signature'] = sig
    return response


async def get_async_client():
    endpoint = os.environ.get('SOLANA_RPC_ENDPOINT', 'https://api.mainnet-beta.solana.com')
    solana_client = AsyncClient(endpoint=endpoint)
    if not await solana_client.is_connected():
        raise Exception(f"Could not connect to mainnet RPC endpoint: {endpoint}!")
    return solana_client


async def _process_tx_batch_for_escrow(signature_batch, index_base):
    solana_client = await get_async_client()
    ledger = dict()

    for index, transaction in enumerate(signature_batch):
        block_time = datetime.fromtimestamp(transaction.block_time)

        signature = transaction.signature

        print(f"Processing #{index_base + index + 1} tx:{signature} from {block_time}")
        try:
            tx_response: GetTransactionResp = await solana_client.get_transaction(tx_sig=signature)
            marketplace_transaction = marketplace.MagicEdenTransaction(tx_response)

            if marketplace_transaction.is_listing():
                mint = str(marketplace_transaction.nft_mint)
                if mint not in ledger:
                    ledger[mint] = {
                        "type": "listed",
                        "timestamp": transaction.block_time,
                        "index": index_base + index
                    }

            if marketplace_transaction.is_sale():
                mint = str(marketplace_transaction.nft_mint)
                if mint not in ledger:
                    ledger[mint] = {
                        "type": "sale",
                        "timestamp": transaction.block_time,
                        "index": index_base + index
                    }

        except Exception:
            print(f"Error processing transaction: {signature}:{traceback.format_exc()}")

    return ledger


def equal_chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


async def get_escrow_nfts(solana_client, nft_mint_address, max_tx_cnt_to_check=100):
    query_chunk_size = min(1000, max_tx_cnt_to_check)
    signature_batch = solana_client.get_signatures_for_address(PublicKey(nft_mint_address), limit=query_chunk_size)

    background_tasks = list()

    worker_count = 3

    index_base = 0
    for batch in split(signature_batch.value, worker_count):
        background_tasks.append(_process_tx_batch_for_escrow(batch, index_base))
        index_base += len(batch)

    results = await asyncio.gather(*background_tasks)
    position_mapped = dict()
    for parts in results:
        for mint, tx_data in parts.items():
            position_mapped[tx_data['index']] = {
                "type": tx_data['type'],
                "mint": mint,
                "timestamp": tx_data["timestamp"]
            }
    sorted_dict = dict(sorted(position_mapped.items()))
    seen = set()
    output = list()
    for timestamp, tx_data in sorted_dict.items():
        if tx_data['mint'] not in seen and tx_data['type'] == "listed":
            output.append(tx_data['mint'])
        seen.add(tx_data['mint'])
    return output


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

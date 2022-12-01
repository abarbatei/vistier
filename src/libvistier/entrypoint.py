import asyncio
import platform

from typing import List

from solders.rpc.responses import GetTransactionResp
from solders.signature import Signature

from . import nfts
from . import marketplace
from .clients import get_client, get_async_client
from .escrows import get_escrow_nfts
from .sells import get_nft_last_sale_batch
from .utils import get_logger


logger = get_logger("VistierAPI")

if platform.system() == 'Windows':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def api_search_wallet_for_nfts(settings: dict,
                                     wallet_address: str,
                                     collection_candy_machine_ids: List[str]) -> dict:

    solana_client = get_client()

    output_response = {
        "owner_address": wallet_address,
        "creator_fee_percent_on_sale": None,
        "fees_on_owned_nfts": {
            "creator": 0,
            "marketplace": 0,
            "total": 0
        },
        'owned_nfts_count': 0,
        "owned_nfts": dict(),
        "transactions": list()
    }

    logger.info(f"Processing wallet {wallet_address} with regards to collection CM Ids: {collection_candy_machine_ids}")

    owned_nfts = nfts.find_wallet_nfts(solana_client, wallet_address, collection_candy_machine_ids)
    logger.info(f"Wallet {wallet_address} has {len(owned_nfts)} NFTs from our collection:")

    escrowed_nfts = await get_escrow_nfts(solana_client,
                                          wallet_address,
                                          worker_count=settings['escrow_tx_workers'],
                                          tx_cnt_to_check=settings['escrow_tx_to_process'],
                                          max_tx_cnt_to_check=settings['escrow_max_tx_to_process'])

    targeted_collection_nfts = nfts.find_nfts_of_collection(solana_client,
                                                            mint_addresses=escrowed_nfts,
                                                            collection_candy_machin_ids=collection_candy_machine_ids)

    logger.info(f"Wallet has {len(escrowed_nfts)} escrowed NFTs, out of which {len(targeted_collection_nfts)} "
                f"are the targeted collection")
    owned_nfts += targeted_collection_nfts

    if not owned_nfts:
        logger.info("owner has no NFTs belonging to the targeted collection, exiting")
        return output_response

    for owned_nft in owned_nfts:
        logger.info(f"{owned_nft['data']['name']:<12} mint_address: {owned_nft['mint']}")

    collection_creator_fee = owned_nfts[0]['data']['seller_fee_basis_points']

    output_response['owned_nfts'] = {o['mint']: o['data']['name'] for o in owned_nfts}
    output_response['owned_nfts_count'] = len(output_response['owned_nfts'])
    output_response['creator_fee_percent_on_sale'] = collection_creator_fee/100

    creators = owned_nfts[0]['data']['creators']
    if len(creators) == 1:
        nft_treasuries = creators
    else:
        nft_treasuries = [c for c in creators[1:]]
    logger.info(f"Collection has {len(nft_treasuries)} treasuries: {nft_treasuries} "
                f"and a creators fee tax of: {collection_creator_fee/100}%")

    logger.info("Processing each owned NFT to determine fee payments history")

    transactions = await get_nft_last_sale_batch(output_response['owned_nfts'],
                                                 nft_treasuries,
                                                 worker_count=settings['sales_tx_workers'],
                                                 tx_cnt_to_check_=settings['sales_tx_to_process'],
                                                 max_tx_cnt_to_check=settings['sales_max_tx_to_process'],
                                                 max_nfts_to_process=settings['sales_max_nft_to_inspect'])
    for transaction in transactions:

        logger.info(f"Found a {transaction.marketplace_name} transaction of {transaction.type} "
                    f"for {transaction.price} SOL: {transaction.encoded_tx.transaction.signatures[0]} "
                    f"with creators_fee: {transaction.creators_fee} SOL "
                    f"({(transaction.creators_fee / transaction.price) * 100:.2f}%) and "
                    f"marketplace_fee: {transaction.marketplace_fee} SOL "
                    f"({(transaction.marketplace_fee / transaction.price) * 100:.2f}%)")
        output_response['transactions'].append(transaction.to_dict())
        output_response['fees_on_owned_nfts']['creator'] += transaction.creators_fee_lamports
        output_response['fees_on_owned_nfts']['marketplace'] += transaction.marketplace_fee_lamports

    output_response['fees_on_owned_nfts']['total'] = (
            output_response['fees_on_owned_nfts']['creator'] + output_response['fees_on_owned_nfts']['marketplace']
    )

    return output_response


async def get_market_tx(solana_client, tx_sig: Signature, nft_treasuries: List[str]):
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
        return marketplace_transaction
    return


async def api_process_signature(sig: str, nft_treasuries: List[str]):
    solana_client = get_client()
    solana_async_client = await get_async_client()
    result = await get_market_tx(solana_async_client, Signature.from_string(sig), nft_treasuries)
    if result:
        nft_metadata = nfts.get_metadata(solana_client, result.nft_mint)
        result.sold_nft_name = nft_metadata['data']['name']
        return result.to_dict()
    response = marketplace.empty_marketplace_data_dict()
    response['type'] = "Unknown"
    response['signature'] = sig
    return response

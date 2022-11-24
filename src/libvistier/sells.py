import asyncio
import traceback
from typing import List
from datetime import datetime

from solana.publickey import PublicKey
from solders.rpc.responses import GetTransactionResp
from solders.signature import Signature

from . import marketplace
from .clients import get_async_client
from .utils import split, get_logger

logger = get_logger("VistierAPI")


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


async def _get_nft_last_sale(nft_batch, index_base, nft_treasuries: List[str], tx_cnt_to_check, max_tx_cnt_to_check):
    solana_client = await get_async_client()
    query_chunk_size = min(max_tx_cnt_to_check, tx_cnt_to_check)

    nft_sell_txs = list()

    for nft_index, nft_mint_address in enumerate(nft_batch):
        signature_batch = await solana_client.get_signatures_for_address(PublicKey(nft_mint_address),
                                                                         limit=query_chunk_size)
        for index, confirmed_transaction in enumerate(signature_batch.value):
            block_time = datetime.fromtimestamp(confirmed_transaction.block_time)

            signature = confirmed_transaction.signature

            logger.info(f"Processing NFT {index_base + nft_index} tx #{index + 1} tx:{signature} from {block_time}")
            try:
                sale_tx = await get_sale(solana_client, signature, nft_treasuries)
                if sale_tx:
                    nft_sell_txs.append(sale_tx)
                    logger.info(f"Found sale for NFT {index_base + nft_index}")
                    break
            except Exception:
                logger.error(f"Error processing transaction: {signature}:{traceback.format_exc()}")
    return nft_sell_txs


async def get_nft_last_sale_batch(
        owned_nfts, nft_treasuries, worker_count, tx_cnt_to_check_, max_tx_cnt_to_check, max_nfts_to_process
):

    background_tasks = list()

    workers = min(worker_count, len(owned_nfts))

    nft_mint_addresses = [k for k in owned_nfts.keys()]
    nft_mint_addresses = nft_mint_addresses[:max_nfts_to_process]

    index_base = 0
    for batch in split(nft_mint_addresses, workers):
        background_tasks.append(_get_nft_last_sale(batch,
                                                   index_base,
                                                   nft_treasuries,
                                                   tx_cnt_to_check_,
                                                   max_tx_cnt_to_check)
                                )
        index_base += len(batch)

    results = await asyncio.gather(*background_tasks)
    combined = sum(results, [])
    for tx in combined:
        tx.sold_nft_name = owned_nfts[str(tx.nft_mint)]
    return combined

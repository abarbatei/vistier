import asyncio
import traceback
from datetime import datetime

from solana.publickey import PublicKey
from solders.rpc.responses import GetTransactionResp

import marketplace
from clients import get_async_client
from utils import split, get_logger

logger = get_logger("VistierAPI")


async def _process_tx_batch_for_escrow(signature_batch, index_base):
    solana_client = await get_async_client()
    ledger = dict()

    for index, transaction in enumerate(signature_batch):
        block_time = datetime.fromtimestamp(transaction.block_time)

        signature = transaction.signature

        logger.info(f"Processing #{index_base + index + 1} tx:{signature} from {block_time}")
        try:
            tx_response: GetTransactionResp = await solana_client.get_transaction(tx_sig=signature)
            marketplace_transaction = marketplace.MagicEdenTransaction(tx_response)

            if marketplace_transaction.is_escrow():
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
            logger.error(f"Error processing transaction: {signature}:{traceback.format_exc()}")

    return ledger


async def get_escrow_nfts(solana_client, nft_mint_address, tx_cnt_to_check, worker_count, max_tx_cnt_to_check):
    query_chunk_size = min(max_tx_cnt_to_check, tx_cnt_to_check)
    signature_batch = solana_client.get_signatures_for_address(PublicKey(nft_mint_address), limit=query_chunk_size)

    background_tasks = list()

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

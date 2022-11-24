import os

from solana.rpc.api import Client
from solana.rpc.async_api import AsyncClient


def get_client():
    endpoint = os.environ['SOLANA_RPC_ENDPOINT']
    solana_client = Client(endpoint=endpoint)
    if not solana_client.is_connected():
        raise Exception(f"Could not connect to mainnet RPC endpoint: {endpoint}!")
    return solana_client


async def get_async_client():
    endpoint = os.environ['SOLANA_RPC_ENDPOINT']
    solana_client = AsyncClient(endpoint=endpoint)
    if not await solana_client.is_connected():
        raise Exception(f"Could not connect to mainnet RPC endpoint: {endpoint}!")
    return solana_client

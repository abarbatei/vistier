import json
import struct
import base58
import base64

from typing import List

import solana
from solana.rpc.api import PublicKey
from solana.rpc.types import TokenAccountOpts


METADATA_PROGRAM_ID = PublicKey('metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s')


# taken from Metaplex python library
def unpack_metadata_account(data: bytes) -> dict:
    assert(data[0] == 4)
    i = 1
    source_account = base58.b58encode(bytes(struct.unpack('<' + "B"*32, data[i:i+32])))
    i += 32
    mint_account = base58.b58encode(bytes(struct.unpack('<' + "B"*32, data[i:i+32])))
    i += 32
    name_len = struct.unpack('<I', data[i:i+4])[0]
    i += 4
    name = struct.unpack('<' + "B"*name_len, data[i:i+name_len])
    i += name_len
    symbol_len = struct.unpack('<I', data[i:i+4])[0]
    i += 4
    symbol = struct.unpack('<' + "B"*symbol_len, data[i:i+symbol_len])
    i += symbol_len
    uri_len = struct.unpack('<I', data[i:i+4])[0]
    i += 4
    uri = struct.unpack('<' + "B"*uri_len, data[i:i+uri_len])
    i += uri_len
    fee = struct.unpack('<h', data[i:i+2])[0]
    i += 2
    has_creator = data[i]
    i += 1
    creators = []
    verified = []
    share = []
    if has_creator:
        creator_len = struct.unpack('<I', data[i:i+4])[0]
        i += 4
        for _ in range(creator_len):
            creator = base58.b58encode(bytes(struct.unpack('<' + "B"*32, data[i:i+32])))
            # creators.append(creator)
            creators.append(creator.decode("utf8"))
            i += 32
            verified.append(data[i])
            i += 1
            share.append(data[i])
            i += 1
    primary_sale_happened = bool(data[i])
    i += 1
    is_mutable = bool(data[i])
    metadata = {
        "update_authority": source_account.decode("utf8"),
        "mint": mint_account.decode("utf8"),
        "data": {
            "name": bytes(name).decode("utf-8").strip("\x00"),
            "symbol": bytes(symbol).decode("utf-8").strip("\x00"),
            "uri": bytes(uri).decode("utf-8").strip("\x00"),
            "seller_fee_basis_points": fee,
            "creators": creators,
            "verified": verified,
            "share": share,
        },
        "primary_sale_happened": primary_sale_happened,
        "is_mutable": is_mutable,
    }
    return metadata


def get_nft_pda(mint_key: str) -> PublicKey:
    return PublicKey.find_program_address([b'metadata', bytes(METADATA_PROGRAM_ID), bytes(PublicKey(mint_key))],
                                          METADATA_PROGRAM_ID)[0]


def get_metadata(solana_client, mint_address: str) -> dict:
    """
    An example of what it returns
    {
        "update_authority": "DGNZDSvy6emDXvBuCDRrpLVxcPaEcvKiStvvCivEJ38X",
        "mint": "2AHSrTqXMX9rk9zdBmnNAowiAz4VMATLiyeftpB1Tyn",
        "data": {
            "name": "Shadowy Super Coder #4049",
            "symbol": "SSC",
            "uri": "https://shdw-drive.genesysgo.net/8yHTE5Cz3hwcTdghynB2jgLuvKyRgKEz2n5XvSiXQabG/4049.json",
            "seller_fee_basis_points": 500,
            "creators": [
                "71ghWqucipW661X4ht61qvmc3xKQGMBGZxwSDmZrYQmf",
                "D6wZ5U9onMC578mrKMp5PZtfyc5262426qKsYJW7nT3p"
            ],
            "verified": [
                1,
                0
            ],
            "share": [
                0,
                100
            ]
        },
        "primary_sale_happened": true,
        "is_mutable": true
    }
    """
    account_info = solana_client.get_account_info(get_nft_pda(mint_address))

    acc_info = json.loads(account_info.to_json())
    if acc_info and acc_info['result'] and acc_info['result']['value'] and acc_info['result']['value']['data']:
        data = base64.b64decode(acc_info['result']['value']['data'][0])
        if data:
            return unpack_metadata_account(data)


def get_tokens_held_by_address(solana_client: solana.rpc.api.Client, public_key: PublicKey):
    opts = TokenAccountOpts(program_id=PublicKey("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"))
    result = solana_client.get_token_accounts_by_owner_json_parsed(public_key, opts)
    return json.loads(result.to_json())


def find_nft(solana_client: solana.rpc.api.Client,
             wallet_address: str,
             collection_candy_machin_ids: List[str]) -> List[dict]:

    opts = TokenAccountOpts(program_id=PublicKey("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"))
    result = solana_client.get_token_accounts_by_owner_json_parsed(PublicKey(wallet_address), opts)
    payload = json.loads(result.to_json())
    possible_nfts = list()

    for token_data in payload['result']['value']:

        # https://docs.metaplex.com/programs/token-metadata/overview
        if token_data['account']['data']['parsed']['info']['tokenAmount']['decimals'] != 0:
            continue

        if token_data['account']['data']['parsed']['info']['tokenAmount']['amount'] != '1':
            continue

        possible_nfts.append(token_data)

    nfts = list()

    for token_data in possible_nfts:
        metadata = get_metadata(solana_client, token_data['account']['data']['parsed']['info']['mint'])
        if not metadata or not metadata.get('data'):
            continue

        creators = metadata['data']['creators']
        verified = metadata['data']['verified']

        if not verified or verified[0] != 1:
            # NFT collection is not verified by indicated creator wallet, can be a scam!
            continue

        if not creators:
            continue

        if creators[0] in collection_candy_machin_ids:
            nfts.append(metadata)

    return nfts

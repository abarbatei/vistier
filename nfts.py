import struct
import base58
import json
from solana.rpc.api import PublicKey
from solana.rpc.types import TokenAccountOpts
import base64
import requests
"""
Code taken from https://github.com/michaelhly/solana-py/issues/48
"""

METADATA_PROGRAM_ID = PublicKey('metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s')


def unpack_metadata_account(data):
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
            creators.append(creator)
            i += 32
            verified.append(data[i])
            i += 1
            share.append(data[i])
            i += 1
    primary_sale_happened = bool(data[i])
    i += 1
    is_mutable = bool(data[i])
    metadata = {
        "update_authority": source_account,
        "mint": mint_account,
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


def get_nft_pda(mint_key) -> PublicKey:
    return PublicKey.find_program_address([b'metadata', bytes(METADATA_PROGRAM_ID), bytes(PublicKey(mint_key))],
                                          METADATA_PROGRAM_ID)[0]


def get_metadata(solana_client, mint_key):
    x = solana_client.get_account_info(get_nft_pda(mint_key))

    x = json.loads(x.to_json())
    if x and x['result'] and x['result']['value'] and x['result']['value']['data']:
        data = base64.b64decode(x['result']['value']['data'][0])
        if data:
            return unpack_metadata_account(data)


def get_tokens_held_by_address(solana_client, public_key: PublicKey):
    opts = TokenAccountOpts(program_id=PublicKey("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"))
    return solana_client.get_token_accounts_by_owner_json_parsed(public_key, opts)


def get_address_nfts(solana_client, public_key: PublicKey):
    opts = TokenAccountOpts(program_id=PublicKey("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"))
    result = solana_client.get_token_accounts_by_owner_json_parsed(public_key, opts)
    payload = json.loads(result.to_json())

    possible_nfts = list()
    for token_data in payload['result']['value']:

        # https://docs.metaplex.com/programs/token-metadata/overview
        if token_data['account']['data']['parsed']['info']['tokenAmount']['decimals'] != 0:
            continue

        # https://docs.metaplex.com/programs/token-metadata/changelog/v1.0
        # for must_have in ["name", "symbol", "uri", "creators", "update_authority", "primary_sale_happened",
        #                   "seller_fee_basis_points"]:
        #     if must_have not in token_data:
        #         print(f"Missing {must_have} from token")

        possible_nfts.append(token_data)

    nfts = list()

    for token_data in possible_nfts:
        mint_address = PublicKey(token_data['account']['data']['parsed']['info']['mint'])

        metadata = get_metadata(solana_client, mint_address)
        if not metadata or not metadata.get('data'):
            continue
        metadata = metadata['data']

        skip = False
        for must_have in ["name", "symbol", "uri", "seller_fee_basis_points"]:
            if must_have not in metadata:
                print(f"missing {must_have} from metadata for {mint_address}")
                skip = True
                break
        if skip:
            continue

        name = metadata["name"]
        symbol = metadata["symbol"]
        uri = metadata["uri"]

        try:
            response = requests.get(uri)
        except Exception as e:
            print(e.args)
            continue

        if response.status_code != 200:
            print(f"Failed to get data from {uri}, skipping")
            continue

        uri_content = response.json()

        # must have https://docs.metaplex.com/programs/token-metadata/changelog/v1.0#json-structure
        skip = False
        for must_have in ["name", "symbol", "properties"]:
            if must_have not in uri_content:
                print(f"missing {must_have} from uri_content for {name}:{symbol}:{uri}")
                skip = True
                break
        if skip:
            continue

        # example https://shdw-drive.genesysgo.net/8yHTE5Cz3hwcTdghynB2jgLuvKyRgKEz2n5XvSiXQabG/5240.json
        # image or animation properties
        if "image" not in uri_content and "animation_url" not in uri_content:
            print(f"missing image or animation_url from metadata for {name}:{symbol}:{uri}")

        nfts.append({
            "token_data": token_data,
            "metadata": metadata,
            "uri_data": uri_content
        })

    return nfts
